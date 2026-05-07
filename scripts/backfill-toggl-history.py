#!/usr/bin/env python3
"""
One-shot Toggl history backfill via Reports API v3.

Walks back from yesterday in 365-day windows, paginating within each window,
normalizes the response to the v9 entry shape, and merges everything into
`data/raw_history.json` (additively — existing entries are preserved).

After the backfill, `data/raw_data.json` is re-derived as the last 90 days
slice so the existing dashboard keeps working.

Environment
-----------
- TOGGL_API_TOKEN       (required)
- TOGGL_WORKSPACE       (default: "DRE-P")
- BACKFILL_START_DATE   (optional, "YYYY-MM-DD")  -- earliest date to backfill.
                         Default: 2010-01-01 (covers any realistic Toggl history).
                         The script also stops automatically as soon as a year-window
                         comes back empty.
- BACKFILL_PAGE_SIZE    (optional, default 200, max 1000 per Toggl docs)
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _toggl_common as tc  # noqa: E402

WINDOW_DAYS = 365  # walk-back window size (Reports v3 typically caps ~1 year)
DEFAULT_FLOOR = "2010-01-01"  # safety floor — Toggl was founded in 2006


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def main() -> int:
    api_token = os.getenv("TOGGL_API_TOKEN")
    workspace_name = os.getenv("TOGGL_WORKSPACE", "DRE-P")
    floor_str = os.getenv("BACKFILL_START_DATE", "").strip() or DEFAULT_FLOOR
    page_size = int(os.getenv("BACKFILL_PAGE_SIZE", "200") or "200")

    if not api_token:
        print("❌ TOGGL_API_TOKEN is required.")
        return 1

    floor_dt = _parse_date(floor_str)
    print(
        f"🚀 DebateSettler BACKFILL  workspace='{workspace_name}'  "
        f"earliest={floor_str}  page_size={page_size}"
    )

    headers = tc.make_auth_headers(api_token)
    workspace_id = tc.get_workspace_id(headers, workspace_name)
    print(f"📡 Workspace id: {workspace_id}")

    tag_map = tc.get_workspace_tags_map(headers, workspace_id)
    print(f"🏷  Loaded {len(tag_map)} workspace tag(s)")

    # Load existing history (or start fresh)
    history = tc.load_history() or tc.empty_history(workspace_name, workspace_id)
    if history.get("workspace_id") != workspace_id:
        history["workspace_id"] = workspace_id
    if history.get("workspace_name") != workspace_name:
        history["workspace_name"] = workspace_name

    # Walk back: end_date = yesterday on first iter; subsequent windows step
    # back WINDOW_DAYS each loop. Stop when start_dt <= floor_dt or empty window.
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cur_end = today - timedelta(days=1)

    total_added = 0
    consecutive_empty = 0

    while cur_end >= floor_dt:
        cur_start = max(cur_end - timedelta(days=WINDOW_DAYS - 1), floor_dt)
        print(
            f"\n📅 Window  {cur_start.date()} → {cur_end.date()}  "
            f"(spans {(cur_end - cur_start).days + 1} days)"
        )

        rows = tc.fetch_reports_v3_window(
            headers, workspace_id, cur_start, cur_end, page_size=page_size
        )
        print(f"   • Reports API returned {len(rows)} row(s)")

        v9_entries = tc.normalize_reports_entries(rows, workspace_id, tag_map)
        print(f"   • Normalized to {len(v9_entries)} v9-shape entr(y/ies)")

        history, added = tc.merge_additive(history, v9_entries)
        total_added += added
        print(f"   • Added {added} new entries (history total now {history['total_entries']})")

        # Stop early: two consecutive empty windows ⇒ assume start of history reached
        if len(rows) == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print("✓ Two consecutive empty windows — stopping early.")
                break
        else:
            consecutive_empty = 0

        if cur_start <= floor_dt:
            break

        # Next window: end the day BEFORE cur_start to avoid overlap
        cur_end = cur_start - timedelta(days=1)
        time.sleep(0.4)  # polite gap between windows

    history["last_backfill_at"] = datetime.now().isoformat()

    tc.write_history(history)
    print(
        f"\n💾 Wrote {tc.HISTORY_FILE}: {history['total_entries']} total entries "
        f"({history['first_entry_start']} → {history['last_entry_start']}); "
        f"+{total_added} new from this backfill"
    )

    derived = tc.derive_raw_data(history)
    tc.write_raw_data(derived)
    print(
        f"💾 Wrote {tc.RAW_DATA_FILE}: {derived['total_entries']} entries "
        f"(window {derived['date_range']['start']} → {derived['date_range']['end']})"
    )

    print("🎉 Backfill complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
