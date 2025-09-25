#!/usr/bin/env python3
"""
Test timezone fixes with existing raw data
This will show the difference between UTC and Swiss local time processing
"""

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import pytz

class TestTimezoneFix:
    def __init__(self):
        self.data_dir = Path("data")
        self.swiss_tz = pytz.timezone('Europe/Zurich')

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

    def load_existing_raw_data(self):
        """Load existing raw data for testing"""
        raw_file = self.data_dir / "raw_data.json"
        with open(raw_file) as f:
            return json.load(f)

    def analyze_july_17_timezone_issue(self, raw_entries):
        """Specifically analyze the July 17th issue"""
        print("🔍 ANALYZING JULY 17th TIMEZONE ISSUE:")
        print("=" * 60)
        
        july_17_entries = []
        for entry in raw_entries:
            if '2025-07-17' in entry.get('start', ''):
                start_utc = self.parse_datetime_utc(entry['start'])
                stop_utc = self.parse_datetime_utc(entry['stop'])
                start_swiss = self.utc_to_swiss_time(start_utc)
                stop_swiss = self.utc_to_swiss_time(stop_utc)
                
                july_17_entries.append({
                    'start_utc': start_utc,
                    'stop_utc': stop_utc,
                    'start_swiss': start_swiss,
                    'stop_swiss': stop_swiss,
                    'tags': entry.get('tags', []),
                    'duration_hours': entry.get('duration', 0) / 3600,
                    'billable': entry.get('billable', False)
                })
        
        print(f"Found {len(july_17_entries)} entries for July 17th, 2025")
        print()
        
        # Show timezone conversion examples
        print("TIMEZONE CONVERSION EXAMPLES:")
        print("-" * 40)
        for i, entry in enumerate(july_17_entries[:3], 1):  # Show first 3
            print(f"{i}. UTC:   {entry['start_utc'].strftime('%H:%M:%S')} → {entry['stop_utc'].strftime('%H:%M:%S')}")
            print(f"   SWISS: {entry['start_swiss'].strftime('%H:%M:%S')} → {entry['stop_swiss'].strftime('%H:%M:%S')} ({'CEST' if entry['start_swiss'].dst() else 'CET'})")
            print(f"   Tags: {entry['tags']}")
            print()
        
        # Find commuting entries
        commute_entries = [e for e in july_17_entries if 'Commuting' in e['tags']]
        print(f"COMMUTING ENTRIES ({len(commute_entries)} found):")
        print("-" * 40)
        
        for i, entry in enumerate(commute_entries, 1):
            print(f"{i}. UTC:   {entry['start_utc'].strftime('%H:%M:%S')} → {entry['stop_utc'].strftime('%H:%M:%S')}")
            print(f"   SWISS: {entry['start_swiss'].strftime('%H:%M:%S')} → {entry['stop_swiss'].strftime('%H:%M:%S')}")
            print(f"   Duration: {entry['duration_hours']:.2f}h")
            print()
        
        if commute_entries:
            # Find first and last commuting
            first_commute = min(commute_entries, key=lambda x: x['start_swiss'])
            last_commute = max(commute_entries, key=lambda x: x['stop_swiss'])
            
            print("COMMUTE ANALYSIS:")
            print("-" * 40)
            print(f"First commute started: {first_commute['start_swiss'].strftime('%H:%M')} Swiss time")
            print(f"Last commute ended:    {last_commute['stop_swiss'].strftime('%H:%M')} Swiss time")
            print()
            print("USER CLAIM vs DATA:")
            print(f"User said: Started at 4:37, back at 20:38")
            print(f"Data shows: Started at {first_commute['start_swiss'].strftime('%H:%M')}, back at {last_commute['stop_swiss'].strftime('%H:%M')}")
            print()
            
            # Check late work
            is_late_work_utc = last_commute['stop_utc'].hour >= 20
            is_late_work_swiss = last_commute['stop_swiss'].hour >= 20
            
            print("LATE WORK ANALYSIS:")
            print("-" * 40)
            print(f"End time UTC:   {last_commute['stop_utc'].strftime('%H:%M')} → Late work: {is_late_work_utc}")
            print(f"End time SWISS: {last_commute['stop_swiss'].strftime('%H:%M')} → Late work: {is_late_work_swiss}")
            print()
            
            if is_late_work_swiss and not is_late_work_utc:
                print("🐛 BUG CONFIRMED: UTC logic missed late work!")
                print("✅ SWISS logic correctly detects late work!")
            elif is_late_work_swiss == is_late_work_utc:
                print("ℹ️  Both UTC and Swiss logic agree on late work status")
            
            return {
                'commute_start_swiss': first_commute['start_swiss'].strftime('%H:%M'),
                'commute_end_swiss': last_commute['stop_swiss'].strftime('%H:%M'),
                'is_late_work': is_late_work_swiss,
                'timezone': 'CEST' if last_commute['stop_swiss'].dst() else 'CET'
            }
        
        return None

    def calculate_daily_kpis_with_timezone_fix(self, raw_entries):
        """Calculate daily KPIs with proper timezone handling"""
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

        print(f"\n🧮 Processing {len(raw_entries)} entries with TIMEZONE FIXES...")
        
        late_work_detected = []
        
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
            
            # FIXED: Late work detection using SWISS LOCAL TIME
            if start_time_swiss.hour >= 20 or stop_time_swiss.hour >= 20:
                day_data['late_work_count'] = 1
                late_work_detected.append({
                    'date': date_str,
                    'start_swiss': start_time_swiss.strftime('%H:%M'),
                    'stop_swiss': stop_time_swiss.strftime('%H:%M'),
                    'tags': tags
                })

        if late_work_detected:
            print(f"\n🕘 LATE WORK DETECTED ({len(late_work_detected)} days):")
            for lw in late_work_detected:
                print(f"  - {lw['date']}: {lw['start_swiss']}-{lw['stop_swiss']} (tags: {lw['tags']})")
        else:
            print(f"\n🕘 No late work detected")

        # Calculate complex metrics
        daily_kpis = {}
        
        for date_str, day_data in daily_data.items():
            if not day_data['working_day']:
                continue
                
            entry_data_list = day_data['entries']
            
            # Back home time (Swiss local time)
            commute_entries = [e for e in entry_data_list if 'Commuting' in e['entry'].get('tags', [])]
            if commute_entries:
                last_commute = max(commute_entries, key=lambda x: x['stop_swiss'])
                day_data['back_home_time_swiss'] = self.swiss_time_to_decimal_hours(last_commute['stop_swiss'])
            
            # Home office end time (Swiss local time)
            home_office_entries = [e for e in entry_data_list if 'HomeOffice' in e['entry'].get('tags', [])]
            non_home_entries = [e for e in entry_data_list if 'HomeOffice' not in e['entry'].get('tags', []) and 'Commuting' not in e['entry'].get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                last_home_entry = max(home_office_entries, key=lambda x: x['stop_swiss'])
                day_data['home_office_end_time_swiss'] = self.swiss_time_to_decimal_hours(last_home_entry['stop_swiss'])
            
            # Store daily KPI
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

    def test_timezone_fixes(self):
        """Test timezone fixes with existing data"""
        print("🧪 TESTING TIMEZONE FIXES")
        print("=" * 60)
        
        # Load existing data
        raw_data = self.load_existing_raw_data()
        print(f"📊 Loaded {raw_data['total_entries']} raw entries")
        
        # Analyze July 17th specifically
        july_analysis = self.analyze_july_17_timezone_issue(raw_data['raw_entries'])
        
        # Calculate KPIs with timezone fixes
        print("🔄 Calculating KPIs with timezone fixes...")
        daily_kpis_fixed = self.calculate_daily_kpis_with_timezone_fix(raw_data['raw_entries'])
        
        print(f"📈 Processed {len(daily_kpis_fixed)} working days")
        
        # Show July 17th comparison
        if '2025-07-17' in daily_kpis_fixed:
            print("\n📊 JULY 17th COMPARISON:")
            print("-" * 40)
            
            # Load old KPI
            try:
                with open(self.data_dir / "daily_kpis.json") as f:
                    old_kpis = json.load(f)
                old_july = old_kpis.get('2025-07-17', {})
                
                new_july = daily_kpis_fixed['2025-07-17']
                
                print("OLD (UTC-based):")
                print(f"  Back home: {old_july.get('back_home_times', {}).get('time')} (decimal hours)")
                print(f"  Late work: {old_july.get('late_work_frequency', {}).get('count', 0)}")
                
                print("\nNEW (Swiss time-based):")
                print(f"  Back home: {new_july['back_home_times']['time']} (decimal hours)")
                print(f"  Late work: {new_july['late_work_frequency']['count']}")
                
                if july_analysis:
                    print(f"\nVERIFICATION:")
                    print(f"  User claim: 4:37 → 20:38")
                    print(f"  Data shows: {july_analysis['commute_start_swiss']} → {july_analysis['commute_end_swiss']} ({july_analysis['timezone']})")
                    print(f"  Late work: {july_analysis['is_late_work']}")
                
            except Exception as e:
                print(f"Could not load old KPIs: {e}")
        
        # Save fixed results
        with open(self.data_dir / "daily_kpis_timezone_fixed.json", 'w') as f:
            json.dump(daily_kpis_fixed, f, indent=2)
        
        print(f"\n✅ Timezone-fixed KPIs saved to daily_kpis_timezone_fixed.json")
        
        # Count late work days in fixed version
        late_work_days = sum(1 for kpi in daily_kpis_fixed.values() if kpi['late_work_frequency']['count'] > 0)
        print(f"🕘 Late work days in fixed version: {late_work_days}")
        
        return daily_kpis_fixed

def main():
    tester = TestTimezoneFix()
    daily_kpis = tester.test_timezone_fixes()
    print(f"\n🎉 Timezone fix test completed! Generated {len(daily_kpis)} fixed daily KPIs")

if __name__ == "__main__":
    main()