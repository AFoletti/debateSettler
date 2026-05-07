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
- **`data/raw_history.json`** – **Cumulative** Toggl history (source of truth)
- **`data/raw_data.json`** – **Derived** last-90-days slice consumed by the dashboard
- **`scripts/_toggl_common.py`** – Shared helpers used by both fetch scripts
- **`scripts/fetch-toggl-data.py`** – Daily incremental fetch (GitHub Actions)
- **`scripts/backfill-toggl-history.py`** – One-shot backfill (manual GitHub Action)
- **`scripts/generate_metrics_snapshot.js`** – Generates a baseline metrics snapshot from the current logic
- **`scripts/test_metrics_engine.js`** – Compares current metrics output against the baseline snapshot

There is **no bundler** (no Webpack/Vite/Parcel/etc.). GitHub Pages (or any static host) serves:

- `index.html`
- `style.css`
- `metrics_engine.js`
- `script.js`
- `data/raw_data.json`
- (Optionally also `data/raw_history.json` if you want chart code in the
  browser to read it directly — currently unused by the live dashboard.)

These filenames are **stable, non-hashed entrypoints** and should be preserved.

---

## 2. Build & Deployment Model (Non-Hashed Static Files)

### 2.1 What "build" means for DebateSettler

For this project, a "build" is simply:

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

- `scripts/_toggl_common.py`
- `scripts/fetch-toggl-data.py`
- `scripts/backfill-toggl-history.py`
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

3. **Data refresh via GitHub Actions** (see §3 for the full data flow)
   - `.github/workflows/fetch-toggl-data.yml` runs the daily incremental fetch.
   - `.github/workflows/backfill-toggl-history.yml` runs the one-shot
     historical backfill (manual trigger only).
   - Both workflows commit `data/raw_history.json` and `data/raw_data.json`
     back into the repo so GitHub Pages serves the fresh data.

4. **Static hosting elsewhere**
   - Any static file host (S3, Netlify, etc.) can serve these files.
   - Ensure that the public root contains at least the runtime files listed in 2.1 with the same names.

---

## 3. Data Flow

### 3.1 Two-file model

DebateSettler maintains two JSON files in `data/`:

| File | Role | Lifecycle |
|------|------|-----------|
| `data/raw_history.json` | **Cumulative source of truth.** All Toggl entries ever tracked, deduped by `id`, stored in v9 entry shape. | Created by the backfill, kept current by the daily fetch. |
| `data/raw_data.json`   | **Derived** last-90-days slice consumed by the live dashboard. | Re-generated on every daily run from `raw_history.json`. |

Both files are committed to the repo by the workflows. The dashboard reads only `raw_data.json` today; future history-based features (e.g. charts) will read `raw_history.json`.

### 3.2 Daily incremental run (`scripts/fetch-toggl-data.py`)

Runs every day on a cron schedule from `.github/workflows/fetch-toggl-data.yml`:

1. Loads `data/raw_history.json`. If missing, bootstraps it from `data/raw_data.json` (no API call needed) or, as a last resort, fetches a 90-day seed via the v9 API.
2. Calls the v9 endpoint `GET /api/v9/me/time_entries` for the **last 30 days** (yesterday – 29 days … yesterday).
3. **Replaces** all entries in `raw_history.json` whose `start` falls in that 30-day window with the freshly fetched ones — capturing edits **and** deletions made within the recent past.
4. Re-derives `data/raw_data.json` as the last-90-days slice from the updated history (preserving the original `fetched_at` / `date_range` shape so the dashboard and regression snapshot continue to work unchanged).
5. Commits `data/raw_history.json` and `data/raw_data.json` (and a mirror in `public/data/`).

The 30-day window keeps the daily run **idempotent** and bounded in size.

### 3.3 One-shot backfill (`scripts/backfill-toggl-history.py`)

Runs only when triggered manually from the GitHub Actions tab via
`.github/workflows/backfill-toggl-history.yml` (`workflow_dispatch`). Inputs:

- `start_date` (optional, `YYYY-MM-DD`) – earliest date to backfill. Default: `2010-01-01` (the script stops automatically as soon as a window comes back empty).
- `page_size` (optional, default `1000`) – Reports API page size.

The script:

1. Resolves the workspace ID and fetches the workspace's tag map (id → name) via the v9 API. The Reports API only returns `tag_ids`, so we resolve them locally.
2. Walks **backward** in time in 90-day windows from yesterday down to the `start_date` floor.
3. For each window calls `POST /reports/api/v3/workspace/{wid}/search/time_entries` (Reports API v3).
4. Normalizes each Reports row into the v9 entry shape used by `metrics_engine.js` (see §3.5).
5. Merges new entries **additively** (never overwrites entries already in `raw_history.json`).
6. Stops early after two consecutive empty windows (signals end of history).
7. Re-derives `data/raw_data.json` and commits both files.

### 3.4 Toggl API quirks worth knowing

These were validated empirically against the live API and shape the design above:

- **v9 `/me/time_entries` has a hard ~3-month-ago floor** on `start_date`. It returns `start_date must not be earlier than YYYY-MM-DD` for older requests. That's why the daily run uses v9 (returns canonical entry shape, simple) but the **backfill must use Reports API v3**.
- **Reports API v3 has a hard ~1000-row cap per single search**, regardless of `page_size`. The backfill detects this (raises `WindowCappedError`) and **automatically splits the window in half**, recursing until each chunk fits under the cap.
- **Reports API v3 cursor pagination is unreliable** when a page fills exactly to `page_size`: the API returns a `X-Next-Id` / `X-Next-Row-Number` header, but the next page can come back empty even when more rows exist. Mitigation: the backfill uses `page_size=1000` (the API max) so almost all windows fit in a single page; the auto-split above covers the residual case.
- **Response header casing**: Toggl returns `X-Next-Id` (lowercase `d`), not the `X-Next-ID` shown in some docs. The shared helper checks both forms defensively.
- **Reports API rows can group multiple sub-entries** under a single row in `time_entries: [...]`. With `grouped` defaulting to `false` each row in practice contains exactly one sub-entry, but the normalizer in `_toggl_common.normalize_reports_entries` handles the multi-sub-entry case anyway.
- **Reports API auth is `email:api_token` per the official docs**, but `{api_token}:api_token` (the same form as v9) works just as well, so we use a single auth helper for both APIs.

### 3.5 Reports v3 → v9 normalization (`_toggl_common.normalize_reports_entries`)

The Reports API v3 response uses **different field names** from `/me/time_entries`. Each entry produced by the backfill is therefore translated into v9 shape so that `metrics_engine.js` and `data/raw_data.json` see exactly one canonical format:

| v9 field used by metrics | Source in Reports v3 |
|--------------------------|----------------------|
| `start`                  | `start` (sub-entry)  |
| `stop`                   | `stop` (sub-entry) — sometimes `end` |
| `duration` (seconds)     | `seconds`            |
| `billable`               | `billable` (row level) |
| `tags` (string array)    | `tag_ids` (row) → resolved against the workspace tag map |
| `tag_ids`                | `tag_ids` (row)      |
| `id`, `workspace_id`, `project_id`, `task_id`, `user_id` | passed through |

`description` is dropped (the project has always done this for privacy).

### 3.6 Bootstrap behavior

To make the migration to the two-file model painless:

- If `data/raw_history.json` is missing **and** `data/raw_data.json` exists →
  the daily script seeds the history from the existing `raw_data.json`
  entries. **No API call is needed.** Run with the env var `BOOTSTRAP_ONLY=1`
  if you want this seed step without performing the daily fetch.
- If both files are missing → the daily script falls back to a 90-day v9
  fetch as the initial seed.

In both cases the backfill workflow can be run afterwards to extend the
history backward in time as far as it goes.

---

## 4. Metrics Engine and Rules

`metrics_engine.js` exposes a single function:

```js
const { processRawData } = require('./metrics_engine'); // Node
// or in browser: window.DebateSettlerMetrics.processRawData(rawData);
```

`processRawData(rawData)` expects the structure produced by the daily fetch
(i.e. the **derived** `raw_data.json`):

```jsonc
{
  "fetched_at": "2025-12-01T02:57:43.313812",
  "date_range": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 90 },
  "workspace_name": "DRE-P",
  "workspace_id": 4536519,
  "total_entries": 968,
  "raw_entries": [ /* Toggl time entries (v9 shape) */ ]
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

1. **Generate baseline** (run once, or whenever you intentionally change logic
   or the underlying data has changed):

```bash
node scripts/generate_metrics_snapshot.js
# writes data/metrics_snapshot_baseline.json
```

2. **Test current engine vs baseline** (run after changes to `metrics_engine.js`):

```bash
node scripts/test_metrics_engine.js
# exits with code 0 if metrics match, non-zero otherwise
```

These tests read the real `data/raw_data.json` in the repo, so they always
compare against actual Toggl data. Note: the baseline snapshot reflects a
specific point in time. After a normal daily run the underlying data changes,
so a once-stale baseline is expected and not a code regression — regenerate it
intentionally when convenient.

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

When adding **history-based** features (e.g. long-range charts):

- Read `data/raw_history.json` directly; it is in the same v9 entry shape as
  `raw_data.json` so any helper that already works with `raw_entries` will work.
- Don't modify the shape of either JSON file. New computed series should live in
  the JS layer (or, if precomputed, in a new file under `data/`).

---

## 8. Handoff Notes for Other Agents (Human or AI)

If you are taking over this project:

1. **Assume no build tool** – treat `/app` as the deployable root.
2. **Serve statically** – any HTTP static server that serves the files as-is will work.
3. **Do not introduce hashed filenames** unless you also update `index.html` and keep the public API (`window.DebateSettlerMetrics.processRawData`, `data/raw_data.json`) intact.
4. **Use the regression scripts** before and after significant changes to ensure metrics behavior is preserved.
5. **Treat `data/raw_history.json` as append-only outside the recent 30-day
   window.** Only the daily script's "replace last 30 days" rule is allowed to
   mutate older entries. Anything else should call the backfill (additive
   merge) to be safe.
6. **Toggl API specifics** are documented in §3.4 — if a future change calls
   the Toggl API, re-read those notes before touching pagination or
   date-window logic.

Following these constraints ensures DebateSettler remains simple to host on GitHub Pages and easy to evolve without surprises.
