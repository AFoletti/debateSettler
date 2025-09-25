#!/usr/bin/env python3
"""
Test fixed enhanced KPI processing with existing raw data
"""

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

class TestFixedProcessing:
    def __init__(self):
        self.data_dir = Path("data")

    def parse_datetime(self, dt_str):
        """Parse datetime string with timezone handling"""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def time_to_decimal_hours(self, dt):
        """Convert datetime to decimal hours since midnight"""
        return dt.hour + dt.minute / 60.0

    def load_existing_raw_data(self):
        """Load existing raw data for testing"""
        raw_file = self.data_dir / "raw_data.json"
        with open(raw_file) as f:
            return json.load(f)

    def calculate_daily_kpis(self, raw_entries):
        """Calculate KPIs for each day from raw entries - FIXED VERSION"""
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
            
            # FIXED: Late work detection (ANY entry that starts OR ends after 20:00)
            if start_time.hour >= 20 or stop_time.hour >= 20:
                day_data['late_work_count'] = 1  # Flag that this day had late work
                print(f"🕘 Late work detected on {date_str}: {start_time.strftime('%H:%M')}-{stop_time.strftime('%H:%M')} (tags: {tags})")

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
            
            # Store daily KPI in FIXED simplified format
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
        """Aggregate daily KPIs into weekly data (calendar weeks) - FIXED VERSION"""
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
        
        # Calculate weekly aggregations in FIXED format
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

    def calculate_working_days_aggregations(self, daily_kpis):
        """Calculate rolling working days aggregations (5, 10, 30 working days) - FIXED VERSION"""
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
                
                # Same calculation logic as weekly 
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

    def test_fixed_processing(self):
        """Test the fixed processing logic"""
        print("🧪 Testing FIXED enhanced KPI processing...")
        
        # Load existing data
        raw_data = self.load_existing_raw_data()
        print(f"📊 Loaded {raw_data['total_entries']} raw entries from {raw_data['date_range']['start']} to {raw_data['date_range']['end']}")
        
        # Calculate daily KPIs with fixed logic
        daily_kpis = self.calculate_daily_kpis(raw_data['raw_entries'])
        
        # Show sample results
        print(f"\n📈 Calculated KPIs for {len(daily_kpis)} days")
        
        # Check for late work specifically
        late_work_days = [date for date, kpi in daily_kpis.items() if kpi['late_work_frequency']['count'] > 0]
        print(f"\n🕘 Days with late work: {len(late_work_days)}")
        for date in late_work_days:
            print(f"  - {date}: Late work detected")
        
        print("\n🔍 Sample daily KPI (most recent day):")
        latest_date = max(daily_kpis.keys())
        sample_kpi = daily_kpis[latest_date]
        print(f"Date: {latest_date}")
        print(f"Format: {json.dumps(sample_kpi, indent=2)}")
        
        # Test weekly aggregations
        weekly_kpis = self.aggregate_weekly_data(daily_kpis)
        print(f"\n📅 Weekly aggregations: {len(weekly_kpis)}")
        latest_week = max(weekly_kpis.keys())
        print(f"Latest week ({latest_week}): {json.dumps(weekly_kpis[latest_week], indent=2)}")
        
        # Test working days aggregations
        working_days_kpis = self.calculate_working_days_aggregations(daily_kpis)
        print(f"\n📈 Working days aggregations: {len(working_days_kpis)}")
        print(f"30WD: {json.dumps(working_days_kpis['30WD'], indent=2)}")
        
        # Save fixed results using final filenames
        self.data_dir.mkdir(exist_ok=True)
        
        with open(self.data_dir / "daily_kpis.json", 'w') as f:
            json.dump(daily_kpis, f, indent=2)
            
        with open(self.data_dir / "weekly_aggregations.json", 'w') as f:
            json.dump(weekly_kpis, f, indent=2)
            
        with open(self.data_dir / "working_days_aggregations.json", 'w') as f:
            json.dump(working_days_kpis, f, indent=2)
        
        print(f"\n✅ Fixed results saved with final filenames!")
        return daily_kpis, weekly_kpis, working_days_kpis

def main():
    tester = TestFixedProcessing()
    daily_kpis, weekly_kpis, working_days_kpis = tester.test_fixed_processing()
    print(f"🎉 Fixed test completed! Generated:")
    print(f"📊 Daily KPIs: {len(daily_kpis)}")
    print(f"📅 Weekly aggregations: {len(weekly_kpis)}")
    print(f"📈 Working days aggregations: {len(working_days_kpis)}")

if __name__ == "__main__":
    main()