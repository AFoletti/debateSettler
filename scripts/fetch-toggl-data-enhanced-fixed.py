#!/usr/bin/env python3
"""
Enhanced Toggl Track data fetcher with KPI calculation and aggregation
FIXED VERSION - Corrected data structures and logic
"""

import requests
import json
import os
import base64
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

class FixedEnhancedTogglDataFetcher:
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

    def time_to_decimal_hours(self, dt):
        """Convert datetime to decimal hours since midnight"""
        return dt.hour + dt.minute / 60.0

    def calculate_daily_kpis(self, raw_entries):
        """Calculate KPIs for each day from raw entries"""
        daily_data = defaultdict(lambda: {
            'entries': [],
            'billable_hours': 0,
            'away_from_home_hours': 0,
            'back_home_time': None,
            'home_office_end_time': None,
            'late_work_count': 0,
            'total_entries': 0,
            'working_day': False
        })

        print(f"Processing {len(raw_entries)} raw entries...")

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
            
            # Late work detection (ANY entry that starts OR ends after 20:00)
            if start_time.hour >= 20 or stop_time.hour >= 20:
                day_data['late_work_count'] = 1  # Flag that this day had late work

        print(f"Found {len(daily_data)} working days")

        # Calculate complex metrics (back home times, home office end times)
        daily_kpis = {}
        
        for date_str, day_data in daily_data.items():
            if not day_data['working_day']:
                continue
                
            entries = day_data['entries']
            
            # Calculate back home time (only for days with commuting)
            commute_entries = [e for e in entries if 'Commuting' in e.get('tags', [])]
            if commute_entries:
                # Find last commuting entry end time
                last_commute = max(commute_entries, key=lambda x: self.parse_datetime(x['stop']))
                back_home_time = self.parse_datetime(last_commute['stop'])
                day_data['back_home_time'] = self.time_to_decimal_hours(back_home_time)
            
            # Calculate home office end time (only for pure home office days)
            home_office_entries = [e for e in entries if 'HomeOffice' in e.get('tags', [])]
            non_home_entries = [e for e in entries if 'HomeOffice' not in e.get('tags', []) and 'Commuting' not in e.get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                # Pure home office day - find last home office entry
                last_home_entry = max(home_office_entries, key=lambda x: self.parse_datetime(x['stop']))
                home_end_time = self.parse_datetime(last_home_entry['stop'])
                day_data['home_office_end_time'] = self.time_to_decimal_hours(home_end_time)
            
            # Store daily KPI in simplified format
            daily_kpis[date_str] = {
                'billable_hours': {
                    'sum': round(day_data['billable_hours'], 2)
                },
                'away_from_home_hours': {
                    'sum': round(day_data['away_from_home_hours'], 2)
                },
                'back_home_times': {
                    'time': round(day_data['back_home_time'], 2) if day_data['back_home_time'] else None
                },
                'home_office_end_times': {
                    'time': round(day_data['home_office_end_time'], 2) if day_data['home_office_end_time'] else None
                },
                'late_work_frequency': {
                    'count': day_data['late_work_count']
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
            
            # Aggregate billable hours (sum for calculation)
            if kpis['billable_hours']['sum'] > 0:
                week_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            # Aggregate away from home hours (for mean/median)
            if kpis['away_from_home_hours']['sum'] > 0:
                week_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            # Aggregate back home times (for statistics)
            if kpis['back_home_times']['time']:
                week_data['back_home_times'].append(kpis['back_home_times']['time'])
                
            # Aggregate home office end times (for statistics)
            if kpis['home_office_end_times']['time']:
                week_data['home_office_end_times'].append(kpis['home_office_end_times']['time'])
                
            # Late work frequency (count days with late work)
            if kpis['late_work_frequency']['count'] > 0:
                week_data['late_work_days'] += 1
        
        # Calculate weekly aggregations in correct format
        weekly_kpis = {}
        for week, data in weekly_data.items():
            result = {
                'working_days': data['total_working_days'],
                'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
                'week': week
            }
            
            # Billable hours - sum, mean, median
            if data['billable_hours']:
                result['billable_hours'] = {
                    'sum': round(sum(data['billable_hours']), 2),
                    'mean': round(statistics.mean(data['billable_hours']), 2),
                    'median': round(statistics.median(data['billable_hours']), 2)
                }
            else:
                result['billable_hours'] = {'sum': 0}
                
            # Away from home hours - mean, median (daily averages)
            if data['away_from_home_hours']:
                result['away_from_home_hours'] = {
                    'mean': round(statistics.mean(data['away_from_home_hours']), 2),
                    'median': round(statistics.median(data['away_from_home_hours']), 2)
                }
            
            # Back home times - mean, median, earliest, latest
            if data['back_home_times']:
                result['back_home_times'] = {
                    'mean': round(statistics.mean(data['back_home_times']), 2),
                    'median': round(statistics.median(data['back_home_times']), 2),
                    'earliest': round(min(data['back_home_times']), 2),
                    'latest': round(max(data['back_home_times']), 2)
                }
                
            # Home office end times - mean, median, earliest, latest  
            if data['home_office_end_times']:
                result['home_office_end_times'] = {
                    'mean': round(statistics.mean(data['home_office_end_times']), 2),
                    'median': round(statistics.median(data['home_office_end_times']), 2),
                    'earliest': round(min(data['home_office_end_times']), 2),
                    'latest': round(max(data['home_office_end_times']), 2)
                }
                
            # Late work frequency - count of days
            result['late_work_frequency'] = {
                'count': data['late_work_days']
            }
            
            weekly_kpis[week] = result
            
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
            if kpis['billable_hours']['sum'] > 0:
                month_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            if kpis['away_from_home_hours']['sum'] > 0:
                month_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            if kpis['back_home_times']['time']:
                month_data['back_home_times'].append(kpis['back_home_times']['time'])
                
            if kpis['home_office_end_times']['time']:
                month_data['home_office_end_times'].append(kpis['home_office_end_times']['time'])
                
            if kpis['late_work_frequency']['count'] > 0:
                month_data['late_work_days'] += 1
        
        # Calculate monthly aggregations in correct format
        monthly_kpis = {}
        for month, data in monthly_data.items():
            result = {
                'working_days': data['total_working_days'],
                'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
                'month': month
            }
            
            # Same calculation logic as weekly
            if data['billable_hours']:
                result['billable_hours'] = {
                    'sum': round(sum(data['billable_hours']), 2)
                }
            else:
                result['billable_hours'] = {'sum': 0}
                
            if data['away_from_home_hours']:
                result['away_from_home_hours'] = {
                    'mean': round(statistics.mean(data['away_from_home_hours']), 2),
                    'median': round(statistics.median(data['away_from_home_hours']), 2)
                }
            
            if data['back_home_times']:
                result['back_home_times'] = {
                    'mean': round(statistics.mean(data['back_home_times']), 2),
                    'median': round(statistics.median(data['back_home_times']), 2),
                    'earliest': round(min(data['back_home_times']), 2),
                    'latest': round(max(data['back_home_times']), 2)
                }
                
            if data['home_office_end_times']:
                result['home_office_end_times'] = {
                    'mean': round(statistics.mean(data['home_office_end_times']), 2),
                    'median': round(statistics.median(data['home_office_end_times']), 2),
                    'earliest': round(min(data['home_office_end_times']), 2),
                    'latest': round(max(data['home_office_end_times']), 2)
                }
                
            result['late_work_frequency'] = {
                'count': data['late_work_days']
            }
            
            monthly_kpis[month] = result
            
        return monthly_kpis

    def calculate_working_days_aggregations(self, daily_kpis):
        """Calculate rolling working days aggregations (5, 10, 30 working days)"""
        # Sort dates to get most recent working days
        sorted_dates = sorted(daily_kpis.keys(), reverse=True)
        
        working_days_aggregations = {}
        
        for period in [5, 10, 30]:
            if len(sorted_dates) >= period:
                # Get the last N working days
                period_dates = sorted_dates[:period]
                period_data = {
                    'billable_hours': [],
                    'away_from_home_hours': [],
                    'back_home_times': [],
                    'home_office_end_times': [],
                    'late_work_days': 0,
                    'total_working_days': 0,
                    'dates': period_dates
                }
                
                for date_str in period_dates:
                    kpis = daily_kpis[date_str]
                    period_data['total_working_days'] += 1
                    
                    if kpis['billable_hours']['sum'] > 0:
                        period_data['billable_hours'].append(kpis['billable_hours']['sum'])
                    
                    if kpis['away_from_home_hours']['sum'] > 0:
                        period_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                        
                    if kpis['back_home_times']['time']:
                        period_data['back_home_times'].append(kpis['back_home_times']['time'])
                        
                    if kpis['home_office_end_times']['time']:
                        period_data['home_office_end_times'].append(kpis['home_office_end_times']['time'])
                        
                    if kpis['late_work_frequency']['count'] > 0:
                        period_data['late_work_days'] += 1
                
                result = {
                    'working_days': period_data['total_working_days'],
                    'date_range': {'start': max(period_dates), 'end': min(period_dates)},  # Most recent first
                    'period': f"{period}WD"
                }
                
                # Same calculation logic as monthly
                if period_data['billable_hours']:
                    result['billable_hours'] = {
                        'sum': round(sum(period_data['billable_hours']), 2)
                    }
                else:
                    result['billable_hours'] = {'sum': 0}
                    
                if period_data['away_from_home_hours']:
                    result['away_from_home_hours'] = {
                        'mean': round(statistics.mean(period_data['away_from_home_hours']), 2),
                        'median': round(statistics.median(period_data['away_from_home_hours']), 2)
                    }
                
                if period_data['back_home_times']:
                    result['back_home_times'] = {
                        'mean': round(statistics.mean(period_data['back_home_times']), 2),
                        'median': round(statistics.median(period_data['back_home_times']), 2),
                        'earliest': round(min(period_data['back_home_times']), 2),
                        'latest': round(max(period_data['back_home_times']), 2)
                    }
                    
                if period_data['home_office_end_times']:
                    result['home_office_end_times'] = {
                        'mean': round(statistics.mean(period_data['home_office_end_times']), 2),
                        'median': round(statistics.median(period_data['home_office_end_times']), 2),
                        'earliest': round(min(period_data['home_office_end_times']), 2),
                        'latest': round(max(period_data['home_office_end_times']), 2)
                    }
                    
                result['late_work_frequency'] = {
                    'count': period_data['late_work_days']
                }
                
                working_days_aggregations[f"{period}WD"] = result
        
        return working_days_aggregations

    def load_existing_aggregated_data(self):
        """Load existing aggregated data files"""
        data_dir = Path("data")
        
        existing_data = {
            'daily_kpis': {},
            'weekly_aggregations': {},
            'monthly_aggregations': {},
            'working_days_aggregations': {}
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
                
        # Load working days aggregations
        wd_file = data_dir / "working_days_aggregations.json"
        if wd_file.exists():
            with open(wd_file) as f:
                existing_data['working_days_aggregations'] = json.load(f)
        
        return existing_data

    def save_aggregated_data(self, daily_kpis, weekly_kpis, monthly_kpis, working_days_kpis):
        """Save aggregated data to persistent files"""
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Load existing data
        existing = self.load_existing_aggregated_data()
        
        # Merge with new data (new data overwrites existing for same dates/periods)
        existing['daily_kpis'].update(daily_kpis)
        existing['weekly_aggregations'].update(weekly_kpis)
        existing['monthly_aggregations'].update(monthly_kpis)
        existing['working_days_aggregations'].update(working_days_kpis)
        
        # Save updated data with final filenames
        with open(data_dir / "daily_kpis.json", 'w') as f:
            json.dump(existing['daily_kpis'], f, indent=2)
            
        with open(data_dir / "weekly_aggregations.json", 'w') as f:
            json.dump(existing['weekly_aggregations'], f, indent=2)
            
        with open(data_dir / "monthly_aggregations.json", 'w') as f:
            json.dump(existing['monthly_aggregations'], f, indent=2)
            
        with open(data_dir / "working_days_aggregations.json", 'w') as f:
            json.dump(existing['working_days_aggregations'], f, indent=2)
        
        return existing

    def fetch_and_process_data(self):
        """Main method: fetch raw data and process all aggregations"""
        print(f"🚀 Enhanced Toggl data processing (FIXED) for workspace: {self.workspace_name}")
        
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
        
        # Calculate working days aggregations
        print("📈 Calculating working days aggregations...")
        working_days_kpis = self.calculate_working_days_aggregations(daily_kpis)
        print(f"📊 Processed {len(working_days_kpis)} working day periods")
        
        # Save all aggregated data (preserves historical data)
        print("💾 Saving aggregated data...")
        saved_data = self.save_aggregated_data(daily_kpis, weekly_kpis, monthly_kpis, working_days_kpis)
        
        print(f"🎉 Enhanced processing completed!")
        print(f"📊 Total daily KPIs: {len(saved_data['daily_kpis'])}")
        print(f"📅 Total weekly aggregations: {len(saved_data['weekly_aggregations'])}")  
        print(f"📆 Total monthly aggregations: {len(saved_data['monthly_aggregations'])}")
        print(f"📈 Total working days aggregations: {len(saved_data['working_days_aggregations'])}")

def main():
    try:
        fetcher = FixedEnhancedTogglDataFetcher()
        fetcher.fetch_and_process_data()
        print("🎉 Fixed enhanced data fetch completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()