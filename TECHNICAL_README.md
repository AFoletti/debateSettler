# DebateSettler – Technical Overview

This document is for developers (human or AI) who want to understand how DebateSettler works internally and how to safely extend or redeploy it **without introducing hashed filenames or unnecessary build steps**.

---

## 1. High-Level Architecture

DebateSettler is a **pure static** dashboard. There is **no frontend framework** and **no runtime backend**.

Root files under `/app`:

- **`index.html`** – DOM structure (loading, error, metrics, trends, summary, footer)
- **`style.css`** – Dark theme + responsive layout (no frameworks)
- **`metrics_engine.js`** – Pure calculation logic (all statistics derived from Toggl raw data)
- **`script.js`** – UI state, DOM updates, data loading
- **`data/raw_data.json`** – Raw Toggl time entries (last 90 days, excluding today)
- **`scripts/fetch-toggl-data.py`** – GitHub Actions script that fetches Toggl data and writes `data/raw_data.json`
- **`scripts/generate_metrics_snapshot.js`** – Generates a baseline metrics snapshot from the current logic
- **`scripts/test_metrics_engine.js`** – Compares current metrics output against the baseline snapshot

There is **no bundler** (no Webpack/Vite/Parcel/etc.). GitHub Pages (or any static host) serves:

- `index.html`
- `style.css`
- `metrics_engine.js`
- `script.js`
- `data/raw_data.json`

These filenames are **stable, non-hashed entrypoints** and should be preserved.

---

## 2. Build & Deployment Model (Non-Hashed Static Files)

### 2.1 What “build” means for DebateSettler

For this project, a “build” is simply:

- Selecting the minimal set of static files under `/app` that are needed at runtime, and
- Copying them to the target environment **without changing their names**.

Runtime-critical files:

- `index.html`
- `style.css`
- `metrics_engine.js`
- `script.js`
- `data/raw_data.json`
- `favicon.ico`
- `manifest.json`
- `robots.txt`

Support files (used by CI / dev tooling, not served to browsers):

- `scripts/fetch-toggl-data.py`
- `scripts/generate_metrics_snapshot.js`
- `scripts/test_metrics_engine.js`

### 2.2 Non-hashed filenames – strict rule

The dashboard is designed around **fixed file names**. Any agent taking over MUST:

- **Not introduce hashed asset names** (e.g. `main.abcd1234.js`) unless the HTML is also updated to point **exactly** to those names, and
- Prefer to keep the simple structure where:
  - `index.html` references `./style.css`, `./metrics_engine.js`, and `./script.js`
  - `script.js` fetches `./data/raw_data.json`

If you add a bundler for your own development convenience, make sure the final output still exposes:

- An `index.html` at the site root
- A non-hashed JS bundle referenced as `./script.js` (or update `index.html` explicitly)
- A non-hashed CSS file referenced as `./style.css`
- The metrics engine accessible as `window.DebateSettlerMetrics.processRawData`
- `data/raw_data.json` still available at `./data/raw_data.json`

**Recommendation:** keep the current no-bundler setup. It is simpler and less error-prone for this use case.

### 2.3 Typical deployment to GitHub Pages

1. **Repository layout**
   - Place the contents of `/app` at the root of your repository, or
   - Configure GitHub Pages to use the `/app` directory as the site source.

2. **GitHub Pages configuration**
   - In **Settings → Pages**, set:
     - **Source**: your main branch (e.g. `main`)
     - **Folder**: `/ (root)` if `/app` is the repo root; otherwise, configure Pages to use the `/app` folder.

3. **Data refresh via GitHub Actions**
   - A workflow (in `.github/workflows`) should run `scripts/fetch-toggl-data.py` on a schedule (e.g. daily at 06:00 UTC).
   - The workflow must commit the updated `data/raw_data.json` back into the repo so GitHub Pages serves the fresh data.

4. **Static hosting elsewhere**
   - Any static file host (S3, Netlify, etc.) can serve these files.
   - Ensure that the public root contains at least the runtime files listed in 2.1 with the same names.

---

## 3. Data Flow

1. A scheduled GitHub Action runs `scripts/fetch-toggl-data.py` daily.
2. The script:
   - Reads Toggl API credentials from GitHub Secrets
   - Fetches the last **90 days of entries**, excluding today
   - Removes the `description` field from each entry
   - Stores everything in `data/raw_data.json`
3. When a user opens `index.html` in the browser:
   - `script.js` fetches `./data/raw_data.json`
   - Passes the parsed JSON to `DebateSettlerMetrics.processRawData` from `metrics_engine.js`
   - Receives a metrics object and updates the DOM accordingly

All calculations run in the browser; the server (GitHub Pages) only serves static files.

---

## 4. Metrics Engine and Rules

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

### 4.1 Working-Day Selection

1. Collect all dates where there is at least one entry with `duration > 0`.
2. Sort them ascending, then reverse for **most recent first**.
3. Use:
   - `last30WorkingDays` – first 30 dates (or fewer if there are less than 30)
   - `last7WorkingDays` – first 7 dates (or fewer if there are less than 7)

All main dashboard metrics are based on `last30WorkingDays`. Trends compare 7-day values to 30-day values.

### 4.2 Metrics per 30/7 Working Days

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

### 4.3 Trends

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

---

## 5. UI Responsibilities (`script.js`)

`script.js` is responsible for:

- Managing loading / error / dashboard states.
- Fetching `./data/raw_data.json`.
- Calling `DebateSettlerMetrics.processRawData(rawData)`.
- Populating and updating DOM elements with the metrics result.

It does **not** know any of the detailed calculation rules; those live in `metrics_engine.js`.

---

## 6. Regression Testing

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

---

## 7. Extending the App Safely

When adding a new metric or UI feature:

1. **Add calculation** to `metrics_engine.js`:
   - Extend `calculateMetricsForDays` or add a new helper.
   - Include the new value in the returned object from `processRawData`.
2. **Update UI** (`index.html` + `script.js`):
   - Add new DOM nodes for the metric in `index.html`.
   - In `script.js`, extend `updateMetrics`, `updateSummary`, or `updateTrends` to write values into those elements.
3. **Update docs**:
   - Add a short explanation to `README.md` and/or this technical document.
4. **Run regression tests**:
   - If the change is intentional and breaks the baseline, regenerate the snapshot after manually confirming numbers.

---

## 8. Handoff Notes for Other Agents (Human or AI)

If you are taking over this project:

1. **Assume no build tool** – treat `/app` as the deployable root.
2. **Serve statically** – any HTTP static server that serves the files as-is will work.
3. **Do not introduce hashed filenames** unless you also update `index.html` and keep the public API (`window.DebateSettlerMetrics.processRawData`, `data/raw_data.json`) intact.
4. **Use the regression scripts** before and after significant changes to ensure metrics behavior is preserved.

Following these constraints ensures DebateSettler remains simple to host on GitHub Pages and easy to evolve without surprises.
