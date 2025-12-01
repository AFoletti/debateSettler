/**
 * DebateSettler Dashboard - Static JavaScript
 */

// Global state
let rawData = null;
let metrics = null;
let loading = true;
let error = null;

// Chart state
let historyCharts = null;
let chartsInitialized = false;
let chartInstances = {
  billable: null,
  away: null,
  backHome: null,
  homeOffice: null,
};

// DOM elements
const viewToggleDataBtn = document.querySelector('[data-testid="view-toggle-data"]');
const viewToggleChartsBtn = document.querySelector('[data-testid="view-toggle-charts"]');
const chartsSection = document.querySelector('[data-testid="charts-section"]');
const metricsGridSection = document.querySelector('.metrics-grid');
const dataSummarySection = document.querySelector('.data-summary');

let chartState = {
  range: '30d',
  resolution: 'daily',
  means: {
    mean30: false,
    mean90: false,
  },
  aggregation: 'sum',
};

// DOM elements
const loadingContainer = document.getElementById('loading-container');
const errorContainer = document.getElementById('error-container');
const mainDashboard = document.getElementById('main-dashboard');
const retryButton = document.getElementById('retry-button');

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
}

function rangeFilterSeries(series, rangeKey) {
  if (!Array.isArray(series) || series.length === 0) return [];

  // Use date (for daily) or start_date (for weekly/monthly)
  const first = series[0];
  const useDateField = Object.prototype.hasOwnProperty.call(first, 'date') ? 'date' : 'start_date';

  const dates = series
    .map((p) => p[useDateField])
    .filter(Boolean)
    .sort();
  const lastDateStr = dates[dates.length - 1];
  const lastDate = parseISODate(lastDateStr);
  if (!lastDate) return [];

  let startDate = null;

  switch (rangeKey) {
    case '7d': {
      startDate = new Date(lastDate);
      startDate.setDate(startDate.getDate() - 6);
      break;
    }
    case '30d': {
      startDate = new Date(lastDate);
      startDate.setDate(startDate.getDate() - 29);
      break;
    }
    case '3m': {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 3);
      break;
    }
    case '6m': {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 6);
      break;
    }
    case '1y': {
      startDate = new Date(lastDate);
      startDate.setFullYear(startDate.getFullYear() - 1);
      break;
    }
    case 'ytd': {
      startDate = new Date(lastDate.getFullYear(), 0, 1);
      break;
    }
    case 'all':
    default:
      startDate = null;
      break;
  }

  return series.filter((p) => {
    const v = p[useDateField];
    const dt = parseISODate(v);
    if (!dt) return false;
    if (!startDate) return true;
    return dt >= startDate && dt <= lastDate;
  });
}

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

function setViewMode(mode) {
  if (mode === 'charts') {
    viewToggleDataBtn.classList.remove('is-active');
    viewToggleChartsBtn.classList.add('is-active');
    if (metricsGridSection) metricsGridSection.style.display = 'none';
    if (dataSummarySection) dataSummarySection.style.display = 'none';
    if (chartsSection) chartsSection.style.display = 'block';
  } else {
    viewToggleDataBtn.classList.add('is-active');
    viewToggleChartsBtn.classList.remove('is-active');
    if (metricsGridSection) metricsGridSection.style.display = 'grid';
    if (dataSummarySection) dataSummarySection.style.display = 'block';
    if (chartsSection) chartsSection.style.display = 'none';
  }
}

// ---------- Charts Helpers ----------

function parseISODate(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

function rangeFilterDailyMetrics(dailyMetrics, rangeKey) {
  if (!Array.isArray(dailyMetrics) || dailyMetrics.length === 0) return [];

  const dates = dailyMetrics.map((d) => d.date).sort();
  const lastDateStr = dates[dates.length - 1];
  const lastDate = parseISODate(lastDateStr);
  if (!lastDate) return [];

  let startDate = null;

  switch (rangeKey) {
    case '7d': {
      startDate = new Date(lastDate);
      startDate.setDate(startDate.getDate() - 6);
      break;
    }
    case '30d': {
      startDate = new Date(lastDate);
      startDate.setDate(startDate.getDate() - 29);
      break;
    }
    case '3m': {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 3);
      break;
    }
    case '6m': {
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 6);
      break;
    }
    case '1y': {
      startDate = new Date(lastDate);
      startDate.setFullYear(startDate.getFullYear() - 1);
      break;
    }
    case 'ytd': {
      startDate = new Date(lastDate.getFullYear(), 0, 1);
      break;
    }
    case 'all':
    default:
      startDate = null;
      break;
  }

  return dailyMetrics.filter((d) => {
    const dt = parseISODate(d.date);
    if (!dt) return false;
    if (!startDate) return true;
    return dt >= startDate && dt <= lastDate;
  });
}

function tukeyOutlierFlags(values) {
  const finiteVals = values.filter((v) => typeof v === 'number' && Number.isFinite(v));
  if (finiteVals.length < 4) {
    return {
      isOutlier: values.map(() => false),
      lowerFence: null,
      upperFence: null,
    };
  }

  const sorted = [...finiteVals].sort((a, b) => a - b);
  const q1Index = (sorted.length - 1) * 0.25;
  const q3Index = (sorted.length - 1) * 0.75;

  function interp(arr, idx) {
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return arr[lo];
    const t = idx - lo;
    return arr[lo] + (arr[hi] - arr[lo]) * t;
  }

  const q1 = interp(sorted, q1Index);
  const q3 = interp(sorted, q3Index);
  const iqr = q3 - q1;
  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;

  const isOutlier = values.map((v) => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return false;
    return v < lowerFence || v > upperFence;
  });

  return { isOutlier, lowerFence, upperFence };
}

function runningMean(values, windowSize) {
  const result = new Array(values.length).fill(null);
  if (!windowSize || windowSize <= 1) return result;

  const nums = values.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : null));
  let sum = 0;
  let count = 0;

  for (let i = 0; i < nums.length; i++) {
    const v = nums[i];
    if (v != null) {
      sum += v;
      count += 1;
    }

    const removeIndex = i - windowSize;
    if (removeIndex >= 0) {
      const removeVal = nums[removeIndex];
      if (removeVal != null) {
        sum -= removeVal;
        count -= 1;
      }
    }

    if (count > 0 && i >= windowSize - 1) {
      result[i] = sum / count;
    }
  }

  return result;
}

function timeToMinutes(timeStr) {
  if (!timeStr) return null;
  const parts = timeStr.split(':').map((p) => parseInt(p, 10));
  if (parts.length !== 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return null;
  return parts[0] * 60 + parts[1];
}

function minutesToTimeLabel(minutes) {
  if (minutes == null || !Number.isFinite(minutes)) return null;
  const h = String(Math.floor(minutes / 60)).padStart(2, '0');
  const m = String(Math.floor(minutes % 60)).padStart(2, '0');
  return `${h}:${m}`;
}

function aggregateByPeriod(filteredDaily, resolution, valueSelector) {
  if (resolution === 'daily') {
    return filteredDaily.map((d) => ({ key: d.date, label: d.date, value: valueSelector(d) }));
  }

  const buckets = new Map();

  function keyFor(dateStr, res) {
    const dt = parseISODate(dateStr);
    if (!dt) return null;
    const year = dt.getFullYear();
    if (res === 'weekly') {
      // Simple ISO week approximation
      const tmp = new Date(dt.getTime());
      tmp.setHours(0, 0, 0, 0);
      const dayNum = (tmp.getDay() + 6) % 7; // Mon=0
      tmp.setDate(tmp.getDate() - dayNum + 3);
      const firstThursday = new Date(tmp.getFullYear(), 0, 4);
      const diff = tmp - firstThursday;
      const week = 1 + Math.round(diff / (7 * 24 * 60 * 60 * 1000));
      return `${year}-W${String(week).padStart(2, '0')}`;
    }
    // monthly
    const month = String(dt.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
  }

  filteredDaily.forEach((d) => {
    const key = keyFor(d.date, resolution);
    if (!key) return;
    const v = valueSelector(d);
    const isNumeric = typeof v === 'number' && Number.isFinite(v);
    if (!buckets.has(key)) {
      buckets.set(key, {
        key,
        dates: [],
        sum: 0,
        count: 0,
      });
    }
    const bucket = buckets.get(key);
    bucket.dates.push(d.date);
    if (isNumeric) {
      bucket.sum += v;
      bucket.count += 1;
    }
  });

  const result = Array.from(buckets.values()).sort((a, b) => (a.key < b.key ? -1 : 1));
  return result.map((b) => ({ key: b.key, label: b.key, sum: b.sum, count: b.count }));
}

function getAggregatedSeries(filteredDaily, resolution, aggregationMode, selector) {
  if (resolution === 'daily') {
    return filteredDaily.map((d) => ({
      key: d.date,
      label: d.date,
      value: selector(d),
    }));
  }

  const buckets = aggregateByPeriod(filteredDaily, resolution, selector);
  return buckets.map((b) => {
    const base = aggregationMode === 'mean' && b.count > 0 ? b.sum / b.count : b.sum;
    return { key: b.key, label: b.key, value: base };
  });
}

function buildChartDatasetsFromSeries(series, options) {
  const baseValues = series.map((p) => (typeof p.value === 'number' ? p.value : null));
  const baseOutliers = tukeyOutlierFlags(baseValues);

  const labels = series.map((p) => p.label);

  const mean7 = runningMean(baseValues, 7);
  const mean30 = options.mean30 ? runningMean(baseValues, 30) : new Array(baseValues.length).fill(null);
  const mean90 = options.mean90 ? runningMean(baseValues, 90) : new Array(baseValues.length).fill(null);

  const datasets = [];

  // Base bars
  datasets.push({
    type: 'bar',
    label: options.baseLabel,
    data: baseValues,
    backgroundColor: baseValues.map((v, idx) =>
      baseOutliers.isOutlier[idx] ? 'rgba(239, 68, 68, 0.7)' : 'rgba(59, 130, 246, 0.7)',
    ),
    borderWidth: 0,
  });

  // 7d running mean (always on)
  datasets.push({
    type: 'line',
    label: '7d mean',
    data: mean7,
    borderColor: 'rgba(16, 185, 129, 1)',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    tension: 0.3,
    borderWidth: 2,
    pointRadius: 0,
    spanGaps: true,
    yAxisID: options.yAxisID || 'y',
  });

  if (options.mean30) {
    datasets.push({
      type: 'line',
      label: '30d mean',
      data: mean30,
      borderColor: 'rgba(234, 179, 8, 1)',
      backgroundColor: 'rgba(234, 179, 8, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  if (options.mean90) {
    datasets.push({
      type: 'line',
      label: '90d mean',
      data: mean90,
      borderColor: 'rgba(129, 140, 248, 1)',
      backgroundColor: 'rgba(129, 140, 248, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  return { labels, datasets };
}

function ensureHistoryLoaded() {
  if (historyCharts) return Promise.resolve(historyCharts);

  return fetch('./data/history_charts.json')
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Failed to load history_charts.json: ${res.status}`);
      }
      return res.json();
    })
    .then((data) => {
      historyCharts = data;
      return data;
    })
    .catch((err) => {
      console.error('Error loading history_charts.json', err);
      return null;
    });
}

function destroyExistingChart(key) {
  if (chartInstances[key]) {
    chartInstances[key].destroy();
    chartInstances[key] = null;
  }
}

function renderNumericChartFromPrecomputed(key, metricKey, options = {}) {
  if (!historyCharts || !historyCharts.metrics || !historyCharts.metrics[metricKey]) return;

  const metric = historyCharts.metrics[metricKey];
  const seriesSource = metric[chartState.resolution];
  if (!Array.isArray(seriesSource) || seriesSource.length === 0) return;

  // Filter by range based on date or start_date
  const filtered = rangeFilterSeries(seriesSource, chartState.range);
  const values = filtered.map((p) => p.value != null
    ? p.value
    : (chartState.aggregation === 'mean' ? p.mean_per_workday : p.sum));
  const labels = filtered.map((p) => p.date || p.period);

  const baseOutliers = tukeyOutlierFlags(values);

  const mean7 = filtered.map((p) => p.mean_7 ?? null);
  const mean30 = chartState.means.mean30 ? filtered.map((p) => p.mean_30 ?? null) : new Array(values.length).fill(null);
  const mean90 = chartState.means.mean90 ? filtered.map((p) => p.mean_90 ?? null) : new Array(values.length).fill(null);

  const datasets = [];

  // Base bars
  datasets.push({
    type: 'bar',
    label: options.baseLabel,
    data: values,
    backgroundColor: values.map((v, idx) =>
      baseOutliers.isOutlier[idx] ? 'rgba(239, 68, 68, 0.7)' : 'rgba(59, 130, 246, 0.7)',
    ),
    borderWidth: 0,
  });

  // 7d running mean (from precomputed daily only)
  datasets.push({
    type: 'line',
    label: '7d mean',
    data: mean7,
    borderColor: 'rgba(16, 185, 129, 1)',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    tension: 0.3,
    borderWidth: 2,
    pointRadius: 0,
    spanGaps: true,
    yAxisID: options.yAxisID || 'y',
  });

  if (chartState.means.mean30) {
    datasets.push({
      type: 'line',
      label: '30d mean',
      data: mean30,
      borderColor: 'rgba(234, 179, 8, 1)',
      backgroundColor: 'rgba(234, 179, 8, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  if (chartState.means.mean90) {
    datasets.push({
      type: 'line',
      label: '90d mean',
      data: mean90,
      borderColor: 'rgba(129, 140, 248, 1)',
      backgroundColor: 'rgba(129, 140, 248, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  const ctx = document.getElementById(options.canvasId).getContext('2d');
  destroyExistingChart(key);

  chartInstances[key] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            color: '#d1d5db',
          },
          grid: {
            color: 'rgba(55, 65, 81, 0.5)',
          },
        },
        x: {
          ticks: {
            color: '#9ca3af',
            maxTicksLimit: 8,
          },
          grid: {
            color: 'rgba(31, 41, 55, 0.5)',
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            color: '#e5e7eb',
          },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || '';
              const value = context.parsed.y;
              return `${label}: ${value != null ? value.toFixed(2) : 'N/A'}`;
            },
          },
        },
      },
    },
  });
}
  const { labels, datasets } = buildChartDatasetsFromSeries(series, {
    baseLabel: options.baseLabel,
    mean30: chartState.means.mean30,
    mean90: chartState.means.mean90,
    yAxisID: 'y',
  });

  const ctx = document.getElementById(options.canvasId).getContext('2d');
  destroyExistingChart(key);

  chartInstances[key] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            color: '#d1d5db',
          },
          grid: {
            color: 'rgba(55, 65, 81, 0.5)',
          },
        },
        x: {
          ticks: {
            color: '#9ca3af',
            maxTicksLimit: 8,
          },
          grid: {
            color: 'rgba(31, 41, 55, 0.5)',
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            color: '#e5e7eb',
          },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || '';
              const value = context.parsed.y;
              return `${label}: ${value != null ? value.toFixed(2) : 'N/A'}`;
            },
          },
        },
      },
    },
  });
}

function renderTimeChartFromPrecomputed(key, metricKey, options = {}) {
  if (!historyCharts || !historyCharts.metrics || !historyCharts.metrics[metricKey]) return;

  const metric = historyCharts.metrics[metricKey];
  const seriesSource = metric[chartState.resolution];
  if (!Array.isArray(seriesSource) || seriesSource.length === 0) return;

  const filtered = rangeFilterSeries(seriesSource, chartState.range);
  const values = filtered.map((p) => p.value != null
    ? p.value
    : (chartState.aggregation === 'mean' ? p.mean_per_workday : p.sum));
  const labels = filtered.map((p) => p.date || p.period);

  const baseOutliers = tukeyOutlierFlags(values);

  const mean7 = filtered.map((p) => p.mean_7 ?? null);
  const mean30 = chartState.means.mean30 ? filtered.map((p) => p.mean_30 ?? null) : new Array(values.length).fill(null);
  const mean90 = chartState.means.mean90 ? filtered.map((p) => p.mean_90 ?? null) : new Array(values.length).fill(null);

  const datasets = [];

  datasets.push({
    type: 'bar',
    label: options.baseLabel,
    data: values,
    backgroundColor: values.map((v, idx) =>
      baseOutliers.isOutlier[idx] ? 'rgba(239, 68, 68, 0.7)' : 'rgba(59, 130, 246, 0.7)',
    ),
    borderWidth: 0,
  });

  datasets.push({
    type: 'line',
    label: '7d mean',
    data: mean7,
    borderColor: 'rgba(16, 185, 129, 1)',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    tension: 0.3,
    borderWidth: 2,
    pointRadius: 0,
    spanGaps: true,
    yAxisID: options.yAxisID || 'y',
  });

  if (chartState.means.mean30) {
    datasets.push({
      type: 'line',
      label: '30d mean',
      data: mean30,
      borderColor: 'rgba(234, 179, 8, 1)',
      backgroundColor: 'rgba(234, 179, 8, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  if (chartState.means.mean90) {
    datasets.push({
      type: 'line',
      label: '90d mean',
      data: mean90,
      borderColor: 'rgba(129, 140, 248, 1)',
      backgroundColor: 'rgba(129, 140, 248, 0.1)',
      tension: 0.3,
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: true,
      yAxisID: options.yAxisID || 'y',
    });
  }

  const ctx = document.getElementById(options.canvasId).getContext('2d');
  destroyExistingChart(key);

  chartInstances[key] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: false,
          ticks: {
            color: '#d1d5db',
            callback(value) {
              return minutesToTimeLabel(value) || '';
            },
          },
          grid: {
            color: 'rgba(55, 65, 81, 0.5)',
          },
        },
        x: {
          ticks: {
            color: '#9ca3af',
            maxTicksLimit: 8,
          },
          grid: {
            color: 'rgba(31, 41, 55, 0.5)',
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            color: '#e5e7eb',
          },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || '';
              const value = context.parsed.y;
              const human = minutesToTimeLabel(value);
              return `${label}: ${human || 'N/A'}`;
            },
          },
        },
      },
    },
  });
}

function renderAllCharts() {
  if (!historyCharts || !historyCharts.metrics) return;

  // Billable hours (numeric)
  renderNumericChartFromPrecomputed(
    'billable',
    'billable_hours',
    {
      canvasId: 'chart-billable-canvas',
      baseLabel: 'Billable hours',
    },
  );

  // Away from home (numeric)
  renderNumericChartFromPrecomputed(
    'away',
    'away_from_home_hours',
    {
      canvasId: 'chart-away-canvas',
      baseLabel: 'Away from home (hours)',
    },
  );

  // Back home times (time-of-day)
  renderTimeChartFromPrecomputed(
    'backHome',
    'back_home_time',
    {
      canvasId: 'chart-back-home-canvas',
      baseLabel: 'Back home time',
    },
  );

  // HomeOffice end times (time-of-day)
  renderTimeChartFromPrecomputed(
    'homeOffice',
    'home_office_end_time',
    {
      canvasId: 'chart-home-office-canvas',
      baseLabel: 'HomeOffice end time',
    },
  );
}

function initChartControls() {
  if (chartsInitialized) return;
  chartsInitialized = true;

  // Range buttons
  document.querySelectorAll('[data-range]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const range = btn.getAttribute('data-range');
      chartState.range = range;
      document.querySelectorAll('[data-range]').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      renderAllCharts();
    });
  });

  // Resolution buttons
  document.querySelectorAll('[data-resolution]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const res = btn.getAttribute('data-resolution');
      chartState.resolution = res;
      document
        .querySelectorAll('[data-resolution]')
        .forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      renderAllCharts();
    });
  });

  // Running means buttons (30d / 90d)
  document.querySelectorAll('[data-mean]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.getAttribute('data-mean');
      if (val === '30') {
        chartState.means.mean30 = !chartState.means.mean30;
        btn.classList.toggle('is-active', chartState.means.mean30);
      } else if (val === '90') {
        chartState.means.mean90 = !chartState.means.mean90;
        btn.classList.toggle('is-active', chartState.means.mean90);
      }
      renderAllCharts();
    });
  });

  // Aggregation buttons (sum/mean)
  document.querySelectorAll('[data-agg]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const agg = btn.getAttribute('data-agg');
      chartState.aggregation = agg;
      document.querySelectorAll('[data-agg]').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      renderAllCharts();
    });
  });
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

  // Default to data view
  setViewMode('data');

  // Load history for charts and init controls
  ensureHistoryLoaded().then(() => {
    initChartControls();
    renderAllCharts();
  });

  // View toggle buttons
  if (viewToggleDataBtn && viewToggleChartsBtn) {
    viewToggleDataBtn.addEventListener('click', () => setViewMode('data'));
    viewToggleChartsBtn.addEventListener('click', () => setViewMode('charts'));
  }

  // Retry button
  retryButton.addEventListener('click', fetchData);
});

// Make functions available globally for debugging
window.DebateSettler = {
  fetchData,
  rawData: () => rawData,
  metrics: () => metrics,
};
