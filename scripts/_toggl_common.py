"""
Shared helpers for DebateSettler Toggl scripts.

Both `fetch-toggl-data.py` (daily) and `backfill-toggl-history.py` (one-shot)
import from this module. They maintain a single cumulative file:
`data/raw_history.json`.

Schema reminder
---------------
data/raw_history.json (cumulative source of truth):
{
  "version": 1,
  "workspace_name": "...",
  "workspace_id": 0,
  "first_entry_start": "...",
  "last_entry_start":  "...",
  "last_backfill_at":  "... or null",
  "last_incremental_at": "... or null",
  "total_entries": N,
  "raw_entries": [ <v9-shape entries, sorted by start ASC, deduped by id, NO description> ]
}
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "raw_history.json"

HISTORY_VERSION = 1

V9_BASE = "https://api.track.toggl.com/api/v9"
REPORTS_V3_BASE = "https://api.track.toggl.com/reports/api/v3"


# ---------------------------------------------------------------------------
# Auth & workspace helpers
# ---------------------------------------------------------------------------
def make_auth_headers(api_token: str) -> dict:
    auth = base64.b64encode(f"{api_token}:api_token".encode()).decode()
    return {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    }


def get_workspace_id(headers: dict, workspace_name: str) -> int:
    r = requests.get(f"{V9_BASE}/workspaces", headers=headers, timeout=30)
    r.raise_for_status()
    for ws in r.json():
        if ws["name"] == workspace_name:
            return ws["id"]
    raise ValueError(f"Workspace '{workspace_name}' not found")


def get_workspace_tags_map(headers: dict, workspace_id: int) -> dict:
    """Return {tag_id: tag_name} for the workspace."""
    r = requests.get(
        f"{V9_BASE}/workspaces/{workspace_id}/tags", headers=headers, timeout=30
    )
    r.raise_for_status()
    return {t["id"]: t["name"] for t in (r.json() or [])}


# ---------------------------------------------------------------------------
# v9 fetch (daily run)
# ---------------------------------------------------------------------------
def fetch_v9_time_entries(headers: dict, start_date: datetime, end_date: datetime) -> list:
    """Fetch entries via /me/time_entries — returns native v9 shape."""
    params = {
        "start_date": start_date.strftime("%Y-%m-%dT00:00:00.000Z"),
        "end_date": end_date.strftime("%Y-%m-%dT23:59:59.999Z"),
    }
    r = requests.get(
        f"{V9_BASE}/me/time_entries", headers=headers, params=params, timeout=60
    )
    r.raise_for_status()
    return r.json() or []


# ---------------------------------------------------------------------------
# Reports API v3 fetch (backfill)
# ---------------------------------------------------------------------------
class WindowCappedError(RuntimeError):
    """Raised when a Reports API search returns the API's hard row cap,
    indicating the window should be split and retried."""


def fetch_reports_v3_window(
    headers: dict,
    workspace_id: int,
    start_date: datetime,
    end_date: datetime,
    page_size: int = 1000,
    sleep_between_pages: float = 0.4,
) -> list:
    """
    Fetch ALL entries in [start_date, end_date] from Reports API v3.

    Notes on Toggl quirks (validated empirically against the live API):
      • The API has a hard ~1000-row cap per single search.
      • Cursor pagination via X-Next-Id / X-Next-Row-Number is unreliable when
        a page fills exactly to `page_size`: the next page can return 0 rows
        even when more data exists. We therefore prefer `page_size=1000`
        (the API max) so a single page usually covers the window.
      • If a single page returns exactly `page_size` rows AND `page_size`
        equals the API cap (1000), the caller MUST split the window further —
        this function raises `WindowCappedError` to signal that case.

    Returns a list of entries in the **Reports API v3 row shape**
    (must be normalized to v9 shape afterwards).
    """
    url = f"{REPORTS_V3_BASE}/workspace/{workspace_id}/search/time_entries"
    payload_base = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "page_size": page_size,
        "order_by": "date",
        # DESC: most-recent entries come back first. Combined with small
        # walk-back windows in the caller, this keeps each search well below
        # the Reports API's ~1000-row-per-search cap.
        "order_dir": "DESC",
    }

    all_entries: list = []
    first_id = None
    first_row_number = None
    page = 0

    while True:
        page += 1
        payload = dict(payload_base)
        if first_id is not None:
            payload["first_id"] = first_id
        if first_row_number is not None:
            payload["first_row_number"] = first_row_number

        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 429:
            import time as _time

            _time.sleep(2.0)
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()

        body = r.json() or []
        # The Reports API v3 sometimes returns a bare list, sometimes {data: [...]}.
        if isinstance(body, dict):
            entries = body.get("data", []) or []
        else:
            entries = body

        all_entries.extend(entries)

        next_id = r.headers.get("X-Next-Id") or r.headers.get("X-Next-ID")
        next_row = r.headers.get("X-Next-Row-Number")
        if not next_id or not next_row:
            break

        first_id = int(next_id)
        first_row_number = int(next_row)

        if sleep_between_pages > 0:
            import time as _time

            _time.sleep(sleep_between_pages)

        if page > 5000:
            raise RuntimeError("Pagination safety limit hit (5000 pages)")

    REPORTS_V3_HARD_CAP = 1000
    if len(all_entries) >= REPORTS_V3_HARD_CAP and page_size >= REPORTS_V3_HARD_CAP:
        raise WindowCappedError(
            f"Window {start_date.date()}→{end_date.date()} returned "
            f"{len(all_entries)} rows (API cap = {REPORTS_V3_HARD_CAP}). "
            "Split the window and retry."
        )

    return all_entries


# ---------------------------------------------------------------------------
# Reports v3 → v9 shape normalization
# ---------------------------------------------------------------------------
def _row_workspace_id(report_row: dict, default_wid: int) -> int:
    return report_row.get("workspace_id") or default_wid


def normalize_reports_entries(
    report_rows: list, workspace_id: int, tag_map: dict
) -> list:
    """
    Convert Reports API v3 rows (one row may itself contain a `time_entries`
    array of sub-entries) to the v9 shape used everywhere else in this app.

    Output shape (v9-like, with description removed):
      id, workspace_id, project_id, task_id, billable, start, stop,
      duration, tags, tag_ids, duronly, at, server_deleted_at,
      user_id, uid, wid, pid, tid
    """
    normalized: list = []

    for row in report_rows:
        sub_entries = row.get("time_entries")
        row_common = {
            "workspace_id": _row_workspace_id(row, workspace_id),
            "project_id": row.get("project_id"),
            "task_id": row.get("task_id"),
            "billable": bool(row.get("billable", False)),
            "tag_ids": row.get("tag_ids") or [],
            "user_id": row.get("user_id"),
        }

        if isinstance(sub_entries, list) and sub_entries:
            for sub in sub_entries:
                normalized.append(_build_v9_entry(sub, row_common, tag_map))
        else:
            normalized.append(_build_v9_entry(row, row_common, tag_map))

    return normalized


def _build_v9_entry(src: dict, row_common: dict, tag_map: dict) -> dict:
    """Build a v9-style entry from one Reports row/sub-entry."""
    start = src.get("start") or row_common.get("start")
    stop = src.get("stop") or src.get("end")
    duration = src.get("seconds")
    if duration is None:
        duration = src.get("duration", 0)

    tag_ids = src.get("tag_ids") or row_common.get("tag_ids") or []
    tag_ids = [t for t in tag_ids if t is not None]
    tags = [tag_map[t] for t in tag_ids if t in tag_map]

    workspace_id = src.get("workspace_id") or row_common["workspace_id"]
    project_id = src.get("project_id", row_common.get("project_id"))
    task_id = src.get("task_id", row_common.get("task_id"))
    user_id = src.get("user_id", row_common.get("user_id"))
    billable = bool(src.get("billable", row_common["billable"]))

    return {
        "id": src["id"],
        "workspace_id": workspace_id,
        "project_id": project_id,
        "task_id": task_id,
        "billable": billable,
        "start": start,
        "stop": stop,
        "duration": int(duration) if duration is not None else 0,
        "tags": tags,
        "tag_ids": tag_ids,
        "duronly": True,
        "at": src.get("at"),
        "server_deleted_at": None,
        "user_id": user_id,
        "uid": user_id,
        "wid": workspace_id,
        "pid": project_id,
        "tid": task_id,
    }


# ---------------------------------------------------------------------------
# History I/O & merge
# ---------------------------------------------------------------------------
def empty_history(workspace_name: str, workspace_id: int) -> dict:
    return {
        "version": HISTORY_VERSION,
        "workspace_name": workspace_name,
        "workspace_id": workspace_id,
        "first_entry_start": None,
        "last_entry_start": None,
        "last_backfill_at": None,
        "last_incremental_at": None,
        "total_entries": 0,
        "raw_entries": [],
    }


def load_history() -> dict | None:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return None


def strip_description(entries: list) -> list:
    for e in entries:
        if "description" in e:
            del e["description"]
    return entries


def entry_start_date_str(entry: dict) -> str:
    s = entry.get("start") or ""
    return s.split("T", 1)[0] if s else ""


def merge_authoritative_window(
    history: dict,
    fresh_entries: list,
    window_start: datetime,
    window_end: datetime,
) -> dict:
    """
    Replace ALL existing history entries whose start is in
    [window_start, window_end] with `fresh_entries` (which is the
    authoritative source for that window).

    This catches edits AND deletions inside the recent window.
    """
    start_iso = window_start.strftime("%Y-%m-%d")
    end_iso = window_end.strftime("%Y-%m-%d")

    kept = [
        e
        for e in history["raw_entries"]
        if not (start_iso <= entry_start_date_str(e) <= end_iso)
    ]

    fresh_clean = strip_description(list(fresh_entries))
    deduped: dict = {}
    for e in fresh_clean:
        deduped[e["id"]] = e

    merged = kept + list(deduped.values())
    merged.sort(key=lambda e: e.get("start") or "")

    history["raw_entries"] = merged
    history["total_entries"] = len(merged)
    if merged:
        history["first_entry_start"] = merged[0].get("start")
        history["last_entry_start"] = merged[-1].get("start")
    else:
        history["first_entry_start"] = None
        history["last_entry_start"] = None
    return history


def merge_additive(history: dict, fresh_entries: list) -> dict:
    """
    Add entries that are NOT already in history (by id). Existing entries
    are left untouched. Used by the backfill, where the older window is
    immutable from our perspective.
    """
    existing_ids = {e["id"] for e in history["raw_entries"]}
    fresh_clean = strip_description(list(fresh_entries))

    added = 0
    for e in fresh_clean:
        if e["id"] not in existing_ids:
            history["raw_entries"].append(e)
            existing_ids.add(e["id"])
            added += 1

    history["raw_entries"].sort(key=lambda e: e.get("start") or "")
    history["total_entries"] = len(history["raw_entries"])
    if history["raw_entries"]:
        history["first_entry_start"] = history["raw_entries"][0].get("start")
        history["last_entry_start"] = history["raw_entries"][-1].get("start")
    return history, added


def write_history(history: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
