#!/usr/bin/env python3
"""
Fetch raw Toggl Track data and save to JSON file for GitHub Pages
This script runs daily via GitHub Actions and stores RAW data only,
with 'description' field removed from entries before saving.
"""

import requests
import json
import os
import base64
from datetime import datetime, timedelta
from pathlib import Path

from collections import defaultdict


def _parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string from Toggl, handling trailing 'Z'."""
    if not dt_str:
        return None
    # Toggl returns e.g. "2025-11-28T13:26:00+00:00" or with "Z"
    try:
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _update_history_daily(time_entries, workspace_name: str, data_dir: Path) -> None:
    """Update data/history_daily.json with per-day aggregates.

    This keeps a long-term daily history by overwriting the last 90 days
    while preserving older days.
    """
    history_path = data_dir / "history_daily.json"

    # Load existing history (if any)
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
            existing_days = {d["date"]: d for d in history.get("daily_metrics", [])}
        except Exception:
            history = {}
            existing_days = {}
    else:
        history = {}
        existing_days = {}

    # Group entries by date (YYYY-MM-DD)
    per_day = defaultdict(list)
    for entry in time_entries:
        duration = entry.get("duration", 0) or 0
        if duration <= 0:
            continue
        start = _parse_iso_datetime(entry.get("start"))
        stop = _parse_iso_datetime(entry.get("stop"))
        if not start:
            continue
        date_str = start.date().isoformat()
        per_day[date_str].append({
            "start": start,
            "stop": stop,
            "duration": duration,
            "billable": bool(entry.get("billable")),
            "tags": entry.get("tags") or [],
        })

    def _minutes_since_midnight(dt: datetime) -> int:
        return dt.hour * 60 + dt.minute

    # Compute metrics for each day in the current 90-day window
    for date_str, entries in per_day.items():
        if not entries:
            continue

        # Billable hours
        billable_seconds = sum(e["duration"] for e in entries if e["billable"])
        billable_hours = billable_seconds / 3600.0

        # Away-from-home hours (non-HomeOffice)
        away_seconds = 0
        for e in entries:
            tags = e["tags"]
            if "HomeOffice" not in tags:
                away_seconds += e["duration"]
        away_hours = away_seconds / 3600.0

        # Back home time (last commuting entry end time)
        commuting_entries = [e for e in entries if "Commuting" in e["tags"] and e["stop"]]
        commuting_entries.sort(key=lambda e: e["stop"])  # by end time
        if commuting_entries:
            last_commuting = commuting_entries[-1]
            back_home_minutes = _minutes_since_midnight(last_commuting["stop"])
            back_home_time = f"{back_home_minutes // 60:02d}:{back_home_minutes % 60:02d}"
        else:
            back_home_time = None

        # HomeOffice end time for pure HomeOffice days
        # Mirror rules from metrics_engine.js
        all_entries = []
        home_office_entries = []
        for e in entries:
            is_home = "HomeOffice" in e["tags"]
            all_entries.append({
                "start": e["start"],
                "stop": e["stop"],
                "is_home": is_home,
                "tags": e["tags"],
            })
            if is_home:
                home_office_entries.append({
                    "start": e["start"],
                    "stop": e["stop"],
                    "tags": e["tags"],
                })

        home_office_end_time = None
        if home_office_entries:
            all_entries.sort(key=lambda e: e["start"])
            home_office_entries.sort(key=lambda e: e["start"])

            last_entry_of_day = all_entries[-1]
            last_home = home_office_entries[-1]

            commuting_for_day = [e for e in all_entries if "Commuting" in e["tags"]]
            commuting_for_day.sort(key=lambda e: e["start"])
            last_commuting_any = commuting_for_day[-1] if commuting_for_day else None

            # Rule 1: If there's HomeOffice AFTER the last commuting entry, skip as pure HO day
            if last_commuting_any and last_home["start"] > last_commuting_any["stop"]:
                home_office_end_time = None
            else:
                # Rule 2: mixed day - non-HomeOffice entries after last HomeOffice
                entries_after_last_home = [
                    e for e in all_entries
                    if e["start"] > last_home["stop"] and not e["is_home"]
                ]
                if entries_after_last_home:
                    home_office_end_time = None
                else:
                    # Rule 3: overall last entry of day must be HomeOffice
                    if last_entry_of_day["is_home"]:
                        ho_minutes = _minutes_since_midnight(last_home["stop"])
                        home_office_end_time = f"{ho_minutes // 60:02d}:{ho_minutes % 60:02d}"

        # Late work flag
        late_work = False
        for e in entries:
            start = e["start"]
            stop = e["stop"]
            if start.hour >= 20 or (stop and stop.hour >= 20):
                late_work = True
                break

        day_record = {
            "date": date_str,
            "billable_hours": round(billable_hours, 2),
            "away_from_home_hours": round(away_hours, 2),
            "back_home_time": back_home_time,
            "home_office_end_time": home_office_end_time,
            "late_work": late_work,
            "total_entries": len(entries),
        }

        # Overwrite or insert this date
        existing_days[date_str] = day_record

    if not existing_days:
        # Nothing to write
        return

    # Rebuild history document
    all_dates = sorted(existing_days.keys())
    history = {
        "generated_at": datetime.now().isoformat(),
        "date_range": {
            "start": all_dates[0],
            "end": all_dates[-1],
        },
        "workspace_name": workspace_name,
        "daily_metrics": [existing_days[d] for d in all_dates],
    }

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"✅ Daily history updated at {history_path} with {len(all_dates)} days")


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

    def fetch_and_save_raw_data(self):
        """Fetch raw data, remove 'description' field, and save to JSON file"""
        print(f"🚀 Fetching raw Toggl data for workspace: {self.workspace_name}")
        
        # Get workspace ID
        workspace_id = self.get_workspace_id()
        print(f"📡 Found workspace ID: {workspace_id}")
        
        # Calculate date range (last 90 days, excluding today)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        start_date = end_date - timedelta(days=89)  # 90 days total including end_date
        
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        
        print(f"📅 Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (90 days, excluding today)")
        
        # Fetch time entries - RAW DATA ONLY
        # End date is yesterday to ensure complete day data
        time_entries = self.get_time_entries(start_date_str, end_date_str)
        print(f"📊 Retrieved {len(time_entries)} raw time entries")
        
        # Remove 'description' field from each entry if it exists
        for entry in time_entries:
            if "description" in entry:
                del entry["description"]
        
        # Store data with metadata
        raw_data = {
            "fetched_at": datetime.now().isoformat(),
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "days": 90
            },
            "workspace_name": self.workspace_name,
            "workspace_id": workspace_id,
            "total_entries": len(time_entries),
            "raw_entries": time_entries  # Raw data, with descriptions removed
        }
        
        # Ensure data directory exists
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Save short-term raw data (90 days) to JSON file
        output_file = data_dir / "raw_data.json"
        with open(output_file, 'w') as f:
            json.dump(raw_data, f, indent=2)

        print(f"✅ Raw data saved to {output_file}")
        print(f"💾 Total Entries: {len(time_entries)}")
        print(f"💾 Date Range: {raw_data['date_range']['start']} to {raw_data['date_range']['end']}")
        print(f"💾 'description' field removed from entries")

        # Update long-term daily aggregates for charts
        _update_history_daily(time_entries, self.workspace_name, data_dir)

def main():
    try:
        fetcher = TogglDataFetcher()
        fetcher.fetch_and_save_raw_data()
        print("🎉 Raw data fetch completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
