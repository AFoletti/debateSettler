/**
 * DebateSettler Dashboard — static JavaScript
 *
 * Reads `./data/raw_history.json` (cumulative source of truth) and renders
 * the metrics for a user-selected timeframe.
 *
 * Timeframes:
 *   - Current week / Last week              (calendar, ISO Mon-Sun)
 *   - Current month / Last month            (calendar)
 *   - Last 30 / 100 working days            (working-days)
 *   - Full history                          (everything we have)
 *
 * Trends card always compares the **last 10 working days** to the
 * **currently selected timeframe**.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let rawData = null;          // shape: { raw_entries: [...], ... }
let metrics = null;
let loading = true;
let error = null;
let currentTimeframeId = "last_30";  // matches previous default behavior

// ---------------------------------------------------------------------------
// DOM elements
// ---------------------------------------------------------------------------
const loadingContainer = document.getElementById("loading-container");
const errorContainer = document.getElementById("error-container");
const mainDashboard = document.getElementById("main-dashboard");
const retryButton = document.getElementById("retry-button");
const timeframeSelector = document.getElementById("timeframe-selector");

// ---------------------------------------------------------------------------
// Timeframes
// ---------------------------------------------------------------------------
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function ymd(date) {
  // YYYY-MM-DD in UTC, matching how metrics_engine.js bucketizes dates.
  return date.toISOString().split("T")[0];
}

function startOfIsoWeekUtc(date) {
  // Monday-based week. Returns a new Date at 00:00 UTC on Monday.
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const dow = (d.getUTCDay() + 6) % 7; // Mon=0 ... Sun=6
  d.setUTCDate(d.getUTCDate() - dow);
  return d;
}

function buildTimeframeSpec(id, today) {
  const now = today || new Date();
  const y = now.getUTCFullYear();
  const m = now.getUTCMonth();
  const d = now.getUTCDate();

  switch (id) {
    case "full":
      return { type: "full", label: "Full history" };
    case "last_100":
      return { type: "last_n_working_days", n: 100, label: "Last 100 working days" };
    case "last_30":
      return { type: "last_n_working_days", n: 30, label: "Last 30 working days" };
    case "current_month": {
      const start = new Date(Date.UTC(y, m, 1));
      const end = new Date(Date.UTC(y, m, d));
      return {
        type: "calendar_range",
        start: ymd(start),
        end: ymd(end),
        label: `${MONTH_NAMES[m]} ${y} (so far)`,
      };
    }
    case "last_month": {
      const start = new Date(Date.UTC(y, m - 1, 1));
      const end = new Date(Date.UTC(y, m, 0)); // last day of previous month
      return {
        type: "calendar_range",
        start: ymd(start),
        end: ymd(end),
        label: `${MONTH_NAMES[start.getUTCMonth()]} ${start.getUTCFullYear()}`,
      };
    }
    case "current_week": {
      const start = startOfIsoWeekUtc(now);
      const end = new Date(Date.UTC(y, m, d));
      return {
        type: "calendar_range",
        start: ymd(start),
        end: ymd(end),
        label: "This week (Mon → today)",
      };
    }
    case "last_week": {
      const startThis = startOfIsoWeekUtc(now);
      const start = new Date(startThis);
      start.setUTCDate(start.getUTCDate() - 7);
      const end = new Date(startThis);
      end.setUTCDate(end.getUTCDate() - 1);
      return {
        type: "calendar_range",
        start: ymd(start),
        end: ymd(end),
        label: "Last week",
      };
    }
    default:
      return buildTimeframeSpec("last_30", now);
  }
}

const TIMEFRAME_BUTTONS = [
  { id: "current_week",  label: "This week" },
  { id: "last_week",     label: "Last week" },
  { id: "current_month", label: "This month" },
  { id: "last_month",    label: "Last month" },
  { id: "last_30",       label: "30 working days" },
  { id: "last_100",      label: "100 working days" },
  { id: "full",          label: "Full history" },
];

// ---------------------------------------------------------------------------
// State transitions
// ---------------------------------------------------------------------------
function showLoading() {
  loadingContainer.style.display = "flex";
  errorContainer.style.display = "none";
  mainDashboard.style.display = "none";
}

function showError(errorMessage) {
  loadingContainer.style.display = "none";
  errorContainer.style.display = "flex";
  mainDashboard.style.display = "none";
  document.getElementById("error-message").textContent = errorMessage;
}

function showDashboard() {
  loadingContainer.style.display = "none";
  errorContainer.style.display = "none";
  mainDashboard.style.display = "block";
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function formatLastUpdated(isoString) {
  try {
    return new Date(isoString).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return "Unknown";
  }
}

function renderTimeframeButtons() {
  if (!timeframeSelector) return;
  timeframeSelector.innerHTML = "";
  for (const tf of TIMEFRAME_BUTTONS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "timeframe-pill";
    btn.dataset.timeframeId = tf.id;
    btn.dataset.testid = `timeframe-${tf.id}`;
    btn.textContent = tf.label;
    if (tf.id === currentTimeframeId) btn.classList.add("is-active");
    btn.addEventListener("click", () => onTimeframeChange(tf.id));
    timeframeSelector.appendChild(btn);
  }
}

function highlightTimeframeButton() {
  if (!timeframeSelector) return;
  for (const el of timeframeSelector.querySelectorAll(".timeframe-pill")) {
    el.classList.toggle("is-active", el.dataset.timeframeId === currentTimeframeId);
  }
}

function onTimeframeChange(id) {
  currentTimeframeId = id;
  highlightTimeframeButton();
  recomputeMetrics();
  updateUI();
}

function recomputeMetrics() {
  if (!rawData) return;
  if (!window.DebateSettlerMetrics || typeof window.DebateSettlerMetrics.processWithTimeframe !== "function") {
    error = "Metrics engine not available";
    return;
  }
  const spec = buildTimeframeSpec(currentTimeframeId);
  metrics = window.DebateSettlerMetrics.processWithTimeframe(rawData, spec);
}

function updateUI() {
  if (loading) return showLoading();
  if (error) return showError(error);

  showDashboard();
  updateMetrics();
  updateTrends();
  updateSummary();
  updateFooter();
}

function updateMetrics() {
  if (!metrics) return;
  const tf = metrics.timeframe || {};
  const tfLabel = tf.label || "selected timeframe";

  // Header analytics info
  const start = (metrics.date_range && metrics.date_range.start) || "—";
  const end = (metrics.date_range && metrics.date_range.end) || "—";
  const dayCount = metrics.working_days_analyzed || 0;
  document.getElementById("analytics-info").textContent =
    `${tfLabel} · ${dayCount} working day${dayCount === 1 ? "" : "s"} (${start} → ${end})`;

  // Status indicator subtext
  if (rawData && rawData.fetched_at) {
    document.getElementById("last-updated").textContent =
      `Last updated: ${formatLastUpdated(rawData.fetched_at)}`;
  } else if (rawData && rawData.last_incremental_at) {
    document.getElementById("last-updated").textContent =
      `Last updated: ${formatLastUpdated(rawData.last_incremental_at)}`;
  }
  document.getElementById("data-info").textContent =
    `Statistics for: ${tfLabel} · client-side calculations`;

  // Metric card subtitles (so each card states the timeframe inline)
  setText("billable-window-label", tfLabel);
  setText("away-window-label", tfLabel);
  setText("home-office-window-label", tfLabel);
  setText("back-home-window-label", tfLabel);

  // Billable hours
  setText("billable-hours", `${metrics.billable_hours || 0}h`);
  document.getElementById("billable-avg").innerHTML =
    `Daily average: <span>${metrics.daily_billable_avg || 0}h</span>`;

  // Time away from home
  setText("away-hours", `${metrics.absent_from_home_hours || 0}h`);
  document.getElementById("away-avg").innerHTML =
    `Daily average: <span>${metrics.daily_away_avg || 0}h</span>`;

  // Late work
  const lwf = metrics.late_work_frequency || {};
  setText("late-work-percentage", `${lwf.percentage || 0}%`);
  setText("late-work-subtitle",
    `${lwf.late_work_days || 0} out of ${lwf.total_work_days || 0} work days after 20:00`);

  // Back home
  const bh = metrics.back_home_stats || {};
  setText("back-home-count", bh.count || 0);
  setText("back-home-mean", bh.mean || "N/A");
  setText("back-home-median", bh.median || "N/A");
  setText("back-home-earliest", bh.earliest || "N/A");
  setText("back-home-latest", bh.latest || "N/A");

  // HomeOffice end times
  const ho = metrics.home_office_end_stats || {};
  setText("home-office-count", ho.count || 0);
  setText("home-office-mean", ho.mean || "N/A");
  setText("home-office-median", ho.median || "N/A");
  setText("home-office-earliest", ho.earliest || "N/A");
  setText("home-office-latest", ho.latest || "N/A");
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function updateTrends() {
  if (!metrics || !metrics.trends) return;
  const trendsCard = document.getElementById("trends-card");
  trendsCard.style.display = "block";

  const billableTrend = metrics.trends.billable_hours;
  const homeTrend = metrics.trends.back_home_time;

  const billableIcon = document.getElementById("billable-trend-icon");
  const billableText = document.getElementById("billable-trend-text");
  const billableDiff = document.getElementById("billable-trend-diff");

  switch (billableTrend.trend) {
    case "up":
      billableIcon.textContent = "↗";
      billableIcon.className = "trend-icon trend-up";
      billableText.textContent = "Longer";
      break;
    case "down":
      billableIcon.textContent = "↘";
      billableIcon.className = "trend-icon trend-down";
      billableText.textContent = "Shorter";
      break;
    default:
      billableIcon.textContent = "→";
      billableIcon.className = "trend-icon trend-stable";
      billableText.textContent = "Same";
      break;
  }
  if (Math.abs(billableTrend.difference) > 0) {
    billableDiff.textContent = `${billableTrend.difference > 0 ? "+" : ""}${(billableTrend.difference * 60).toFixed(0)}min`;
    billableDiff.style.display = "block";
  } else {
    billableDiff.style.display = "none";
  }

  const homeIcon = document.getElementById("home-trend-icon");
  const homeText = document.getElementById("home-trend-text");
  const homeDiff = document.getElementById("home-trend-diff");

  switch (homeTrend.trend) {
    case "up":
      homeIcon.textContent = "↗";
      homeIcon.className = "trend-icon trend-up";
      homeText.textContent = "Later";
      break;
    case "down":
      homeIcon.textContent = "↘";
      homeIcon.className = "trend-icon trend-down";
      homeText.textContent = "Earlier";
      break;
    default:
      homeIcon.textContent = "→";
      homeIcon.className = "trend-icon trend-stable";
      homeText.textContent = "Same";
      break;
  }
  if (Math.abs(homeTrend.difference) > 0) {
    homeDiff.textContent = `${homeTrend.difference > 0 ? "+" : ""}${homeTrend.difference.toFixed(0)}min`;
    homeDiff.style.display = "block";
  } else {
    homeDiff.style.display = "none";
  }

  // Trend footer reflects the new comparison (last 10 wd vs selected)
  const tfLabel = (metrics.timeframe && metrics.timeframe.label) || "selected timeframe";
  setText("trend-footer-text", `Last 10 working days vs ${tfLabel}`);
}

function updateSummary() {
  if (!metrics || !rawData) return;
  setText("total-entries-selected", metrics.total_entries || 0);
  setText("total-entries-history", (rawData.raw_entries || []).length);
  setText("working-days", metrics.working_days_analyzed || 0);
}

function updateFooter() {
  if (!rawData) return;
  setText("workspace-name", rawData.workspace_name || "DRE-P");
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------
async function fetchData() {
  try {
    loading = true;
    error = null;
    updateUI();

    // Read the cumulative source of truth.
    const resp = await fetch("./data/raw_history.json", { cache: "no-store" });
    if (!resp.ok) throw new Error(`Failed to load data: ${resp.status}`);

    rawData = await resp.json();
    if (!Array.isArray(rawData.raw_entries)) {
      throw new Error("Unexpected data file shape (no raw_entries array)");
    }

    recomputeMetrics();
    loading = false;
    error = null;
  } catch (err) {
    loading = false;
    error = `Failed to load dashboard data: ${err.message}`;
    console.error("Error fetching data:", err);
  } finally {
    updateUI();
  }
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  renderTimeframeButtons();
  fetchData();
  if (retryButton) retryButton.addEventListener("click", fetchData);
});

// Debugging hook
window.DebateSettler = {
  fetchData,
  rawData: () => rawData,
  metrics: () => metrics,
  setTimeframe: onTimeframeChange,
};
