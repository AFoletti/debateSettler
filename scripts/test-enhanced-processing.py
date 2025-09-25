#!/usr/bin/env python3
"""
Test enhanced KPI processing with existing raw data
"""

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

class TestEnhancedProcessing:
    def __init__(self):
        self.data_dir = Path("data")

    def parse_datetime(self, dt_str):
        """Parse datetime string with timezone handling"""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def time_to_minutes(self, dt):
        """Convert datetime to minutes since midnight"""
        return dt.hour * 60 + dt.minute

    def calculate_stats(self, values):
        """Calculate sum, mean, median, earliest, latest for a list of values"""
        if not values:
            return {"sum": None, "mean": None, "median": None, "earliest": None, "latest": None, "count": 0}
        
        return {
            "sum": round(sum(values), 2),
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 2),
            "earliest": round(min(values), 2),
            "latest": round(max(values), 2),
            "count": len(values)
        }

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

    def load_existing_raw_data(self):
        """Load existing raw data for testing"""
        raw_file = self.data_dir / "raw_data.json"
        with open(raw_file) as f:
            return json.load(f)

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
            
            # Late work detection (starts or ends after 20:00)
            if start_time.hour >= 20 or stop_time.hour >= 20:
                day_data['late_work_entries'] += 1

        print(f"Found {len(daily_data)} working days")

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
            non_home_entries = [e for e in entries if 'HomeOffice' not in e.get('tags', []) and 'Commuting' not in e.get('tags', [])]
            
            if home_office_entries and not non_home_entries:
                # Pure home office day - find last home office entry
                last_home_entry = max(home_office_entries, key=lambda x: self.parse_datetime(x['stop']))
                home_end_time = self.parse_datetime(last_home_entry['stop'])
                day_data['home_office_end_times'].append(self.time_to_minutes(home_end_time))
            
            # Store daily KPI
            daily_kpis[date_str] = {
                'billable_hours': self.calculate_stats([day_data['billable_hours']]) if day_data['billable_hours'] > 0 else self.calculate_stats([]),
                'away_from_home_hours': self.calculate_stats([day_data['away_from_home_hours']]) if day_data['away_from_home_hours'] > 0 else self.calculate_stats([]),
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

    def test_processing(self):
        """Test the enhanced processing logic"""
        print("🧪 Testing enhanced KPI processing...")
        
        # Load existing data
        raw_data = self.load_existing_raw_data()
        print(f"📊 Loaded {raw_data['total_entries']} raw entries from {raw_data['date_range']['start']} to {raw_data['date_range']['end']}")
        
        # Calculate daily KPIs
        daily_kpis = self.calculate_daily_kpis(raw_data['raw_entries'])
        
        # Show sample results
        print(f"\n📈 Calculated KPIs for {len(daily_kpis)} days")
        print("\n🔍 Sample daily KPI (most recent day):")
        
        latest_date = max(daily_kpis.keys())
        sample_kpi = daily_kpis[latest_date]
        
        print(f"Date: {latest_date}")
        print(f"Billable Hours: {sample_kpi['billable_hours']}")
        print(f"Away from Home: {sample_kpi['away_from_home_hours']}")
        print(f"Back Home Times: {sample_kpi['back_home_times']}")
        print(f"Home Office End: {sample_kpi['home_office_end_times']}")
        print(f"Late Work: {sample_kpi['late_work_frequency']}")
        
        # Save test results
        test_file = self.data_dir / "test_daily_kpis.json"
        with open(test_file, 'w') as f:
            json.dump(daily_kpis, f, indent=2)
        
        print(f"\n✅ Test results saved to {test_file}")
        return daily_kpis

def main():
    tester = TestEnhancedProcessing()
    daily_kpis = tester.test_processing()
    print(f"🎉 Test completed! Generated {len(daily_kpis)} daily KPIs")

if __name__ == "__main__":
    main()