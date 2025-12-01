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

1. A scheduled GitHub Action (in your repository) runs `scripts/fetch-toggl-data.py` every day.
2. The script:
   - Reads your Toggl Track API token from a GitHub Secret
   - Fetches the last **90 days** of time entries (excluding today)
   - Removes the `description` field from each entry
   - Writes `data/raw_data.json` into the repository
3. The static site (served by GitHub Pages):
   - Loads `index.html`, `style.css`, `metrics_engine.js`, and `script.js`
   - `script.js` fetches `./data/raw_data.json`
   - `metrics_engine.js` computes all metrics in the browser
   - The page updates to show your latest numbers

There is **no backend server** and no client‑side dependencies beyond the browser.

---

## Deploying on GitHub Pages

1. **Create or reuse a repository** containing the contents of this project at the root.
2. **Add your Toggl API token** as a repository secret (e.g. `TOGGL_API_TOKEN`).
3. **Set up a GitHub Action** that runs `scripts/fetch-toggl-data.py` on a schedule (for example, daily at 06:00 UTC) and commits the updated `data/raw_data.json` back to the repo.
4. In **Settings → Pages**, configure GitHub Pages to serve from the branch where these static files live (typically `main`, root folder).
5. Visit your GitHub Pages URL; the dashboard will:
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