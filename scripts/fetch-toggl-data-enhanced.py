#!/usr/bin/env python3
"""
Enhanced Toggl Track data fetcher with KPI calculation and aggregation
This script runs daily via GitHub Actions and:
1. Fetches 6 months of raw data (overwrites previous)
2. Calculates daily KPIs and stores them persistently 
3. Builds weekly, monthly, and working days aggregations
"""

import requests
import json
import os
import base64
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

class EnhancedTogglDataFetcher:
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

    def parse_datetime(self, dt_str):
        """Parse datetime string with timezone handling"""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def minutes_to_decimal_hours(self, minutes):
        """Convert minutes to decimal hours"""
        return round(minutes / 60, 2)

    def time_to_minutes(self, dt):
        """Convert datetime to minutes since midnight"""
        return dt.hour * 60 + dt.minute

    def calculate_stats(self, values):
        """Calculate sum, mean, median, earliest, latest for a list of values"""
        if not values:
            return {"sum": None, "mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        # For time values (minutes since midnight), convert back to decimal hours for some stats
        if all(isinstance(v, (int, float)) for v in values):
            return {
                "sum": round(sum(values), 2),
                "mean": round(statistics.mean(values), 2),
                "median": round(statistics.median(values), 2),
                "earliest": round(min(values), 2),
                "latest": round(max(values), 2),
                "count": len(values)
            }
        return {"sum": None, "mean": None, "median": None, "earliest": None, "latest": None, "count": 0}

    def calculate_time_stats(self, time_values):
        """Calculate stats for time values (minutes since midnight)"""
        if not time_values:
            return {"sum": None, "mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        return {
            "sum": None,  # Sum doesn't make sense for times
            "mean": round(statistics.mean(time_values) / 60, 2),  # Convert to decimal hours
            "median": round(statistics.median(time_values) / 60, 2),
            "earliest": round(min(time_values) / 60, 2),
            "latest": round(max(time_values) / 60, 2),
            "count": len(time_values)
        }

    def calculate_daily_kpis(self, raw_entries):
        """Calculate KPIs for each day from raw entries"""
        daily_data = defaultdict(lambda: {
            'entries': [],
            'billable_hours': 0,
            'away_from_home_hours': 0,
            'back_home_times': [],
            'home_office_end_times': [],
            'late_work_entries': 0,
            'total_entries': 0,
            'working_day': False
        })

        # Group entries by date and calculate basic metrics
        for entry in raw_entries:
            start_time = self.parse_datetime(entry.get('start'))
            stop_time = self.parse_datetime(entry.get('stop'))
            
            if not start_time or not stop_time or entry.get('duration', 0) <= 0:
                continue
                
            date_str = start_time.strftime('%Y-%m-%d')
            day_data = daily_data[date_str]
            day_data['entries'].append(entry)
            day_data['total_entries'] += 1
            day_data['working_day'] = True
            
            duration_hours = entry.get('duration', 0) / 3600
            tags = entry.get('tags', [])
            
            # Billable hours
            if entry.get('billable', False):
                day_data['billable_hours'] += duration_hours
            
            # Away from home hours (not HomeOffice)
            if 'HomeOffice' not in tags:
                day_data['away_from_home_hours'] += duration_hours
            
            # Late work detection (starts or ends after 20:00)
            if start_time.hour >= 20 or stop_time.hour >= 20:
                day_data['late_work_entries'] += 1

        # Calculate complex metrics (back home times, home office end times)
        daily_kpis = {}
        
        for date_str, day_data in daily_data.items():
            if not day_data['working_day']:
                continue
                
            entries = day_data['entries']
            
            # Calculate back home times (only for days with commuting)
            commute_entries = [e for e in entries if 'Commuting' in e.get('tags', [])]
            if commute_entries:
                # Find last commuting entry end time
                last_commute = max(commute_entries, key=lambda x: self.parse_datetime(x['stop']))
                back_home_time = self.parse_datetime(last_commute['stop'])
                day_data['back_home_times'].append(self.time_to_minutes(back_home_time))
            
            # Calculate home office end times (only for pure home office days)
            home_office_entries = [e for e in entries if 'HomeOffice' in e.get('tags', [])]
            non_home_entries = [e for e in entries if 'HomeOffice' not in e.get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                # Pure home office day - find last home office entry
                last_home_entry = max(home_office_entries, key=lambda x: self.parse_datetime(x['stop']))
                home_end_time = self.parse_datetime(last_home_entry['stop'])
                day_data['home_office_end_times'].append(self.time_to_minutes(home_end_time))
            
            # Store daily KPI
            daily_kpis[date_str] = {
                'billable_hours': self.calculate_stats([day_data['billable_hours']]),
                'away_from_home_hours': self.calculate_stats([day_data['away_from_home_hours']]),
                'back_home_times': self.calculate_time_stats(day_data['back_home_times']),
                'home_office_end_times': self.calculate_time_stats(day_data['home_office_end_times']),
                'late_work_frequency': {
                    "sum": day_data['late_work_entries'], 
                    "mean": day_data['late_work_entries'], 
                    "median": day_data['late_work_entries'],
                    "earliest": day_data['late_work_entries'], 
                    "latest": day_data['late_work_entries'], 
                    "count": 1 if day_data['late_work_entries'] > 0 else 0
                },
                'working_day': True,
                'total_entries': day_data['total_entries'],
                'date': date_str
            }
            
        return daily_kpis

    def aggregate_weekly_data(self, daily_kpis):
        """Aggregate daily KPIs into weekly data (calendar weeks)"""
        weekly_data = defaultdict(lambda: {
            'billable_hours': [],
            'away_from_home_hours': [],
            'back_home_times': [],
            'home_office_end_times': [],
            'late_work_days': 0,
            'total_working_days': 0,
            'dates': []
        })
        
        for date_str, kpis in daily_kpis.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            year_week = f"{date_obj.year}-W{date_obj.isocalendar()[1]:02d}"
            
            week_data = weekly_data[year_week]
            week_data['dates'].append(date_str)
            week_data['total_working_days'] += 1
            
            # Aggregate billable hours
            if kpis['billable_hours']['sum']:
                week_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            # Aggregate away from home hours  
            if kpis['away_from_home_hours']['sum']:
                week_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            # Aggregate back home times
            if kpis['back_home_times']['mean']:
                week_data['back_home_times'].append(kpis['back_home_times']['mean'])
                
            # Aggregate home office end times
            if kpis['home_office_end_times']['mean']:
                week_data['home_office_end_times'].append(kpis['home_office_end_times']['mean'])
                
            # Late work frequency
            if kpis['late_work_frequency']['count'] > 0:
                week_data['late_work_days'] += 1
        
        # Calculate weekly aggregations
        weekly_kpis = {}
        for week, data in weekly_data.items():
            weekly_kpis[week] = {
                'billable_hours': self.calculate_stats(data['billable_hours']),
                'away_from_home_hours': self.calculate_stats(data['away_from_home_hours']),
                'back_home_times': self.calculate_stats(data['back_home_times']), 
                'home_office_end_times': self.calculate_stats(data['home_office_end_times']),
                'late_work_frequency': {
                    "sum": data['late_work_days'],
                    "mean": round(data['late_work_days'] / data['total_working_days'] * 100, 1) if data['total_working_days'] > 0 else 0,
                    "median": data['late_work_days'],
                    "earliest": data['late_work_days'],
                    "latest": data['late_work_days'],
                    "count": data['total_working_days']
                },
                'working_days': data['total_working_days'],
                'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
                'week': week
            }
            
        return weekly_kpis

    def aggregate_monthly_data(self, daily_kpis):
        """Aggregate daily KPIs into monthly data"""
        monthly_data = defaultdict(lambda: {
            'billable_hours': [],
            'away_from_home_hours': [],
            'back_home_times': [],
            'home_office_end_times': [],
            'late_work_days': 0,
            'total_working_days': 0,
            'dates': []
        })
        
        for date_str, kpis in daily_kpis.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            year_month = f"{date_obj.year}-{date_obj.month:02d}"
            
            month_data = monthly_data[year_month]
            month_data['dates'].append(date_str)
            month_data['total_working_days'] += 1
            
            # Same aggregation logic as weekly
            if kpis['billable_hours']['sum']:
                month_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            if kpis['away_from_home_hours']['sum']:
                month_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            if kpis['back_home_times']['mean']:
                month_data['back_home_times'].append(kpis['back_home_times']['mean'])
                
            if kpis['home_office_end_times']['mean']:
                month_data['home_office_end_times'].append(kpis['home_office_end_times']['mean'])
                
            if kpis['late_work_frequency']['count'] > 0:
                month_data['late_work_days'] += 1
        
        # Calculate monthly aggregations
        monthly_kpis = {}
        for month, data in monthly_data.items():
            monthly_kpis[month] = {
                'billable_hours': self.calculate_stats(data['billable_hours']),
                'away_from_home_hours': self.calculate_stats(data['away_from_home_hours']),
                'back_home_times': self.calculate_stats(data['back_home_times']),
                'home_office_end_times': self.calculate_stats(data['home_office_end_times']),
                'late_work_frequency': {
                    "sum": data['late_work_days'],
                    "mean": round(data['late_work_days'] / data['total_working_days'] * 100, 1) if data['total_working_days'] > 0 else 0,
                    "median": data['late_work_days'],
                    "earliest": data['late_work_days'], 
                    "latest": data['late_work_days'],
                    "count": data['total_working_days']
                },
                'working_days': data['total_working_days'],
                'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
                'month': month
            }
            
        return monthly_kpis

    def load_existing_aggregated_data(self):
        """Load existing aggregated data files"""
        data_dir = Path("data")
        
        existing_data = {
            'daily_kpis': {},
            'weekly_aggregations': {},
            'monthly_aggregations': {}
        }
        
        # Load daily KPIs
        daily_file = data_dir / "daily_kpis.json"
        if daily_file.exists():
            with open(daily_file) as f:
                existing_data['daily_kpis'] = json.load(f)
        
        # Load weekly aggregations
        weekly_file = data_dir / "weekly_aggregations.json" 
        if weekly_file.exists():
            with open(weekly_file) as f:
                existing_data['weekly_aggregations'] = json.load(f)
                
        # Load monthly aggregations
        monthly_file = data_dir / "monthly_aggregations.json"
        if monthly_file.exists():
            with open(monthly_file) as f:
                existing_data['monthly_aggregations'] = json.load(f)
        
        return existing_data

    def save_aggregated_data(self, daily_kpis, weekly_kpis, monthly_kpis):
        """Save aggregated data to persistent files"""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Load existing data
        existing = self.load_existing_aggregated_data()
        
        # Merge with new data (new data overwrites existing for same dates)
        existing['daily_kpis'].update(daily_kpis)
        existing['weekly_aggregations'].update(weekly_kpis)
        existing['monthly_aggregations'].update(monthly_kpis)
        
        # Save updated data
        with open(data_dir / "daily_kpis.json", 'w') as f:
            json.dump(existing['daily_kpis'], f, indent=2)
            
        with open(data_dir / "weekly_aggregations.json", 'w') as f:
            json.dump(existing['weekly_aggregations'], f, indent=2)
            
        with open(data_dir / "monthly_aggregations.json", 'w') as f:
            json.dump(existing['monthly_aggregations'], f, indent=2)
        
        return existing

    def fetch_and_process_data(self):
        """Main method: fetch raw data and process all aggregations"""
        print(f"🚀 Enhanced Toggl data processing for workspace: {self.workspace_name}")
        
        # Get workspace ID
        workspace_id = self.get_workspace_id()
        print(f"📡 Found workspace ID: {workspace_id}")
        
        # Calculate date range (last 6 months, excluding today)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        start_date = end_date - timedelta(days=180)  # Approximately 6 months
        
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59.999Z")
        
        print(f"📅 Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (6 months)")
        
        # Fetch time entries
        time_entries = self.get_time_entries(start_date_str, end_date_str)
        print(f"📊 Retrieved {len(time_entries)} raw time entries")
        
        # Remove 'description' field
        for entry in time_entries:
            if "description" in entry:
                del entry["description"]
        
        # Save raw data (overwrites previous)
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        raw_data = {
            "fetched_at": datetime.now().isoformat(),
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d"),
                "days": 180
            },
            "workspace_name": self.workspace_name,
            "workspace_id": workspace_id,
            "total_entries": len(time_entries),
            "raw_entries": time_entries
        }
        
        with open(data_dir / "raw_data.json", 'w') as f:
            json.dump(raw_data, f, indent=2)
        
        print(f"✅ Raw data saved (6 months, {len(time_entries)} entries)")
        
        # Calculate daily KPIs
        print("🧮 Calculating daily KPIs...")
        daily_kpis = self.calculate_daily_kpis(time_entries)
        print(f"📈 Processed {len(daily_kpis)} working days")
        
        # Calculate weekly aggregations
        print("📅 Calculating weekly aggregations...")
        weekly_kpis = self.aggregate_weekly_data(daily_kpis)
        print(f"📊 Processed {len(weekly_kpis)} weeks")
        
        # Calculate monthly aggregations  
        print("📆 Calculating monthly aggregations...")
        monthly_kpis = self.aggregate_monthly_data(daily_kpis)
        print(f"📋 Processed {len(monthly_kpis)} months")
        
        # Save all aggregated data (preserves historical data)
        print("💾 Saving aggregated data...")
        saved_data = self.save_aggregated_data(daily_kpis, weekly_kpis, monthly_kpis)
        
        print(f"🎉 Enhanced processing completed!")
        print(f"📊 Total daily KPIs: {len(saved_data['daily_kpis'])}")
        print(f"📅 Total weekly aggregations: {len(saved_data['weekly_aggregations'])}")  
        print(f"📆 Total monthly aggregations: {len(saved_data['monthly_aggregations'])}")

def main():
    try:
        fetcher = EnhancedTogglDataFetcher()
        fetcher.fetch_and_process_data()
        print("🎉 Enhanced data fetch completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()