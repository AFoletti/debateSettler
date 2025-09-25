#!/usr/bin/env python3
"""
Fix aggregation counts by adding proper count fields
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def fix_aggregation_counts():
    data_dir = Path("data")
    
    # Load daily KPIs
    with open(data_dir / "daily_kpis.json") as f:
        daily_kpis = json.load(f)
    
    print(f"📊 Fixing aggregation counts for {len(daily_kpis)} daily KPIs")
    
    def calculate_time_stats_with_count(time_strings):
        """Calculate statistics from HH:MM time strings with proper count"""
        if not time_strings:
            return {}
        
        # Convert to decimal for calculations
        decimal_times = []
        for t in time_strings:
            if t:
                hours, minutes = map(int, t.split(':'))
                decimal_times.append(hours + minutes / 60.0)
        
        if not decimal_times:
            return {}
        
        def decimal_to_time(decimal_hours):
            hours = int(decimal_hours)
            minutes = int((decimal_hours - hours) * 60)
            return f"{hours:02d}:{minutes:02d}"
        
        return {
            'mean': decimal_to_time(statistics.mean(decimal_times)),
            'median': decimal_to_time(statistics.median(decimal_times)),
            'earliest': decimal_to_time(min(decimal_times)),
            'latest': decimal_to_time(max(decimal_times)),
            'count': len(decimal_times)  # ACTUAL COUNT
        }
    
    # Fix weekly aggregations
    print("📅 Fixing weekly aggregations...")
    weekly_data = defaultdict(lambda: {
        'billable_hours': [],
        'away_from_home_hours': [],
        'back_home_times': [],
        'home_office_end_times': [],
        'late_work_days': 0,
        'total_working_days': 0,
        'dates': [],
        'total_entries': 0
    })
    
    for date_str, kpis in daily_kpis.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        year_week = f"{date_obj.year}-W{date_obj.isocalendar()[1]:02d}"
        
        week_data = weekly_data[year_week]
        week_data['dates'].append(date_str)
        week_data['total_working_days'] += 1
        week_data['total_entries'] += kpis.get('total_entries', 0)
        
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
    
    # Generate weekly with proper counts
    weekly_kpis = {}
    for week, data in weekly_data.items():
        result = {
            'working_days': data['total_working_days'],
            'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
            'week': week,
            'total_entries': data['total_entries']
        }
        
        if data['billable_hours']:
            result['billable_hours'] = {
                'sum': round(sum(data['billable_hours']), 2),
                'mean': round(statistics.mean(data['billable_hours']), 2),
                'median': round(statistics.median(data['billable_hours']), 2)
            }
        else:
            result['billable_hours'] = {'sum': 0}
            
        if data['away_from_home_hours']:
            result['away_from_home_hours'] = {
                'mean': round(statistics.mean(data['away_from_home_hours']), 2),
                'median': round(statistics.median(data['away_from_home_hours']), 2)
            }
        
        # FIXED: Add proper counts
        result['back_home_times'] = calculate_time_stats_with_count(data['back_home_times'])
        result['home_office_end_times'] = calculate_time_stats_with_count(data['home_office_end_times'])
            
        result['late_work_frequency'] = {
            'count': data['late_work_days']
        }
        
        weekly_kpis[week] = result
    
    # Fix monthly aggregations
    print("📆 Fixing monthly aggregations...")
    monthly_data = defaultdict(lambda: {
        'billable_hours': [],
        'away_from_home_hours': [],
        'back_home_times': [],
        'home_office_end_times': [],
        'late_work_days': 0,
        'total_working_days': 0,
        'dates': [],
        'total_entries': 0
    })
    
    for date_str, kpis in daily_kpis.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        year_month = f"{date_obj.year}-{date_obj.month:02d}"
        
        month_data = monthly_data[year_month]
        month_data['dates'].append(date_str)
        month_data['total_working_days'] += 1
        month_data['total_entries'] += kpis.get('total_entries', 0)
        
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
    
    monthly_kpis = {}
    for month, data in monthly_data.items():
        result = {
            'working_days': data['total_working_days'],
            'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
            'month': month,
            'total_entries': data['total_entries']
        }
        
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
        
        # FIXED: Add proper counts
        result['back_home_times'] = calculate_time_stats_with_count(data['back_home_times'])
        result['home_office_end_times'] = calculate_time_stats_with_count(data['home_office_end_times'])
            
        result['late_work_frequency'] = {
            'count': data['late_work_days']
        }
        
        monthly_kpis[month] = result
    
    # Fix working days aggregations
    print("📈 Fixing working days aggregations...")
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
                'dates': period_dates,
                'total_entries': 0
            }
            
            for date_str in period_dates:
                kpis = daily_kpis[date_str]
                period_data['total_working_days'] += 1
                period_data['total_entries'] += kpis.get('total_entries', 0)
                
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
                'period': f"{period}WD",
                'total_entries': period_data['total_entries']
            }
            
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
            
            # FIXED: Add proper counts
            result['back_home_times'] = calculate_time_stats_with_count(period_data['back_home_times'])
            result['home_office_end_times'] = calculate_time_stats_with_count(period_data['home_office_end_times'])
                
            result['late_work_frequency'] = {
                'count': period_data['late_work_days']
            }
            
            working_days_aggregations[f"{period}WD"] = result
    
    # Save fixed data
    print("💾 Saving fixed aggregations...")
    
    with open(data_dir / "weekly_aggregations.json", 'w') as f:
        json.dump(weekly_kpis, f, indent=2)
        
    with open(data_dir / "monthly_aggregations.json", 'w') as f:
        json.dump(monthly_kpis, f, indent=2)
        
    with open(data_dir / "working_days_aggregations.json", 'w') as f:
        json.dump(working_days_aggregations, f, indent=2)
    
    # Show verification
    print(f"\n📊 VERIFICATION:")
    latest_week = max(weekly_kpis.keys())
    week_sample = weekly_kpis[latest_week]
    print(f"Week {latest_week}:")
    print(f"  Working days: {week_sample['working_days']}")
    print(f"  Back home count: {week_sample['back_home_times'].get('count', 0)}")
    print(f"  Home office count: {week_sample['home_office_end_times'].get('count', 0)}")
    print(f"  Total entries: {week_sample['total_entries']}")

if __name__ == "__main__":
    fix_aggregation_counts()