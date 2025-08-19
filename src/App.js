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
    
    // Get all unique dates that have entries, sorted by date (most recent first)
    const datesWithEntries = [...new Set(
      entries
        .filter(entry => entry.duration > 0)
        .map(entry => {
          const startTime = parseDateTime(entry.start);
          return startTime ? startTime.toISOString().split('T')[0] : null;
        })
        .filter(date => date !== null)
    )].sort().reverse(); // Most recent first
    
    // Take the last 30 days that actually have entries
    const last30WorkingDays = datesWithEntries.slice(0, 30);
    const oldestWorkingDay = last30WorkingDays[last30WorkingDays.length - 1];
    
    console.log(`📊 Using last 30 working days: ${last30WorkingDays.length} days from ${oldestWorkingDay} to ${last30WorkingDays[0]}`);
    console.log(`🏠 Valid HomeOffice days found: ${Object.keys(validHomeOfficeDays).length}`);
    console.log(`🚪 Back home times calculated for: ${backHomeTimes.length} days`);
    
    // Filter entries to only include those from the last 30 working days
    const recentEntries = entries.filter(entry => {
      const startTime = parseDateTime(entry.start);
      if (!startTime || entry.duration <= 0) return false;
      
      const date = startTime.toISOString().split('T')[0];
      return last30WorkingDays.includes(date);
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
    // BUT exclude HomeOffice entries that come AFTER the last Commuting entry
    const dailyLastEntries = {};
    
    recentEntries.forEach(entry => {
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime || !endTime) return;
      
      const date = startTime.toISOString().split('T')[0];
      
      if (!dailyLastEntries[date]) {
        dailyLastEntries[date] = {
          entries: [],
          lastCommutingTime: null,
          lastOverallEntry: null
        };
      }
      
      // Track all entries for this date
      dailyLastEntries[date].entries.push({
        startTime,
        endTime,
        tags: entry.tags || [],
        entry
      });
    });
    
    // Process each day to find the correct "back home" time
    Object.keys(dailyLastEntries).forEach(date => {
      const dayData = dailyLastEntries[date];
      
      // Sort entries by start time
      dayData.entries.sort((a, b) => a.startTime - b.startTime);
      
      // Find the last Commuting entry
      let lastCommutingEntry = null;
      dayData.entries.forEach(entryData => {
        if (entryData.tags.includes("Commuting")) {
          lastCommutingEntry = entryData;
        }
      });
      
      // Find the latest entry that should count for "back home" time
      // This excludes HomeOffice entries that come AFTER the last Commuting entry
      let validLastEntry = null;
      
      if (lastCommutingEntry) {
        // If there was commuting, use the last commuting entry as back home time
        // and ignore any HomeOffice entries after it
        validLastEntry = lastCommutingEntry;
      } else {
        // If no commuting, use the actual last entry of the day
        validLastEntry = dayData.entries[dayData.entries.length - 1];
      }
      
      dayData.lastOverallEntry = validLastEntry;
    });
    
    const backHomeTimes = Object.values(dailyLastEntries)
      .filter(dayData => dayData.lastOverallEntry)
      .map(dayData => dayData.lastOverallEntry.endTime.getHours() * 60 + dayData.lastOverallEntry.endTime.getMinutes());
    
    const backHomeStats = calculateStats(backHomeTimes);

    // 4. Calculate HomeOffice end times (when last daily HomeOffice entry ends)
    // BUT only for days that END with HomeOffice work (not mixed days)
    const dailyHomeOfficeEntries = {};
    
    recentEntries.forEach(entry => {
      const tags = entry.tags || [];
      const startTime = parseDateTime(entry.start);
      const endTime = parseDateTime(entry.stop);
      if (!startTime || !endTime) return;
      
      const date = startTime.toISOString().split('T')[0];
      
      if (!dailyHomeOfficeEntries[date]) {
        dailyHomeOfficeEntries[date] = {
          homeOfficeEntries: [],
          allEntries: []
        };
      }
      
      // Track all entries for this date
      dailyHomeOfficeEntries[date].allEntries.push({
        startTime,
        endTime,
        tags,
        isHomeOffice: tags.includes("HomeOffice"),
        entry
      });
      
      // Track HomeOffice entries
      if (tags.includes("HomeOffice")) {
        dailyHomeOfficeEntries[date].homeOfficeEntries.push({
          startTime,
          endTime,
          tags,
          entry
        });
      }
    });
    
    // Process each day to determine if it's a valid "HomeOffice day"
    const validHomeOfficeDays = {};
    
    Object.keys(dailyHomeOfficeEntries).forEach(date => {
      const dayData = dailyHomeOfficeEntries[date];
      
      // Sort all entries by start time
      dayData.allEntries.sort((a, b) => a.startTime - b.startTime);
      dayData.homeOfficeEntries.sort((a, b) => a.startTime - b.startTime);
      
      if (dayData.homeOfficeEntries.length === 0) return;
      
      // Find the last entry of the day (any type)
      const lastEntryOfDay = dayData.allEntries[dayData.allEntries.length - 1];
      
      // Find the last HomeOffice entry
      const lastHomeOfficeEntry = dayData.homeOfficeEntries[dayData.homeOfficeEntries.length - 1];
      
      // Find the last Commuting entry
      const commutingEntries = dayData.allEntries.filter(e => e.tags.includes("Commuting"));
      const lastCommutingEntry = commutingEntries.length > 0 ? commutingEntries[commutingEntries.length - 1] : null;
      
      // Rule 1: If there's HomeOffice AFTER the last Commuting entry, ignore it for end-of-day calculations
      if (lastCommutingEntry && lastHomeOfficeEntry.startTime > lastCommutingEntry.endTime) {
        // HomeOffice after commuting - don't count for end-of-day
        return;
      }
      
      // Rule 2: Check if this is a "mixed day" (HomeOffice followed by non-HomeOffice)
      // Find all entries after the last HomeOffice entry
      const entriesAfterLastHomeOffice = dayData.allEntries.filter(e => 
        e.startTime > lastHomeOfficeEntry.endTime && !e.isHomeOffice
      );
      
      if (entriesAfterLastHomeOffice.length > 0) {
        // This is a mixed day (HomeOffice → Office) - don't count for HomeOffice end times
        return;
      }
      
      // Rule 3: Only count if the last entry of the day is HomeOffice
      if (lastEntryOfDay.isHomeOffice) {
        validHomeOfficeDays[date] = lastHomeOfficeEntry;
      }
    });
    
    const homeOfficeEndTimes = Object.values(validHomeOfficeDays)
      .map(entryData => entryData.endTime.getHours() * 60 + entryData.endTime.getMinutes());
    
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
      working_days_analyzed: last30WorkingDays.length,
      date_range: {
        start: oldestWorkingDay || 'N/A',
        end: last30WorkingDays[0] || 'N/A'
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
              {metrics?.working_days_analyzed ? 
                `Last ${metrics.working_days_analyzed} working days: ${metrics.date_range.start} to ${metrics.date_range.end}` :
                'Loading data range...'}
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
                  Raw data from {rawData?.date_range?.days || 60} days • Statistics from last {metrics?.working_days_analyzed || 30} working days • Client-side calculations
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
              <div className="text-sm text-gray-600">Time Entries (30 days)</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {rawData?.total_entries || 0}
              </div>
              <div className="text-sm text-gray-600">Total Raw Entries (60 days)</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-primary-600">
                {metrics?.working_days_analyzed || 0}
              </div>
              <div className="text-sm text-gray-600">Working Days Analyzed</div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 bg-gray-100 rounded-xl p-6 border border-gray-200">
          <div className="text-center">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">🚀 Enhanced ArgumentSettler</h3>
            <p className="text-sm text-gray-600 mb-1">
              Raw data (60 days) fetched daily • Calculations performed in your browser
            </p>
            <p className="text-xs text-gray-500">
              Workspace: {rawData?.workspace_name || 'DRE-P'} • 
              ArgumentSettler helps you win debates with data, not emotions 📊
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;