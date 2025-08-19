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
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch from local JSON file (updated daily by GitHub Actions)
      const response = await fetch(`${process.env.PUBLIC_URL}/data/metrics.json`);
      
      if (!response.ok) {
        throw new Error(`Failed to load data: ${response.status}`);
      }
      
      const data = await response.json();
      setMetrics(data);
    } catch (err) {
      setError(`Failed to load dashboard data: ${err.message}`);
      console.error('Error fetching metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const MetricCard = ({ icon: Icon, title, value, subtitle, children, className = "" }) => (
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="loading-spinner w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your Toggl data...</p>
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
            onClick={fetchMetrics}
            className="bg-primary-600 hover:bg-primary-700 text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
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
        {/* Refresh Button */}
        <div className="flex justify-between items-center mb-6">
          <div className="text-sm text-gray-500">
            {lastUpdated && `Last updated: ${lastUpdated.toLocaleTimeString()}`}
          </div>
          <button
            onClick={fetchMetrics}
            disabled={loading}
            className="bg-primary-600 hover:bg-primary-700 disabled:bg-primary-300 text-white font-medium py-2 px-4 rounded-lg transition-colors"
          >
            Refresh Data
          </button>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          
          {/* Billable Hours */}
          <MetricCard
            icon={ClockIcon}
            title="Total Billable Hours"
            value={`${metrics?.billable_hours || 0}h`}
            subtitle="Last 30 days"
          />

          {/* Absent from Home */}
          <MetricCard
            icon={MapPinIcon}
            title="Time Away from Home"
            value={`${metrics?.absent_from_home_hours || 0}h`}
            subtitle="Non-HomeOffice hours (billable + non-billable)"
          />

          {/* Late Work Frequency */}
          <MetricCard
            icon={ExclamationTriangleIcon}
            title="Late Work Frequency"
            value={`${metrics?.late_work_frequency?.percentage || 0}%`}
            subtitle={`${metrics?.late_work_frequency?.late_work_days || 0} out of ${metrics?.late_work_frequency?.total_work_days || 0} work days after 20:00`}
            className="md:col-span-2 xl:col-span-1"
          />

          {/* Commute Back Home Stats */}
          <MetricCard
            icon={HomeIcon}
            title="Back Home Times"
            value={metrics?.commute_back_home_stats?.count || 0}
            subtitle="Commute sessions analyzed"
            className="md:col-span-1 xl:col-span-2"
          >
            <div className="stats-grid">
              <StatItem 
                label="Average" 
                value={metrics?.commute_back_home_stats?.mean} 
              />
              <StatItem 
                label="Median" 
                value={metrics?.commute_back_home_stats?.median} 
              />
              <StatItem 
                label="Earliest" 
                value={metrics?.commute_back_home_stats?.earliest} 
              />
              <StatItem 
                label="Latest" 
                value={metrics?.commute_back_home_stats?.latest} 
              />
            </div>
          </MetricCard>

          {/* HomeOffice End Times */}
          <MetricCard
            icon={ChartBarIcon}
            title="HomeOffice End Times"
            value={metrics?.home_office_end_stats?.count || 0}
            subtitle="HomeOffice sessions analyzed"
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