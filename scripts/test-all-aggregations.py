#!/usr/bin/env python3
"""
Test all aggregation levels with existing data
"""

import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

class TestAllAggregations:
    def __init__(self):
        self.data_dir = Path("data")

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

    def load_daily_kpis(self):
        """Load the test daily KPIs"""
        with open(self.data_dir / "test_daily_kpis.json") as f:
            return json.load(f)

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
                    
                    if kpis['billable_hours']['sum']:
                        period_data['billable_hours'].append(kpis['billable_hours']['sum'])
                    
                    if kpis['away_from_home_hours']['sum']:
                        period_data['away_from_home_hours'].append(kpis['away_from_home_hours']['sum'])
                        
                    if kpis['back_home_times']['mean']:
                        period_data['back_home_times'].append(kpis['back_home_times']['mean'])
                        
                    if kpis['home_office_end_times']['mean']:
                        period_data['home_office_end_times'].append(kpis['home_office_end_times']['mean'])
                        
                    if kpis['late_work_frequency']['count'] > 0:
                        period_data['late_work_days'] += 1
                
                working_days_aggregations[f"{period}WD"] = {
                    'billable_hours': self.calculate_stats(period_data['billable_hours']),
                    'away_from_home_hours': self.calculate_stats(period_data['away_from_home_hours']),
                    'back_home_times': self.calculate_stats(period_data['back_home_times']),
                    'home_office_end_times': self.calculate_stats(period_data['home_office_end_times']),
                    'late_work_frequency': {
                        "sum": period_data['late_work_days'],
                        "mean": round(period_data['late_work_days'] / period_data['total_working_days'] * 100, 1) if period_data['total_working_days'] > 0 else 0,
                        "median": period_data['late_work_days'],
                        "earliest": period_data['late_work_days'],
                        "latest": period_data['late_work_days'],
                        "count": period_data['total_working_days']
                    },
                    'working_days': period_data['total_working_days'],
                    'date_range': {'start': max(period_dates), 'end': min(period_dates)},  # Most recent first
                    'period': f"{period}WD"
                }
        
        return working_days_aggregations

    def test_all_aggregations(self):
        """Test all aggregation levels"""
        print("🧪 Testing all aggregation levels...")
        
        # Load daily KPIs
        daily_kpis = self.load_daily_kpis()
        print(f"📊 Loaded {len(daily_kpis)} daily KPIs")
        
        # Test weekly aggregations
        print("\n📅 Testing weekly aggregations...")
        weekly_kpis = self.aggregate_weekly_data(daily_kpis)
        print(f"✅ Generated {len(weekly_kpis)} weekly aggregations")
        
        # Show sample weekly data
        latest_week = max(weekly_kpis.keys())
        print(f"\nSample week ({latest_week}):")
        print(f"Working days: {weekly_kpis[latest_week]['working_days']}")
        print(f"Billable hours: {weekly_kpis[latest_week]['billable_hours']}")
        print(f"Date range: {weekly_kpis[latest_week]['date_range']}")
        
        # Test monthly aggregations  
        print("\n📆 Testing monthly aggregations...")
        monthly_kpis = self.aggregate_monthly_data(daily_kpis)
        print(f"✅ Generated {len(monthly_kpis)} monthly aggregations")
        
        # Show sample monthly data
        latest_month = max(monthly_kpis.keys())
        print(f"\nSample month ({latest_month}):")
        print(f"Working days: {monthly_kpis[latest_month]['working_days']}")
        print(f"Billable hours: {monthly_kpis[latest_month]['billable_hours']}")
        print(f"Date range: {monthly_kpis[latest_month]['date_range']}")
        
        # Test working days aggregations
        print("\n📈 Testing working days aggregations...")
        working_days_kpis = self.calculate_working_days_aggregations(daily_kpis)
        print(f"✅ Generated {len(working_days_kpis)} working days aggregations")
        
        for period, data in working_days_kpis.items():
            print(f"\n{period}:")
            print(f"  Working days: {data['working_days']}")
            print(f"  Billable hours: {data['billable_hours']}")
            print(f"  Date range: {data['date_range']}")
        
        # Save all test results
        with open(self.data_dir / "test_weekly_kpis.json", 'w') as f:
            json.dump(weekly_kpis, f, indent=2)
            
        with open(self.data_dir / "test_monthly_kpis.json", 'w') as f:
            json.dump(monthly_kpis, f, indent=2)
            
        with open(self.data_dir / "test_working_days_kpis.json", 'w') as f:
            json.dump(working_days_kpis, f, indent=2)
        
        print(f"\n✅ All aggregation tests completed!")
        print(f"📁 Results saved to test_*.json files")
        
        return {
            'daily': daily_kpis,
            'weekly': weekly_kpis, 
            'monthly': monthly_kpis,
            'working_days': working_days_kpis
        }

def main():
    tester = TestAllAggregations()
    results = tester.test_all_aggregations()
    
    print(f"\n🎉 Phase 1 Testing Summary:")
    print(f"📊 Daily KPIs: {len(results['daily'])}")
    print(f"📅 Weekly Aggregations: {len(results['weekly'])}")
    print(f"📆 Monthly Aggregations: {len(results['monthly'])}")
    print(f"📈 Working Days Aggregations: {len(results['working_days'])}")

if __name__ == "__main__":
    main()