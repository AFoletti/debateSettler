#!/usr/bin/env python3
"""
Generate all aggregations from timezone-corrected daily KPIs
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def generate_all_aggregations():
    data_dir = Path("data")
    
    # Load timezone-corrected daily KPIs
    with open(data_dir / "daily_kpis.json") as f:
        daily_kpis = json.load(f)
    
    print(f"📊 Loaded {len(daily_kpis)} timezone-corrected daily KPIs")
    
    # Count late work days
    late_work_days = sum(1 for kpi in daily_kpis.values() if kpi['late_work_frequency']['count'] > 0)
    print(f"🕘 Late work days found: {late_work_days}")
    
    # Generate weekly aggregations
    print("\n📅 Generating weekly aggregations...")
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
    
    weekly_kpis = {}
    for week, data in weekly_data.items():
        result = {
            'working_days': data['total_working_days'],
            'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
            'week': week
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
        
        weekly_kpis[week] = result
    
    print(f"✅ Generated {len(weekly_kpis)} weekly aggregations")
    
    # Generate monthly aggregations
    print("📆 Generating monthly aggregations...")
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
    
    monthly_kpis = {}
    for month, data in monthly_data.items():
        result = {
            'working_days': data['total_working_days'],
            'date_range': {'start': min(data['dates']), 'end': max(data['dates'])},
            'month': month
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
    
    print(f"✅ Generated {len(monthly_kpis)} monthly aggregations")
    
    # Generate working days aggregations
    print("📈 Generating working days aggregations...")
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
                    'median': round(statistics.median(period_data['home_office_times']), 2),
                    'earliest': round(min(period_data['home_office_end_times']), 2),
                    'latest': round(max(period_data['home_office_end_times']), 2)
                }
                
            result['late_work_frequency'] = {
                'count': period_data['late_work_days']
            }
            
            working_days_aggregations[f"{period}WD"] = result
    
    print(f"✅ Generated {len(working_days_aggregations)} working days aggregations")
    
    # Save all corrected aggregations
    with open(data_dir / "weekly_aggregations.json", 'w') as f:
        json.dump(weekly_kpis, f, indent=2)
        
    with open(data_dir / "monthly_aggregations.json", 'w') as f:
        json.dump(monthly_kpis, f, indent=2)
        
    with open(data_dir / "working_days_aggregations.json", 'w') as f:
        json.dump(working_days_aggregations, f, indent=2)
    
    print(f"\n🎉 All timezone-corrected aggregations saved!")
    
    # Show sample with late work
    print(f"\n📊 SAMPLE CORRECTED DATA:")
    print(f"July 2025 (month with late work):")
    if '2025-07' in monthly_kpis:
        july_data = monthly_kpis['2025-07']
        print(f"  Working days: {july_data['working_days']}")
        print(f"  Late work days: {july_data['late_work_frequency']['count']}")
        print(f"  Back home times: {july_data.get('back_home_times', 'N/A')}")
    
    print(f"\n30WD (most recent 30 working days):")
    if '30WD' in working_days_aggregations:
        wd30_data = working_days_aggregations['30WD']
        print(f"  Working days: {wd30_data['working_days']}")
        print(f"  Late work days: {wd30_data['late_work_frequency']['count']}")
        print(f"  Back home times: {wd30_data.get('back_home_times', 'N/A')}")

if __name__ == "__main__":
    generate_all_aggregations()