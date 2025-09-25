#!/usr/bin/env python3
"""
Enhanced Toggl Track data fetcher with PROPER TIMEZONE HANDLING
Stores UTC data but calculates late work and displays times in Swiss local time (CET/CEST)
"""

import requests
import json
import os
import base64
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import pytz

class TimezoneFixedTogglDataFetcher:
    def __init__(self):
        self.api_token = os.getenv('TOGGL_API_TOKEN')
        self.workspace_name = os.getenv('TOGGL_WORKSPACE', 'DRE-P')
        self.base_url = "https://api.track.toggl.com/api/v9"
        
        # Swiss timezone
        self.swiss_tz = pytz.timezone('Europe/Zurich')
        
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

    def parse_datetime_utc(self, dt_str):
        """Parse datetime string and ensure it's UTC"""
        if not dt_str:
            return None
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.astimezone(pytz.UTC)

    def utc_to_swiss_time(self, utc_dt):
        """Convert UTC datetime to Swiss local time (handles CET/CEST automatically)"""
        return utc_dt.astimezone(self.swiss_tz)

    def swiss_time_to_decimal_hours(self, swiss_dt):
        """Convert Swiss local datetime to decimal hours since midnight"""
        return swiss_dt.hour + swiss_dt.minute / 60.0

    def calculate_daily_kpis(self, raw_entries):
        """Calculate KPIs for each day - TIMEZONE CORRECTED VERSION"""
        daily_data = defaultdict(lambda: {
            'entries': [],
            'billable_hours': 0,
            'away_from_home_hours': 0,
            'back_home_time_swiss': None,
            'home_office_end_time_swiss': None,
            'late_work_count': 0,
            'total_entries': 0,
            'working_day': False
        })

        print(f"Processing {len(raw_entries)} raw entries with Swiss timezone conversion...")

        # Group entries by date and calculate basic metrics
        for entry in raw_entries:
            start_time_utc = self.parse_datetime_utc(entry.get('start'))
            stop_time_utc = self.parse_datetime_utc(entry.get('stop'))
            
            if not start_time_utc or not stop_time_utc or entry.get('duration', 0) <= 0:
                continue
            
            # Convert to Swiss local time for date grouping and late work detection
            start_time_swiss = self.utc_to_swiss_time(start_time_utc)
            stop_time_swiss = self.utc_to_swiss_time(stop_time_utc)
            
            # Use Swiss date for grouping (important for entries crossing midnight)
            date_str = start_time_swiss.strftime('%Y-%m-%d')
            day_data = daily_data[date_str]
            day_data['entries'].append({
                'entry': entry,
                'start_utc': start_time_utc,
                'stop_utc': stop_time_utc,
                'start_swiss': start_time_swiss,
                'stop_swiss': stop_time_swiss
            })
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
            
            # FIXED: Late work detection using SWISS LOCAL TIME
            if start_time_swiss.hour >= 20 or stop_time_swiss.hour >= 20:
                day_data['late_work_count'] = 1  # Flag that this day had late work
                print(f"🕘 Late work detected on {date_str}: {start_time_swiss.strftime('%H:%M')}-{stop_time_swiss.strftime('%H:%M')} Swiss time (tags: {tags})")

        print(f"Found {len(daily_data)} working days")

        # Calculate complex metrics (back home times, home office end times)
        daily_kpis = {}
        
        for date_str, day_data in daily_data.items():
            if not day_data['working_day']:
                continue
                
            entry_data_list = day_data['entries']
            
            # Calculate back home time (only for days with commuting) - USE SWISS TIME
            commute_entries = [e for e in entry_data_list if 'Commuting' in e['entry'].get('tags', [])]
            if commute_entries:
                # Find last commuting entry end time in Swiss time
                last_commute = max(commute_entries, key=lambda x: x['stop_swiss'])
                day_data['back_home_time_swiss'] = self.swiss_time_to_decimal_hours(last_commute['stop_swiss'])
                print(f"📍 {date_str}: Back home at {last_commute['stop_swiss'].strftime('%H:%M')} Swiss time ({last_commute['stop_utc'].strftime('%H:%M')} UTC)")
            
            # Calculate home office end time (only for pure home office days) - USE SWISS TIME  
            home_office_entries = [e for e in entry_data_list if 'HomeOffice' in e['entry'].get('tags', [])]
            non_home_entries = [e for e in entry_data_list if 'HomeOffice' not in e['entry'].get('tags', []) and 'Commuting' not in e['entry'].get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                # Pure home office day - find last home office entry in Swiss time
                last_home_entry = max(home_office_entries, key=lambda x: x['stop_swiss'])
                day_data['home_office_end_time_swiss'] = self.swiss_time_to_decimal_hours(last_home_entry['stop_swiss'])
                print(f"🏠 {date_str}: Home office ended at {last_home_entry['stop_swiss'].strftime('%H:%M')} Swiss time")
            
            # Store daily KPI with Swiss local times
            daily_kpis[date_str] = {
                'billable_hours': {
                    'sum': round(day_data['billable_hours'], 2)
                },
                'away_from_home_hours': {
                    'sum': round(day_data['away_from_home_hours'], 2)
                },
                'back_home_times': {
                    'time': round(day_data['back_home_time_swiss'], 2) if day_data['back_home_time_swiss'] else None
                },
                'home_office_end_times': {
                    'time': round(day_data['home_office_end_time_swiss'], 2) if day_data['home_office_end_time_swiss'] else None
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
            
            # Aggregate metrics (times are already in Swiss local time)
            if kpis['billable_hours']['sum'] > 0:
                week_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            if kpis['away_from_home_hours']['sum'] > 0:
                week_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            if kpis['back_home_times']['time']:
                week_data['back_home_times'].append(kpis['back_home_times']['time'])
                
            if kpis['home_office_end_times']['time']:
                week_data['home_office_end_times'].append(kpis['home_office_end_times']['time'])
                
            # Late work frequency (count days with late work)
            if kpis['late_work_frequency']['count'] > 0:
                week_data['late_work_days'] += 1
        
        # Calculate weekly aggregations
        weekly_kpis = {}
        for week, data in weekly_data.items():
            result = {
                'working_days': data['total_working_days'],
                'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
                'week': week
            }
            
            # Billable hours
            if data['billable_hours']:
                result['billable_hours'] = {
                    'sum': round(sum(data['billable_hours']), 2),
                    'mean': round(statistics.mean(data['billable_hours']), 2),
                    'median': round(statistics.median(data['billable_hours']), 2)
                }
            else:
                result['billable_hours'] = {'sum': 0}
                
            # Away from home hours
            if data['away_from_home_hours']:
                result['away_from_home_hours'] = {
                    'mean': round(statistics.mean(data['away_from_home_hours']), 2),
                    'median': round(statistics.median(data['away_from_home_hours']), 2)
                }
            
            # Back home times (already in Swiss local time)
            if data['back_home_times']:
                result['back_home_times'] = {
                    'mean': round(statistics.mean(data['back_home_times']), 2),
                    'median': round(statistics.median(data['back_home_times']), 2),
                    'earliest': round(min(data['back_home_times']), 2),
                    'latest': round(max(data['back_home_times']), 2)
                }
                
            # Home office end times (already in Swiss local time)
            if data['home_office_end_times']:
                result['home_office_end_times'] = {
                    'mean': round(statistics.mean(data['home_office_end_times']), 2),
                    'median': round(statistics.median(data['home_office_end_times']), 2),
                    'earliest': round(min(data['home_office_end_times']), 2),
                    'latest': round(max(data['home_office_end_times']), 2)
                }
                
            # Late work frequency
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
        
        # Calculate monthly aggregations
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
        sorted_dates = sorted(daily_kpis.keys(), reverse=True)
        
        working_days_aggregations = {}
        
        for period in [5, 10, 30]:
            if len(sorted_dates) >= period:
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
                    'date_range': {'start': max(period_dates), 'end': min(period_dates)},
                    'period': f"{period}WD"
                }
                
                # Same calculation logic
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
        
        files_to_load = [
            ('daily_kpis', 'daily_kpis.json'),
            ('weekly_aggregations', 'weekly_aggregations.json'),
            ('monthly_aggregations', 'monthly_aggregations.json'),
            ('working_days_aggregations', 'working_days_aggregations.json')
        ]
        
        for key, filename in files_to_load:
            file_path = data_dir / filename
            if file_path.exists():
                with open(file_path) as f:
                    existing_data[key] = json.load(f)
        
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
        
        # Save updated data
        files_to_save = [
            (existing['daily_kpis'], 'daily_kpis.json'),
            (existing['weekly_aggregations'], 'weekly_aggregations.json'),
            (existing['monthly_aggregations'], 'monthly_aggregations.json'),
            (existing['working_days_aggregations'], 'working_days_aggregations.json')
        ]
        
        for data, filename in files_to_save:
            with open(data_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
        
        return existing

    def fetch_and_process_data(self):
        """Main method: fetch raw data and process all aggregations with timezone fixes"""
        print(f"🚀 TIMEZONE-FIXED Toggl data processing for workspace: {self.workspace_name}")
        print(f"🕐 Using timezone: Europe/Zurich (CET/CEST)")
        
        # Get workspace ID
        workspace_id = self.get_workspace_id()
        print(f"📡 Found workspace ID: {workspace_id}")
        
        # Calculate date range (last 6 months, excluding today)
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        start_date = end_date - timedelta(days=180)
        
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
            "raw_entries": time_entries,
            "timezone_info": {
                "storage": "UTC",
                "display": "Europe/Zurich (CET/CEST)",
                "late_work_threshold": "20:00 local time"
            }
        }
        
        with open(data_dir / "raw_data.json", 'w') as f:
            json.dump(raw_data, f, indent=2)
        
        print(f"✅ Raw data saved (6 months, {len(time_entries)} entries)")
        
        # Calculate daily KPIs with timezone fixes
        print("🧮 Calculating daily KPIs with Swiss timezone conversion...")
        daily_kpis = self.calculate_daily_kpis(time_entries)
        print(f"📈 Processed {len(daily_kpis)} working days")
        
        # Calculate aggregations
        print("📅 Calculating weekly aggregations...")
        weekly_kpis = self.aggregate_weekly_data(daily_kpis)
        print(f"📊 Processed {len(weekly_kpis)} weeks")
        
        print("📆 Calculating monthly aggregations...")
        monthly_kpis = self.aggregate_monthly_data(daily_kpis)
        print(f"📋 Processed {len(monthly_kpis)} months")
        
        print("📈 Calculating working days aggregations...")
        working_days_kpis = self.calculate_working_days_aggregations(daily_kpis)
        print(f"📊 Processed {len(working_days_kpis)} working day periods")
        
        # Save all aggregated data
        print("💾 Saving timezone-corrected aggregated data...")
        saved_data = self.save_aggregated_data(daily_kpis, weekly_kpis, monthly_kpis, working_days_kpis)
        
        print(f"🎉 TIMEZONE-FIXED processing completed!")
        print(f"📊 Total daily KPIs: {len(saved_data['daily_kpis'])}")
        print(f"📅 Total weekly aggregations: {len(saved_data['weekly_aggregations'])}")
        print(f"📆 Total monthly aggregations: {len(saved_data['monthly_aggregations'])}")
        print(f"📈 Total working days aggregations: {len(saved_data['working_days_aggregations'])}")

def main():
    try:
        fetcher = TimezoneFixedTogglDataFetcher()
        fetcher.fetch_and_process_data()
        print("🎉 Timezone-fixed enhanced data fetch completed successfully!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()