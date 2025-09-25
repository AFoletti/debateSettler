#!/usr/bin/env python3
"""
Generate final production data with HH:MM time format
Clean up all test files and create production-ready data
"""

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import pytz

class FinalProductionDataGenerator:
    def __init__(self):
        self.data_dir = Path("data")
        self.swiss_tz = pytz.timezone('Europe/Zurich')

    def decimal_hours_to_time(self, decimal_hours):
        """Convert decimal hours to HH:MM format"""
        if decimal_hours is None:
            return None
        
        hours = int(decimal_hours)
        minutes = int((decimal_hours - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    def parse_datetime_utc(self, dt_str):
        """Parse datetime string and ensure it's UTC"""
        if not dt_str:
            return None
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.astimezone(pytz.UTC)

    def utc_to_swiss_time(self, utc_dt):
        """Convert UTC datetime to Swiss local time"""
        return utc_dt.astimezone(self.swiss_tz)

    def swiss_time_to_time_string(self, swiss_dt):
        """Convert Swiss local datetime to HH:MM format"""
        return swiss_dt.strftime('%H:%M')

    def load_raw_data(self):
        """Load existing raw data"""
        raw_file = self.data_dir / "raw_data.json"
        with open(raw_file) as f:
            return json.load(f)

    def calculate_final_daily_kpis(self, raw_entries):
        """Calculate daily KPIs with HH:MM time format"""
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

        print(f"🧮 Processing {len(raw_entries)} entries for final production data...")

        # Process entries with timezone conversion
        for entry in raw_entries:
            start_time_utc = self.parse_datetime_utc(entry.get('start'))
            stop_time_utc = self.parse_datetime_utc(entry.get('stop'))
            
            if not start_time_utc or not stop_time_utc or entry.get('duration', 0) <= 0:
                continue
            
            # Convert to Swiss local time
            start_time_swiss = self.utc_to_swiss_time(start_time_utc)
            stop_time_swiss = self.utc_to_swiss_time(stop_time_utc)
            
            # Use Swiss date for grouping
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
            
            # Away from home hours
            if 'HomeOffice' not in tags:
                day_data['away_from_home_hours'] += duration_hours
            
            # Late work detection using Swiss local time
            if start_time_swiss.hour >= 20 or stop_time_swiss.hour >= 20:
                day_data['late_work_count'] = 1

        # Calculate complex metrics and store with HH:MM format
        daily_kpis = {}
        
        for date_str, day_data in daily_data.items():
            if not day_data['working_day']:
                continue
                
            entry_data_list = day_data['entries']
            
            # Back home time (Swiss local time as HH:MM)
            commute_entries = [e for e in entry_data_list if 'Commuting' in e['entry'].get('tags', [])]
            if commute_entries:
                last_commute = max(commute_entries, key=lambda x: x['stop_swiss'])
                day_data['back_home_time_swiss'] = last_commute['stop_swiss']
            
            # Home office end time (Swiss local time as HH:MM)
            home_office_entries = [e for e in entry_data_list if 'HomeOffice' in e['entry'].get('tags', [])]
            non_home_entries = [e for e in entry_data_list if 'HomeOffice' not in e['entry'].get('tags', []) and 'Commuting' not in e['entry'].get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                last_home_entry = max(home_office_entries, key=lambda x: x['stop_swiss'])
                day_data['home_office_end_time_swiss'] = last_home_entry['stop_swiss']
            
            # Store daily KPI with HH:MM format
            daily_kpis[date_str] = {
                'billable_hours': {
                    'sum': round(day_data['billable_hours'], 2)
                },
                'away_from_home_hours': {
                    'sum': round(day_data['away_from_home_hours'], 2)
                },
                'back_home_times': {
                    'time': self.swiss_time_to_time_string(day_data['back_home_time_swiss']) if day_data['back_home_time_swiss'] else None
                },
                'home_office_end_times': {
                    'time': self.swiss_time_to_time_string(day_data['home_office_end_time_swiss']) if day_data['home_office_end_time_swiss'] else None
                },
                'late_work_frequency': {
                    'count': day_data['late_work_count']
                },
                'working_day': True,
                'total_entries': day_data['total_entries'],
                'date': date_str
            }
            
        return daily_kpis

    def time_string_to_decimal(self, time_str):
        """Convert HH:MM to decimal hours for calculations"""
        if not time_str:
            return None
        hours, minutes = map(int, time_str.split(':'))
        return hours + minutes / 60.0

    def calculate_time_stats_from_strings(self, time_strings):
        """Calculate statistics from HH:MM time strings"""
        if not time_strings:
            return {}
        
        # Convert to decimal for calculations
        decimal_times = [self.time_string_to_decimal(t) for t in time_strings if t]
        if not decimal_times:
            return {}
        
        # Calculate stats and convert back to HH:MM
        return {
            'mean': self.decimal_hours_to_time(statistics.mean(decimal_times)),
            'median': self.decimal_hours_to_time(statistics.median(decimal_times)),
            'earliest': self.decimal_hours_to_time(min(decimal_times)),
            'latest': self.decimal_hours_to_time(max(decimal_times))
        }

    def aggregate_weekly_data(self, daily_kpis):
        """Aggregate daily KPIs into weekly data with HH:MM format"""
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
            
            if kpis['billable_hours']['sum'] > 0:
                week_data['billable_hours'].append(kpis['billable_hours']['sum'])
            
            if kpis['away_from_home_hours']['sum'] > 0:
                week_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                
            if kpis['back_home_times']['time']:
                week_data['back_home_times'].append(kpis['back_home_times']['time'])
                
            if kpis['home_office_end_times']['time']:
                week_data['home_office_end_times'].append(kpis['home_office_end_times']['time'])
                
            if kpis['late_work_frequency']['count'] > 0:
                week_data['late_work_days'] += 1
        
        # Calculate weekly aggregations with HH:MM format
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
            
            # Back home times (HH:MM format)
            if data['back_home_times']:
                result['back_home_times'] = self.calculate_time_stats_from_strings(data['back_home_times'])
                
            # Home office end times (HH:MM format)
            if data['home_office_end_times']:
                result['home_office_end_times'] = self.calculate_time_stats_from_strings(data['home_office_end_times'])
                
            result['late_work_frequency'] = {
                'count': data['late_work_days']
            }
            
            weekly_kpis[week] = result
            
        return weekly_kpis

    def aggregate_monthly_data(self, daily_kpis):
        """Aggregate daily KPIs into monthly data with HH:MM format"""
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
        
        # Calculate monthly aggregations with HH:MM format
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
                result['back_home_times'] = self.calculate_time_stats_from_strings(data['back_home_times'])
                
            if data['home_office_end_times']:
                result['home_office_end_times'] = self.calculate_time_stats_from_strings(data['home_office_end_times'])
                
            result['late_work_frequency'] = {
                'count': data['late_work_days']
            }
            
            monthly_kpis[month] = result
            
        return monthly_kpis

    def calculate_working_days_aggregations(self, daily_kpis):
        """Calculate rolling working days aggregations with HH:MM format"""
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
                    result['back_home_times'] = self.calculate_time_stats_from_strings(period_data['back_home_times'])
                    
                if period_data['home_office_end_times']:
                    result['home_office_end_times'] = self.calculate_time_stats_from_strings(period_data['home_office_end_times'])
                    
                result['late_work_frequency'] = {
                    'count': period_data['late_work_days']
                }
                
                working_days_aggregations[f"{period}WD"] = result
        
        return working_days_aggregations

    def cleanup_temp_files(self):
        """Remove all temporary/test files"""
        print("🧹 Cleaning up temporary files...")
        
        patterns_to_remove = [
            "*test*", "*corrected*", "*fixed*", "*temp*", 
            "*debug*", "*sample*", "*example*"
        ]
        
        removed_files = []
        
        # Clean data directory
        for pattern in patterns_to_remove:
            for file_path in self.data_dir.glob(pattern):
                if file_path.is_file():
                    print(f"  Removing: {file_path}")
                    file_path.unlink()
                    removed_files.append(str(file_path))
        
        # Clean scripts directory
        scripts_dir = Path("scripts")
        for pattern in patterns_to_remove:
            for file_path in scripts_dir.glob(pattern):
                if file_path.is_file():
                    print(f"  Removing: {file_path}")
                    file_path.unlink()
                    removed_files.append(str(file_path))
        
        print(f"✅ Removed {len(removed_files)} temporary files")
        return removed_files

    def generate_final_production_data(self):
        """Generate final production data with HH:MM format and clean up temp files"""
        print("🚀 GENERATING FINAL PRODUCTION DATA")
        print("=" * 60)
        
        # Load raw data
        raw_data = self.load_raw_data()
        print(f"📊 Loaded {raw_data['total_entries']} raw entries")
        
        # Calculate daily KPIs with HH:MM format
        print("🧮 Calculating daily KPIs with HH:MM time format...")
        daily_kpis = self.calculate_final_daily_kpis(raw_data['raw_entries'])
        print(f"📈 Processed {len(daily_kpis)} working days")
        
        # Generate aggregations
        print("📅 Generating weekly aggregations...")
        weekly_kpis = self.aggregate_weekly_data(daily_kpis)
        print(f"✅ Generated {len(weekly_kpis)} weeks")
        
        print("📆 Generating monthly aggregations...")
        monthly_kpis = self.aggregate_monthly_data(daily_kpis)
        print(f"✅ Generated {len(monthly_kpis)} months")
        
        print("📈 Generating working days aggregations...")
        working_days_kpis = self.calculate_working_days_aggregations(daily_kpis)
        print(f"✅ Generated {len(working_days_kpis)} working day periods")
        
        # Save final production data
        print("💾 Saving final production data...")
        
        files_to_save = [
            (daily_kpis, 'daily_kpis.json'),
            (weekly_kpis, 'weekly_aggregations.json'),
            (monthly_kpis, 'monthly_aggregations.json'),
            (working_days_kpis, 'working_days_aggregations.json')
        ]
        
        for data, filename in files_to_save:
            with open(self.data_dir / filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  ✅ Saved {filename}")
        
        # Clean up temporary files
        removed_files = self.cleanup_temp_files()
        
        # Show sample with HH:MM format
        print(f"\n📊 FINAL DATA SAMPLE (HH:MM format):")
        latest_date = max(daily_kpis.keys())
        sample = daily_kpis[latest_date]
        print(f"Latest day ({latest_date}):")
        print(f"  Back home: {sample['back_home_times']['time']}")
        print(f"  Home office end: {sample['home_office_end_times']['time']}")
        print(f"  Late work: {'Yes' if sample['late_work_frequency']['count'] > 0 else 'No'}")
        
        # Show July 17th specifically
        if '2025-07-17' in daily_kpis:
            july_17 = daily_kpis['2025-07-17']
            print(f"\nJuly 17th verification:")
            print(f"  Back home: {july_17['back_home_times']['time']}")
            print(f"  Late work: {'Yes' if july_17['late_work_frequency']['count'] > 0 else 'No'}")
        
        # Late work summary
        late_work_days = sum(1 for kpi in daily_kpis.values() if kpi['late_work_frequency']['count'] > 0)
        print(f"\n🕘 Late work summary: {late_work_days} days detected")
        
        print(f"\n🎉 FINAL PRODUCTION DATA READY!")
        print(f"📁 Production files: daily_kpis.json, weekly_aggregations.json, monthly_aggregations.json, working_days_aggregations.json")
        print(f"🧹 Cleaned up: {len(removed_files)} temporary files")

def main():
    generator = FinalProductionDataGenerator()
    generator.generate_final_production_data()

if __name__ == "__main__":
    main()