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
        
        # Calculate date range (last 60 days, excluding today)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        start_date = end_date - timedelta(days=59)  # 60 days total including end_date
        
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        
        print(f"📅 Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (60 days, excluding today)")
        
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
                "days": 60
            },
            "workspace_name": self.workspace_name,
            "workspace_id": workspace_id,
            "total_entries": len(time_entries),
            "raw_entries": time_entries  # Raw data, with descriptions removed
        }
        
        # Ensure data directory exists
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Save data to JSON file
        output_file = data_dir / "raw_data.json"
        with open(output_file, 'w') as f:
            json.dump(raw_data, f, indent=2)
        
        print(f"✅ Raw data saved to {output_file}")
        print(f"💾 Total Entries: {len(time_entries)}")
        print(f"💾 Date Range: {raw_data['date_range']['start']} to {raw_data['date_range']['end']}")
        print(f"💾 'description' field removed from entries")

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
