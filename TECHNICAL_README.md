# DebateSettler – Technical Overview

This document is for developers who want to understand how DebateSettler works internally and how to safely extend it.

## 1. High-Level Architecture

DebateSettler is a **pure static** dashboard:

- **index.html** – DOM structure (loading, error, metrics, trends, summary, footer)
- **style.css** – Dark theme + responsive layout (no frameworks)
- **script.js** – UI state, DOM updates, data loading
- **metrics_engine.js** – Pure calculation logic (all statistics derived from Toggl raw data)
- **data/raw_data.json** – Raw Toggl time entries (last 90 days, excluding today)
- **scripts/fetch-toggl-data.py** – GitHub Actions script that fetches raw Toggl data and writes `data/raw_data.json`
- **scripts/generate_metrics_snapshot.js** – Generates a baseline metrics snapshot from current logic
- **scripts/test_metrics_engine.js** – Compares current metrics output against the baseline snapshot

There is **no build step** required for runtime: GitHub Pages serves `index.html`, `style.css`, `metrics_engine.js` and `script.js` directly.

## 2. Data Flow

1. A scheduled GitHub Action runs `scripts/fetch-toggl-data.py` daily.
2. The script:
   - Reads Toggl API credentials from GitHub Secrets
   - Fetches the last **90 days of entries**, excluding today
   - Removes the `description` field from each entry
   - Stores everything in `data/raw_data.json`
3. When a user opens `index.html`:
   - `script.js` fetches `./data/raw_data.json`
   - Passes the parsed JSON to `DebateSettlerMetrics.processRawData` from `metrics_engine.js`
   - Receives a metrics object and updates the DOM accordingly

All calculations run in the browser; the server (GitHub Pages) only serves static files.

## 3. Metrics and Rules

`metrics_engine.js` exposes a single function:

```js
const { processRawData } = require('./metrics_engine'); // Node
// or in browser: window.DebateSettlerMetrics.processRawData(rawData);
```

`processRawData(rawData)` expects the structure produced by `fetch-toggl-data.py`:

```jsonc
{
  "fetched_at": "2025-12-01T02:57:43.313812",
  "date_range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 90 },
  "workspace_name": "DRE-P",
  "workspace_id": 4536519,
  "total_entries": 968,
  "raw_entries": [ /* Toggl time entries */ ]
}
```

Each entry has at least:

- `start`, `stop` – ISO timestamps
- `duration` – seconds (positive for completed entries)
- `billable` – boolean
- `tags` – array of strings (e.g. `"HomeOffice"`, `"Commuting"`)

### 3.1 Working-Day Selection

1. Collect all dates where there is at least one entry with `duration > 0`.
2. Sort them ascending, then reverse for **most recent first**.
3. Use:
   - `last30WorkingDays` – first 30 dates (or fewer if there are less than 30)
   - `last7WorkingDays` – first 7 dates (or fewer if there are less than 7)

All main dashboard metrics are based on `last30WorkingDays`. Trends compare 7-day values to 30-day values.

### 3.2 Metrics per 30/7 Working Days

For a given set of working days:

- **Billable hours**
  - Sum `duration` (in hours) of entries where `billable === true`.
  - Track billable hours per date; daily average = total billable hours / number of days that had any billable work.

- **Time away from home**
  - Sum `duration` for entries whose `tags` **do not** include `"HomeOffice"`.
  - Daily average = total hours / number of days that had any non-HomeOffice work.

- **Back home times** (commuting)
  - For each date, look at all entries.
  - Find the last entry tagged `"Commuting"`. Only dates with such an entry are counted.
  - The *end time* of that last commuting entry is interpreted as "back home" time.
  - Convert end times to minutes since midnight and compute:
    - `mean`, `median`, `earliest`, `latest`, and `count` (number of commuting days).

- **HomeOffice end times**
  - For each date:
    - Collect **all** entries and the subset tagged `"HomeOffice"`.
    - If there are no HomeOffice entries, skip the day.
    - Sort both collections by start time.
    - Identify:
      - Last entry of the day (any type).
      - Last HomeOffice entry.
      - Last entry tagged `"Commuting"` (if any).
    - Rules to qualify a "pure HomeOffice" day:
      1. If there is Commuting after the last HomeOffice entry → **exclude** the day.
      2. If there are any non-HomeOffice entries after the last HomeOffice entry → **exclude** the day.
      3. Only include the day if the overall last entry of the day is a HomeOffice entry.
  - For qualifying days, use the end time of the last HomeOffice entry and compute `mean`, `median`, `earliest`, `latest`, `count`.

- **Late work frequency**
  - For each entry:
    - Determine its date.
    - Add the date to the set of working days.
    - If the start is at or after 20:00 **or** the end is at or after 20:00, add the date to the set of late-work days.
  - `percentage = (late_work_days / total_work_days) * 100`, rounded to one decimal.

The function returns a structure like:

```js
{
  billable_hours: Number,
  daily_billable_avg: Number,
  absent_from_home_hours: Number,
  daily_away_avg: Number,
  back_home_stats: { mean, median, earliest, latest, count },
  home_office_end_stats: { mean, median, earliest, latest, count },
  late_work_frequency: {
    late_work_days,
    total_work_days,
    percentage
  },
  total_entries: Number,              // entries in the selected period
  working_days_analyzed: Number,      // workingDays.length
  date_range: { start, end },         // oldest and newest dates in the 30-day window
  last_7_days: { /* same metrics for 7-day window */ },
  trends: {
    billable_hours: { trend, difference, percentage },
    back_home_time: { trend, difference, percentage }
  }
}
```

### 3.3 Trends

Trends are computed by comparing 7-day values to 30-day values:

- **billable_hours**: compares `daily_billable_avg` (hours).
- **back_home_time**: compares `back_home_stats.mean` (time of day).

Rules:

- Threshold: ±15 minutes → considered **"stable"**.
- Above threshold:
  - `trend = 'up'` if recent > baseline.
  - `trend = 'down'` if recent < baseline.
- For numeric values (hours), `difference` is in hours; for times, it is in minutes.

The UI converts these into arrows (↗️, ↘️, →) and human-readable labels.

## 4. UI Responsibilities (`script.js`)

`script.js` is responsible for:

- Managing loading / error / dashboard states.
- Fetching `./data/raw_data.json`.
- Calling `DebateSettlerMetrics.processRawData(rawData)`.
- Populating and updating DOM elements with the metrics result.
- Building a GitHub Actions link dynamically when running on GitHub Pages.

It does **not** know any of the detailed calculation rules; those live in `metrics_engine.js`.

## 5. Regression Testing

Two Node scripts help keep your refactors safe:

1. **Generate baseline** (run once, or whenever you intentionally change logic):

```bash
node scripts/generate_metrics_snapshot.js
# writes data/metrics_snapshot_baseline.json
```

2. **Test current engine vs baseline** (run after changes to `metrics_engine.js`):

```bash
node scripts/test_metrics_engine.js
# exits with code 0 if metrics match, non-zero otherwise
```

These tests read the real `data/raw_data.json` in the repo, so they always compare against actual Toggl data.

## 6. Extending the App Safely

When adding a new metric:

1. **Add calculation** to `metrics_engine.js`:
   - Extend `calculateMetricsForDays` or add a new helper.
   - Include the new value in the returned object from `processRawData`.
2. **Update UI** (`index.html` + `script.js`):
   - Add new DOM nodes for the metric.
   - In `script.js`, extend the `updateMetrics` or `updateSummary` functions to write values into those elements.
3. **Update docs**:
   - Add a short explanation to `README.md` and this technical document.
4. **Run regression test**:
   - If the change is intentional and breaks the baseline, regenerate the snapshot after manually confirming numbers.

By keeping the metrics engine pure and tested, you can confidently evolve DebateSettler without breaking existing behavior.
