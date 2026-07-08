# DebateSettler — Docker Self-Hosting Add-on (PRD)

## Original Problem Statement
Repo: [AFoletti/debateSettler](https://github.com/AFoletti/debateSettler) — a static
dashboard (index.html/style.css/script.js/metrics_engine.js) fed by Toggl-time-tracking
Python scripts (`scripts/*.py`) currently run via GitHub Actions, writing a cumulative
`data/raw_history.json`.

Goal of this task: enable **self-hosting on a Synology NAS via Docker Compose**
(Nginx serving the static site + a cron-based Python fetcher container), WITHOUT
touching any existing app logic, and WITHOUT breaking the existing GitHub Actions flow.

## Constraints (strict)
- Only 1 code change allowed: 2 lines in `scripts/_toggl_common.py` (make `DATA_DIR`
  configurable via env var, default unchanged).
- All other changes are NEW files only. No existing file behavior may change.
- No DB, no API, no new Python/npm packages, no frontend changes, no workflow changes.

## What Was Implemented (2026-07-08)
1. **`scripts/_toggl_common.py`** — `DATA_DIR` now reads `os.environ.get("DATA_DIR")`,
   falling back to `Path("data")` when unset (100% backward compatible with GitHub
   Actions runs).
2. **`docker-compose.yml`** (repo root) — two services:
   - `web`: `nginx:1.27-alpine`, serves repo root read-only on `127.0.0.1:8080`,
     with the `debatesettler_data` named volume mounted read-only at `/data`.
   - `fetcher`: built from `docker/Dockerfile.fetcher`, runs `supercronic` on a
     daily cron (01:45 Europe/Zurich) executing `fetch-toggl-data.py` with
     `DATA_DIR=/data`, using `.env` for Toggl credentials.
   - Named volume `debatesettler_data` is the shared handoff between both
     containers for `raw_history.json`.
3. **`docker/nginx.conf`** — static file serving, cache headers for js/css/json,
   security headers (CSP, X-Frame-Options, etc.), denies dotfiles.
4. **`docker/Dockerfile.fetcher`** — `python:3.11-slim` + `requests`/`python-dateutil`
   + `supercronic` binary for reliable in-container cron.
5. **`docker/crontab`** — single daily cron line matching the GitHub Actions schedule.
6. **`.env.example`** (repo root) — template for `TOGGL_API_TOKEN` / `TOGGL_WORKSPACE`.
7. **`.gitignore`** — appended `.env` and `*.db` (per spec; existing `.env*` patterns
   were already present from before and were not touched).

## Verification Performed
- ✅ `git diff scripts/_toggl_common.py` — confirmed only the exact 2-line change.
- ✅ Unit-level check: `DATA_DIR` unset → resolves to `data/raw_history.json` (backward compat).
- ✅ Unit-level check: `DATA_DIR=/tmp/testdata` → resolves to `/tmp/testdata/raw_history.json`.
- ✅ `docker-compose.yml` parsed successfully with PyYAML (valid syntax, correct services/volumes).
- ✅ All touched/adjacent `.py` files compile (`py_compile`) with no syntax errors.
- ✅ `git status` confirms ONLY `.gitignore` + `scripts/_toggl_common.py` modified;
  all other changes are new files (`docker-compose.yml`, `docker/*`, `.env.example`).
- ⚠️ `node scripts/test_metrics_engine.js` exits 1 — **pre-existing** baseline snapshot
  drift (`absent_from_home_hours: 141.38 vs 191.78`), reproduced identically on the
  original `main` branch commit BEFORE any of this task's changes (verified via
  `git stash`). Unrelated to this task — out of scope per spec (no `metrics_engine.js`/
  `script.js` changes were made or allowed).
- ⚠️ Docker CLI is not available in this sandboxed environment, so
  `docker compose build/up`, live container curl checks, and the in-container
  fetcher run could NOT be executed here. All Docker-related files are verbatim
  copies of the exact specification provided, and YAML/Dockerfile/crontab syntax
  were manually validated. Recommend the user runs the full Docker checklist on
  their actual Synology/Docker host.
- Live Toggl API call test skipped per user's explicit instruction (no token provided).

## Out of Scope / Not Touched
- `index.html`, `style.css`, `script.js`, `metrics_engine.js`, `data/raw_history.json`
- All other `scripts/*.py` files
- `.github/workflows/*.yml`
- No new Python/npm dependencies added

## Next Action Items
- User to run `docker compose build && docker compose up -d` on the actual Synology
  NAS/Docker host and complete the remaining checklist items that require Docker
  (build, up, curl on 8080, in-container fetcher exec).
- User to create real `.env` from `.env.example` with actual Toggl token before
  starting the `fetcher` container.
- The pre-existing `test_metrics_engine.js` baseline mismatch is unrelated to this
  task but may be worth investigating separately (likely a stale baseline snapshot
  vs. the rolling 30-working-day window).
