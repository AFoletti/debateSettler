import React, { useState, useEffect } from 'react';
import {
  ClockIcon,
  HomeIcon,
  MapPinIcon,
  CalendarIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';
import './App.css';

function App() {
  const [rawData, setRawData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Helper function to parse datetime with timezone handling
  const parseDateTime = (dateTimeStr) => {
    if (!dateTimeStr) return null;
    return new Date(dateTimeStr.replace("Z", "+00:00"));
  };

  // Helper function to format time as HH:MM
  const formatTime = (date) => {
    if (!date) return null;
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  };

  // Helper function to convert minutes to HH:MM format
  const minutesToTime = (minutes) => {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
  };

  // Calculate statistics (mean, median, min, max)
  const calculateStats = (values) => {
    if (values.length === 0) {
      return { mean: null, median: null, earliest: null, latest: null, count: 0 };
    }

    const sorted = [...values].sort((a, b) => a - b);
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const median = sorted.length % 2 === 0 
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)];

    return {
      mean: minutesToTime(mean),
      median: minutesToTime(median),
      earliest: minutesToTime(Math.min(...values)),
      latest: minutesToTime(Math.max(...values)),
      count: values.length
    };
  };

  // Process raw data and calculate all metrics
  const processRawData = (rawData) => {
    const entries = rawData.raw_entries || [];
    
    // Filter entries from last 30 days for calculations
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    
    const recentEntries = entries.filter(entry => {
      const startTime = parseDateTime(entry.start);
      return startTime && startTime >= thirtyDaysAgo && entry.duration > 0;
    });

    // 1. Calculate billable hours (total and daily average)
    let totalBillableSeconds = 0;
    const dailyBillableHours = {};
    
    recentEntries.forEach(entry => {
      if (entry.billable && entry.duration > 0) {
        totalBillableSeconds += entry.duration;
        
        const date = parseDateTime(entry.start).toISOString().split('T')[0];
        if (!dailyBillableHours[date]) dailyBillableHours[date] = 0;
        dailyBillableHours[date] += entry.duration / 3600;
      }
    });
    
    const billableHours = totalBillableSeconds / 3600;
    const billableDays = Object.keys(dailyBillableHours).length;
    const dailyBillableAvg = billableDays > 0 ? billableHours / billableDays : 0;

    // 2. Calculate time away from home (total and daily average)
    let totalAwaySeconds = 0;
    const dailyAwayHours = {};
    
    recentEntries.forEach(entry => {
      const tags = entry.tags || [];
      if (!tags.includes("HomeOffice") && entry.duration > 0) {
        totalAwaySeconds += entry.duration;
        
        const date = parseDateTime(entry.start).toISOString().split('T')[0];
        if (!dailyAwayHours[date]) dailyAwayHours[date] = 0;
        dailyAwayHours[date] += entry.duration / 3600;
      }
    });
    
    const awayFromHomeHours = totalAwaySeconds / 3600;
    const awayDays = Object.keys(dailyAwayHours).length;
    const dailyAwayAvg = awayDays > 0 ? awayFromHomeHours / awayDays : 0;

    // 3. Calculate back home times (when last daily entry ends - ANY entry)
    const dailyLastEntries = {};
    
    recentEntries.forEach(entry => {
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime || !endTime) return;
      
      const date = startTime.toISOString().split('T')[0];
      
      // Keep track of the latest ending entry for each day
      if (!dailyLastEntries[date] || endTime > dailyLastEntries[date].endTime) {
        dailyLastEntries[date] = {
          endTime: endTime,
          entry: entry
        };
      }
    });
    
    const backHomeTimes = Object.values(dailyLastEntries)
      .map(dayData => dayData.endTime.getHours() * 60 + dayData.endTime.getMinutes());
    
    const backHomeStats = calculateStats(backHomeTimes);

    // 4. Calculate HomeOffice end times (when last daily HomeOffice entry ends)
    const dailyHomeOfficeEntries = {};
    
    recentEntries.forEach(entry => {
      const tags = entry.tags || [];
      if (tags.includes("HomeOffice")) {
        const startTime = parseDateTime(entry.start);
        const endTime = parseDateTime(entry.stop);
        if (!startTime || !endTime) return;
        
        const date = startTime.toISOString().split('T')[0];
        
        // Keep track of the latest ending HomeOffice entry for each day
        if (!dailyHomeOfficeEntries[date] || endTime > dailyHomeOfficeEntries[date].endTime) {
          dailyHomeOfficeEntries[date] = {
            endTime: endTime,
            entry: entry
          };
        }
      }
    });
    
    const homeOfficeEndTimes = Object.values(dailyHomeOfficeEntries)
      .map(dayData => dayData.endTime.getHours() * 60 + dayData.endTime.getMinutes());
    
    const homeOfficeStats = calculateStats(homeOfficeEndTimes);

    // 5. Calculate late work frequency (after 20:00)
    const workDays = new Set();
    const lateWorkDays = new Set();
    
    recentEntries.forEach(entry => {
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime) return;
      
      const date = startTime.toISOString().split('T')[0];
      workDays.add(date);
      
      // Check if work started after 20:00 or ended after 20:00
      if ((startTime.getHours() >= 20) || (endTime && endTime.getHours() >= 20)) {
        lateWorkDays.add(date);
      }
    });
    
    const lateWorkPercentage = workDays.size > 0 ? (lateWorkDays.size / workDays.size * 100) : 0;

    return {
      billable_hours: Math.round(billableHours * 100) / 100,
      daily_billable_avg: Math.round(dailyBillableAvg * 100) / 100,
      absent_from_home_hours: Math.round(awayFromHomeHours * 100) / 100,
      daily_away_avg: Math.round(dailyAwayAvg * 100) / 100,
      back_home_stats: backHomeStats,
      home_office_end_stats: homeOfficeStats,
      late_work_frequency: {
        late_work_days: lateWorkDays.size,
        total_work_days: workDays.size,
        percentage: Math.round(lateWorkPercentage * 10) / 10
      },
      total_entries: recentEntries.length,
      date_range: {
        start: thirtyDaysAgo.toISOString().split('T')[0],
        end: new Date().toISOString().split('T')[0]
      }
    };
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch raw data from GitHub Pages
      const response = await fetch(`${process.env.PUBLIC_URL || ''}/data/raw_data.json`);
      
      if (!response.ok) {
        throw new Error(`Failed to load data: ${response.status}`);
      }
      
      const data = await response.json();
      setRawData(data);
      
      // Process raw data to calculate metrics
      const calculatedMetrics = processRawData(data);
      setMetrics(calculatedMetrics);
      
    } catch (err) {
      setError(`Failed to load dashboard data: ${err.message}`);
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const MetricCard = ({ icon: Icon, title, value, subtitle, dailyAvg, children, className = "" }) => (
    <div className={`metric-card ${className}`}>
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <Icon className="metric-icon" />
        </div>
        <div className="ml-4 flex-1">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        </div>
      </div>
      <div className="mt-4">
        <div className="metric-value">{value}</div>
        <div className="metric-label">{subtitle}</div>
        {dailyAvg && (
          <div className="text-sm text-gray-500 mt-1">Daily average: {dailyAvg}</div>
        )}
        {children}
      </div>
    </div>
  );

  const StatItem = ({ label, value }) => (
    <div className="stat-item">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value || 'N/A'}</div>
    </div>
  );

  const formatLastUpdated = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      });
    } catch {
      return 'Unknown';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="loading-spinner w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full mx-auto"></div>
          <p className="mt-4 text-gray-600">Processing your Toggl data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <ExclamationTriangleIcon className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Dashboard</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="bg-primary-600 hover:bg-primary-700 text-white font-medium py-2 px-4 rounded-lg transition-colors inline-flex items-center"
          >
            <ArrowPathIcon className="w-4 h-4 mr-2" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="gradient-bg shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-white">ArgumentSettler Dashboard</h1>
            <p className="mt-2 text-xl text-white opacity-90">
              Your Toggl Track Data - Last 30 Days
            </p>
            <p className="mt-1 text-sm text-white opacity-75">
              {metrics?.date_range && `${metrics.date_range.start} to ${metrics.date_range.end}`}
            </p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Data Status */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <CalendarIcon className="w-5 h-5 text-blue-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-blue-900">
                  Data automatically updated daily at 6:00 AM UTC
                </p>
                <p className="text-xs text-blue-600 mt-1">
                  Last updated: {rawData?.fetched_at ? formatLastUpdated(rawData.fetched_at) : 'Unknown'}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Raw data from {rawData?.date_range?.days || 60} days • Calculations performed client-side
                </p>
              </div>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium py-2 px-3 rounded-lg transition-colors inline-flex items-center text-sm"
            >
              <ArrowPathIcon className="w-4 h-4 mr-1" />
              Refresh
            </button>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          
          {/* Billable Hours */}
          <MetricCard
            icon={ClockIcon}
            title="Total Billable Hours"
            value={`${metrics?.billable_hours || 0}h`}
            subtitle="Last 30 days"
            dailyAvg={`${metrics?.daily_billable_avg || 0}h`}
          />

          {/* Absent from Home */}
          <MetricCard
            icon={MapPinIcon}
            title="Time Away from Home"
            value={`${metrics?.absent_from_home_hours || 0}h`}
            subtitle="Non-HomeOffice hours"
            dailyAvg={`${metrics?.daily_away_avg || 0}h`}
          />

          {/* Late Work Frequency */}
          <MetricCard
            icon={ExclamationTriangleIcon}
            title="Late Work Frequency"
            value={`${metrics?.late_work_frequency?.percentage || 0}%`}
            subtitle={`${metrics?.late_work_frequency?.late_work_days || 0} out of ${metrics?.late_work_frequency?.total_work_days || 0} work days after 20:00`}
            className="md:col-span-2 xl:col-span-1"
          />

          {/* Back Home Times */}
          <MetricCard
            icon={HomeIcon}
            title="Back Home Times"
            value={metrics?.back_home_stats?.count || 0}
            subtitle="Days with tracked entries"
            className="md:col-span-1 xl:col-span-2"
          >
            <div className="stats-grid">
              <StatItem 
                label="Average" 
                value={metrics?.back_home_stats?.mean} 
              />
              <StatItem 
                label="Median" 
                value={metrics?.back_home_stats?.median} 
              />
              <StatItem 
                label="Earliest" 
                value={metrics?.back_home_stats?.earliest} 
              />
              <StatItem 
                label="Latest" 
                value={metrics?.back_home_stats?.latest} 
              />
            </div>
          </MetricCard>

          {/* HomeOffice End Times */}
          <MetricCard
            icon={ChartBarIcon}
            title="HomeOffice End Times"
            value={metrics?.home_office_end_stats?.count || 0}
            subtitle="HomeOffice days analyzed"
            className="md:col-span-2 xl:col-span-1"
          >
            <div className="stats-grid">
              <StatItem 
                label="Average" 
                value={metrics?.home_office_end_stats?.mean} 
              />
              <StatItem 
                label="Median" 
                value={metrics?.home_office_end_stats?.median} 
              />
              <StatItem 
                label="Earliest" 
                value={metrics?.home_office_end_stats?.earliest} 
              />
              <StatItem 
                label="Latest" 
                value={metrics?.home_office_end_stats?.latest} 
              />
            </div>
          </MetricCard>
        </div>

        {/* Summary Stats */}
        <div className="mt-8 bg-white rounded-xl shadow-card p-6 border border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Data Summary</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {metrics?.total_entries || 0}
              </div>
              <div className="text-sm text-gray-600">Total Time Entries</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {metrics?.date_range ? '30' : '0'}
              </div>
              <div className="text-sm text-gray-600">Days Analyzed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {((metrics?.billable_hours || 0) + (metrics?.absent_from_home_hours || 0)).toFixed(1)}h
              </div>
              <div className="text-sm text-gray-600">Total Tracked Time</div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Data sourced from Toggl Track • Workspace: DRE-P</p>
          <p className="mt-1">
            ArgumentSettler helps you win debates with data, not emotions 📊
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;