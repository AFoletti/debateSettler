#!/usr/bin/env python3
"""
Generate monthly aggregations from daily KPIs
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def generate_monthly_aggregations():
    data_dir = Path("data")
    
    # Load daily KPIs
    with open(data_dir / "daily_kpis.json") as f:
        daily_kpis = json.load(f)
    
    print(f"📊 Loaded {len(daily_kpis)} daily KPIs")
    
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
    
    # Calculate monthly aggregations
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
        
        print(f"📅 {month}: {data['total_working_days']} working days, {result['billable_hours']['sum']}h billable")
    
    # Save monthly aggregations
    with open(data_dir / "monthly_aggregations.json", 'w') as f:
        json.dump(monthly_kpis, f, indent=2)
    
    print(f"✅ Generated {len(monthly_kpis)} monthly aggregations")
    
    # Show sample
    latest_month = max(monthly_kpis.keys())
    print(f"\nSample ({latest_month}):")
    print(json.dumps(monthly_kpis[latest_month], indent=2))

if __name__ == "__main__":
    generate_monthly_aggregations()