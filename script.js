/**
 * DebateSettler Dashboard - Static JavaScript
 */

// Global state
let rawData = null;
let metrics = null;
let loading = true;
let error = null;

// DOM elements
const loadingContainer = document.getElementById('loading-container');
const errorContainer = document.getElementById('error-container');
const mainDashboard = document.getElementById('main-dashboard');
const retryButton = document.getElementById('retry-button');
const refreshButton = document.getElementById('refresh-button');
const githubActionsLink = document.getElementById('github-actions-link');

// Format last updated timestamp
function formatLastUpdated(isoString) {
  try {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    });
  } catch {
    return 'Unknown';
  }
}

// Update UI with calculated metrics
function updateUI() {
  if (loading) {
    showLoading();
    return;
  }

  if (error) {
    showError(error);
    return;
  }

  showDashboard();

  // Update all UI elements
  updateMetrics();
  updateTrends();
  updateSummary();
  updateFooter();
}

function showLoading() {
  loadingContainer.style.display = 'flex';
  errorContainer.style.display = 'none';
  mainDashboard.style.display = 'none';
}

function showError(errorMessage) {
  loadingContainer.style.display = 'none';
  errorContainer.style.display = 'flex';
  mainDashboard.style.display = 'none';

  document.getElementById('error-message').textContent = errorMessage;
}

function showDashboard() {
  loadingContainer.style.display = 'none';
  errorContainer.style.display = 'none';
  mainDashboard.style.display = 'block';
}

function updateMetrics() {
  if (!metrics) return;

  // Analytics info
  const analyticsInfo = metrics.working_days_analyzed
    ? `${metrics.working_days_analyzed} working days analyzed: ${metrics.date_range.start} to ${metrics.date_range.end}`
    : 'Loading analytics...';
  document.getElementById('analytics-info').textContent = analyticsInfo;

  // Status
  if (rawData?.fetched_at) {
    document.getElementById('last-updated').textContent = `Last updated: ${formatLastUpdated(
      rawData.fetched_at,
    )}`;
  }

  const dataInfo = `Raw data from ${rawData?.date_range?.days || 60} days • Statistics from last ${
    metrics.working_days_analyzed || 30
  } working days • Client-side calculations`;
  document.getElementById('data-info').textContent = dataInfo;

  // Billable Hours
  document.getElementById('billable-hours').textContent = `${metrics.billable_hours || 0}h`;
  document.getElementById('billable-avg').innerHTML = `Daily average: <span>${
    metrics.daily_billable_avg || 0
  }h</span>`;

  // Time Away from Home
  document.getElementById('away-hours').textContent = `${metrics.absent_from_home_hours || 0}h`;
  document.getElementById('away-avg').innerHTML = `Daily average: <span>${
    metrics.daily_away_avg || 0
  }h</span>`;

  // Late Work Frequency
  document.getElementById('late-work-percentage').textContent = `${
    metrics.late_work_frequency?.percentage || 0
  }%`;
  document.getElementById('late-work-subtitle').textContent = `${
    metrics.late_work_frequency?.late_work_days || 0
  } out of ${metrics.late_work_frequency?.total_work_days || 0} work days after 20:00`;

  // Back Home Times
  document.getElementById('back-home-count').textContent = metrics.back_home_stats?.count || 0;
  document.getElementById('back-home-mean').textContent = metrics.back_home_stats?.mean || 'N/A';
  document.getElementById('back-home-median').textContent = metrics.back_home_stats?.median || 'N/A';
  document.getElementById('back-home-earliest').textContent = metrics.back_home_stats?.earliest || 'N/A';
  document.getElementById('back-home-latest').textContent = metrics.back_home_stats?.latest || 'N/A';

  // HomeOffice End Times
  document.getElementById('home-office-count').textContent = metrics.home_office_end_stats?.count || 0;
  document.getElementById('home-office-mean').textContent = metrics.home_office_end_stats?.mean || 'N/A';
  document.getElementById('home-office-median').textContent = metrics.home_office_end_stats?.median || 'N/A';
  document.getElementById('home-office-earliest').textContent =
    metrics.home_office_end_stats?.earliest || 'N/A';
  document.getElementById('home-office-latest').textContent =
    metrics.home_office_end_stats?.latest || 'N/A';
}

function updateTrends() {
  if (!metrics?.trends) return;

  const trendsCard = document.getElementById('trends-card');
  trendsCard.style.display = 'block';

  const billableTrend = metrics.trends.billable_hours;
  const homeTrend = metrics.trends.back_home_time;

  // Update billable hours trend
  const billableIcon = document.getElementById('billable-trend-icon');
  const billableText = document.getElementById('billable-trend-text');
  const billableDiff = document.getElementById('billable-trend-diff');

  switch (billableTrend.trend) {
    case 'up':
      billableIcon.textContent = '↗️';
      billableIcon.className = 'trend-icon trend-up';
      billableText.textContent = 'Longer';
      break;
    case 'down':
      billableIcon.textContent = '↘️';
      billableIcon.className = 'trend-icon trend-down';
      billableText.textContent = 'Shorter';
      break;
    default:
      billableIcon.textContent = '→';
      billableIcon.className = 'trend-icon trend-stable';
      billableText.textContent = 'Same';
      break;
  }

  if (Math.abs(billableTrend.difference) > 0) {
    billableDiff.textContent = `${billableTrend.difference > 0 ? '+' : ''}${(
      billableTrend.difference * 60
    ).toFixed(0)}min`;
    billableDiff.style.display = 'block';
  } else {
    billableDiff.style.display = 'none';
  }

  // Update back home trend
  const homeIcon = document.getElementById('home-trend-icon');
  const homeText = document.getElementById('home-trend-text');
  const homeDiff = document.getElementById('home-trend-diff');

  switch (homeTrend.trend) {
    case 'up':
      homeIcon.textContent = '↗️';
      homeIcon.className = 'trend-icon trend-up';
      homeText.textContent = 'Later';
      break;
    case 'down':
      homeIcon.textContent = '↘️';
      homeIcon.className = 'trend-icon trend-down';
      homeText.textContent = 'Earlier';
      break;
    default:
      homeIcon.textContent = '→';
      homeIcon.className = 'trend-icon trend-stable';
      homeText.textContent = 'Same';
      break;
  }

  if (Math.abs(homeTrend.difference) > 0) {
    homeDiff.textContent = `${homeTrend.difference > 0 ? '+' : ''}${homeTrend.difference.toFixed(0)}min`;
    homeDiff.style.display = 'block';
  } else {
    homeDiff.style.display = 'none';
  }
}

function updateSummary() {
  if (!metrics || !rawData) return;

  document.getElementById('total-entries-30').textContent = metrics.total_entries || 0;
  document.getElementById('total-entries-60').textContent = rawData.total_entries || 0;
  document.getElementById('working-days').textContent = metrics.working_days_analyzed || 0;
}

function updateFooter() {
  if (!rawData) return;

  document.getElementById('workspace-name').textContent = rawData.workspace_name || 'DRE-P';

  // Try to set up GitHub Actions link based on the current URL
  if (githubActionsLink && typeof window !== 'undefined') {
    const hostname = window.location.hostname;

    // Check if we're on GitHub Pages
    if (hostname.includes('github.io')) {
      // Extract username and repo from GitHub Pages URL
      // Format: username.github.io/repo-name
      const pathParts = window.location.pathname.split('/').filter((p) => p);
      const username = hostname.split('.')[0];
      const repoName = pathParts[0] || 'debateSettler';

      const actionsUrl = `https://github.com/${username}/${repoName}/actions/workflows/fetch-toggl-data.yml`;
      githubActionsLink.href = actionsUrl;
      githubActionsLink.style.display = 'inline-flex';

      console.log(`🔗 GitHub Actions link set to: ${actionsUrl}`);
    } else {
      // For local development or other hosting, hide the button
      githubActionsLink.style.display = 'none';
    }
  }
}

// Fetch data from JSON file
async function fetchData() {
  try {
    loading = true;
    error = null;
    updateUI();

    // Fetch raw data from GitHub Pages with proper path handling
    const dataUrl = './data/raw_data.json';
    console.log('Fetching data from:', dataUrl);
    const response = await fetch(dataUrl);

    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.status}`);
    }

    const data = await response.json();
    rawData = data;

    // Process raw data to calculate metrics
    if (!window.DebateSettlerMetrics || typeof window.DebateSettlerMetrics.processRawData !== 'function') {
      throw new Error('Metrics engine not available');
    }

    const calculatedMetrics = window.DebateSettlerMetrics.processRawData(data);
    metrics = calculatedMetrics;

    loading = false;
    error = null;
  } catch (err) {
    loading = false;
    error = `Failed to load dashboard data: ${err.message}`;
    console.error('Error fetching data:', err);
  } finally {
    updateUI();
  }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function () {
  // Initial data fetch
  fetchData();

  // Retry button
  retryButton.addEventListener('click', fetchData);

  // Refresh button
  refreshButton.addEventListener('click', async function () {
    refreshButton.disabled = true;
    refreshButton.textContent = 'Refreshing...';

    try {
      await fetchData();
      console.log('🔄 Data refreshed successfully');
    } catch (error) {
      console.error('❌ Error refreshing data:', error);
    } finally {
      refreshButton.disabled = false;
      refreshButton.innerHTML = `
        <svg class="btn-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          ></path>
        </svg>
        Refresh Data
      `;
    }
  });
});

// Make functions available globally for debugging
window.DebateSettler = {
  fetchData,
  rawData: () => rawData,
  metrics: () => metrics,
};
