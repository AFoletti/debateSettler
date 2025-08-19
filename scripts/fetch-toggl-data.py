#!/usr/bin/env python3
"""
Fetch Toggl Track data and save to JSON file for GitHub Pages
This script runs daily via GitHub Actions
"""

import requests
import json
import os
import base64
import statistics
from datetime import datetime, timedelta
from pathlib import Path

class TogglDataFetcher:
    def __init__(self):
        self.api_token = os.getenv('TOGGL_API_TOKEN')
        self.workspace_name = os.getenv('TOGGL_WORKSPACE', 'DRE-P')
        self.base_url = "https://api.track.toggl.com/api/v9"
        
        if not self.api_token:
            raise ValueError("TOGGL_API_TOKEN environment variable is required")
        
        # Create auth header
        auth_header = base64.b64encode(f"{self.api_token}:api_token".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json"
        }
        self.workspace_id = None

    def get_workspace_id(self):
        """Get workspace ID by name"""
        if self.workspace_id:
            return self.workspace_id
            
        response = requests.get(f"{self.base_url}/workspaces", headers=self.headers)
        response.raise_for_status()
        
        workspaces = response.json()
        for workspace in workspaces:
            if workspace["name"] == self.workspace_name:
                self.workspace_id = workspace["id"]
                return self.workspace_id
        
        raise ValueError(f"Workspace '{self.workspace_name}' not found")

    def get_time_entries(self, start_date, end_date):
        """Fetch time entries from Toggl API"""
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        
        response = requests.get(
            f"{self.base_url}/me/time_entries",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

    def calculate_billable_hours(self, time_entries):
        """Calculate total billable hours"""
        total_seconds = 0
        for entry in time_entries:
            if entry.get("billable", False) and entry.get("duration", 0) > 0:
                total_seconds += entry["duration"]
        return round(total_seconds / 3600, 2)

    def calculate_absent_from_home_hours(self, time_entries):
        """Calculate hours absent from home (no HomeOffice tag)"""
        total_seconds = 0
        for entry in time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "HomeOffice" not in tags:
                    total_seconds += entry["duration"]
        return round(total_seconds / 3600, 2)

    def get_commute_back_home_times(self, time_entries):
        """Get statistics for commute back home times"""
        daily_last_commute = {}
        
        for entry in time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "Commuting" in tags:
                    start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                    date_key = start_time.date()
                    
                    if date_key not in daily_last_commute or start_time > daily_last_commute[date_key]["datetime"]:
                        daily_last_commute[date_key] = {
                            "datetime": start_time,
                            "end_time": datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else None
                        }
        
        back_home_times = []
        for entry in daily_last_commute.values():
            if entry["end_time"]:
                back_home_times.append(entry["end_time"].time())
        
        if not back_home_times:
            return {"mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        times_in_minutes = [t.hour * 60 + t.minute for t in back_home_times]
        
        def minutes_to_time(minutes):
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            return f"{hours:02d}:{mins:02d}"
        
        mean_minutes = statistics.mean(times_in_minutes)
        median_minutes = statistics.median(times_in_minutes)
        
        return {
            "mean": minutes_to_time(mean_minutes),
            "median": minutes_to_time(median_minutes),
            "earliest": minutes_to_time(min(times_in_minutes)),
            "latest": minutes_to_time(max(times_in_minutes)),
            "count": len(back_home_times)
        }

    def get_home_office_end_times(self, time_entries):
        """Get statistics for HomeOffice end times"""
        daily_last_home_office = {}
        
        for entry in time_entries:
            if entry.get("duration", 0) > 0:
                tags = entry.get("tags", [])
                if "HomeOffice" in tags:
                    start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                    date_key = start_time.date()
                    
                    if date_key not in daily_last_home_office or start_time > daily_last_home_office[date_key]["datetime"]:
                        daily_last_home_office[date_key] = {
                            "datetime": start_time,
                            "end_time": datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else None
                        }
        
        end_times = []
        for entry in daily_last_home_office.values():
            if entry["end_time"]:
                end_times.append(entry["end_time"].time())
        
        if not end_times:
            return {"mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        times_in_minutes = [t.hour * 60 + t.minute for t in end_times]
        
        def minutes_to_time(minutes):
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            return f"{hours:02d}:{mins:02d}"
        
        mean_minutes = statistics.mean(times_in_minutes)
        median_minutes = statistics.median(times_in_minutes)
        
        return {
            "mean": minutes_to_time(mean_minutes),
            "median": minutes_to_time(median_minutes),
            "earliest": minutes_to_time(min(times_in_minutes)),
            "latest": minutes_to_time(max(times_in_minutes)),
            "count": len(end_times)
        }

    def calculate_late_work_frequency(self, time_entries):
        """Calculate how often work happened after 20:00"""
        late_work_days = set()
        total_work_days = set()
        
        for entry in time_entries:
            if entry.get("duration", 0) > 0:
                start_time = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
                date_key = start_time.date()
                total_work_days.add(date_key)
                
                end_time = datetime.fromisoformat(entry["stop"].replace("Z", "+00:00")) if entry.get("stop") else start_time
                
                if start_time.hour >= 20 or end_time.hour >= 20:
                    late_work_days.add(date_key)
        
        total_days = len(total_work_days)
        late_days = len(late_work_days)
        percentage = (late_days / total_days * 100) if total_days > 0 else 0
        
        return {
            "late_work_days": late_days,
            "total_work_days": total_days,
            "percentage": round(percentage, 1)
        }

    def fetch_and_save_metrics(self):
        """Fetch all metrics and save to JSON file"""
        print(f"🚀 Fetching Toggl data for workspace: {self.workspace_name}")
        
        # Get workspace ID
        workspace_id = self.get_workspace_id()
        print(f"📡 Found workspace ID: {workspace_id}")
        
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        
        print(f"📅 Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Fetch time entries
        time_entries = self.get_time_entries(start_date_str, end_date_str)
        print(f"📊 Retrieved {len(time_entries)} time entries")
        
        # Calculate all metrics
        metrics = {
            "billable_hours": self.calculate_billable_hours(time_entries),
            "absent_from_home_hours": self.calculate_absent_from_home_hours(time_entries),
            "commute_back_home_stats": self.get_commute_back_home_times(time_entries),
            "home_office_end_stats": self.get_home_office_end_times(time_entries),
            "late_work_frequency": self.calculate_late_work_frequency(time_entries),
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "total_entries": len(time_entries),
            "last_updated": datetime.now().isoformat(),
            "workspace_name": self.workspace_name
        }
        
        # Ensure data directory exists
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Save to JSON file
        output_file = data_dir / "metrics.json"
        with open(output_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"✅ Metrics saved to {output_file}")
        print(f"💾 Billable Hours: {metrics['billable_hours']}h")
        print(f"💾 Time Away: {metrics['absent_from_home_hours']}h")
        print(f"💾 Total Entries: {metrics['total_entries']}")

def main():
    try:
        fetcher = TogglDataFetcher()
        fetcher.fetch_and_save_metrics()
        print("🎉 Data fetch completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()