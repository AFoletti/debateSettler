# DebateSettler

**DebateSettler** turns your Toggl Track time logs into a simple dashboard you can use to talk about work hours, commuting, and home time with real data instead of impressions.

It is a **pure static site**: just HTML, CSS, and JavaScript, designed to be hosted directly on GitHub Pages with no runtime backend.

---

## What the dashboard shows

Using the last **30 working days** (days with any tracked time), DebateSettler displays:

- **Total billable hours** and **average billable hours per working day**
- **Time away from home** (non‑HomeOffice time) with daily averages
- **Back home time statistics** for days where commuting is tracked
  - Average, median, earliest, and latest times
- **HomeOffice end times** for days that are pure HomeOffice (no commuting or mixed patterns)
- **Late work frequency** – percentage of working days with activity at or after 20:00
- **Summary counts**
  - Number of time entries in the 30‑day window
  - Total raw entries in the 90‑day window
  - Number of working days analyzed
- **Recent trends card** comparing the last **7 working days** to the 30‑day baseline:
  - Trend in daily billable hours
  - Trend in back‑home times

All calculations happen **in your browser** using the raw data file.

---

## How it works

DebateSettler keeps **two** JSON files in `data/` to power the dashboard and (in the
future) historical charts:

- **`data/raw_history.json`** — the **cumulative source of truth**. Every Toggl
  entry ever tracked, deduped by `id` and stored in the `v9` shape used by the
  metrics engine. It grows over time but is also fully self-contained, so any
  new metric can be re-derived from it.
- **`data/raw_data.json`** — a **derived** file containing the last 90 days
  sliced from the history. This is the file the dashboard actually reads, and
  it preserves the exact format the original site has always used.

### Two GitHub Actions keep these files current

1. **`Fetch Toggl Data Daily`** runs every day:
   - Fetches the **last 30 days** via the Toggl v9 `/me/time_entries` endpoint
   - Replaces that window inside `raw_history.json` (so edits and deletions
     made in the recent past are picked up correctly)
   - Re-derives `raw_data.json` from the updated history
   - Commits both files

2. **`Backfill Toggl History (manual)`** runs only when you trigger it manually
   from the GitHub Actions tab:
   - Walks back through your Toggl history via the **Reports API v3**
     (the only Toggl endpoint that can reach data older than ~3 months)
   - Merges new entries into `raw_history.json` without touching anything
     already stored
   - Useful **once at the beginning** to pull years of past data, and any time
     later if you want to refresh the long history

The static site (served by GitHub Pages):
- Loads `index.html`, `style.css`, `metrics_engine.js`, and `script.js`
- `script.js` fetches `./data/raw_data.json`
- `metrics_engine.js` computes all metrics in the browser
- The page updates to show your latest numbers

There is **no backend server** and no client‑side dependencies beyond the browser.

---

## Deploying on GitHub Pages

1. **Create or reuse a repository** containing the contents of this project at the root.
2. **Add your Toggl API token** as a repository secret named `TOGGL_API_TOKEN`.
3. The repository already ships with two workflows under `.github/workflows/`:
   - `fetch-toggl-data.yml` — runs daily on a cron schedule.
   - `backfill-toggl-history.yml` — manual trigger only (`workflow_dispatch`).
4. **(Recommended on first deploy)** Go to the **Actions** tab → pick
   *Backfill Toggl History (manual)* → **Run workflow**. You can leave the
   inputs empty (defaults walk back to 2010-01-01 and stop automatically when
   no more data is found) or set a specific `start_date` like `2025-01-01`.
   The workflow commits the resulting `data/raw_history.json` back to the repo.
5. In **Settings → Pages**, configure GitHub Pages to serve from the branch
   where these static files live (typically `main`, root folder).
6. Visit your GitHub Pages URL; the dashboard will:
   - Show a loading screen while it fetches `data/raw_data.json`
   - Render your metrics once data is loaded

If no data is available or the JSON cannot be loaded, an error message is shown with a button to retry.

---

## Customizing DebateSettler

You can customize the dashboard by editing these files directly:

- **`index.html`** – change titles, text, or layout
- **`style.css`** – adjust colors, spacing, or typography
- **`script.js`** – tweak UI behavior or add new DOM updates
- **`metrics_engine.js`** – add or change how metrics are calculated

Because everything is static, pushing changes to your repository is enough to update the live site.

For implementation details and extension guidelines, see **`TECHNICAL_README.md`**.
