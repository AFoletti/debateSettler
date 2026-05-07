#!/usr/bin/env python3
"""
Daily incremental Toggl fetch.

Behavior
--------
1. Load `data/raw_history.json`. If it doesn't exist:
   - Bootstrap from `data/raw_data.json` if present (no API call needed).
   - Otherwise fetch the last 90 days from v9 and seed the history.

2. Fetch the **last 30 days** from v9 `/me/time_entries`.

3. Replace ALL history entries whose start is inside [today-30d, yesterday]
   with the freshly fetched ones — this captures edits AND deletions in
   the recent window.

4. Re-derive `data/raw_data.json` (last 90 days slice) so the existing
   dashboard + regression tests keep working unchanged.

Environment
-----------
- TOGGL_API_TOKEN  (required for any API call)
- TOGGL_WORKSPACE  (default: "DRE-P")
- BOOTSTRAP_ONLY   (optional; if "1"/"true", skip the API fetch and only
                    perform the seed-from-raw_data + derive steps. Used by
                    the local dry-run test.)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Local sibling import (hyphen in this filename prevents `import` of itself)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _toggl_common as tc  # noqa: E402

DAILY_FETCH_DAYS = 30
SEED_DAYS = 90  # used only when no raw_data.json AND no raw_history.json exists


def _truthy(s: str | None) -> bool:
    return (s or "").strip().lower() in ("1", "true", "yes", "y")


def main() -> int:
    api_token = os.getenv("TOGGL_API_TOKEN")
    workspace_name = os.getenv("TOGGL_WORKSPACE", "DRE-P")
    bootstrap_only = _truthy(os.getenv("BOOTSTRAP_ONLY"))

    print(f"🚀 DebateSettler daily fetch (workspace='{workspace_name}')")
    if bootstrap_only:
        print("   • BOOTSTRAP_ONLY=1 — no API calls, files will be regenerated locally")

    # --- 1. Load or bootstrap history ---------------------------------------
    history = tc.load_history()

    if history is None:
        print("ℹ️  No raw_history.json found — bootstrapping…")
        seeded = tc.seed_from_raw_data(workspace_name, 0)
        if seeded is not None:
            history = seeded
            print(
                f"✓ Seeded history from raw_data.json: "
                f"{history['total_entries']} entries "
                f"({history['first_entry_start']} → {history['last_entry_start']})"
            )
        else:
            if bootstrap_only:
                print(
                    "❌ BOOTSTRAP_ONLY=1 but no raw_data.json to seed from. "
                    "Aborting."
                )
                return 1
            if not api_token:
                print(
                    "❌ No raw_history.json, no raw_data.json, "
                    "and TOGGL_API_TOKEN is not set."
                )
                return 1
            print("• No raw_data.json either — fetching seed data from Toggl…")
            headers = tc.make_auth_headers(api_token)
            wid = tc.get_workspace_id(headers, workspace_name)
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = today - timedelta(days=1)
            start = end - timedelta(days=SEED_DAYS - 1)
            seed_entries = tc.fetch_v9_time_entries(headers, start, end)
            history = tc.empty_history(workspace_name, wid)
            history = tc.merge_authoritative_window(history, seed_entries, start, end)
            print(f"✓ Seeded history from Toggl: {history['total_entries']} entries")

    # --- 2. Daily incremental fetch -----------------------------------------
    if bootstrap_only:
        print("⚙ Skipping daily API fetch (BOOTSTRAP_ONLY=1).")
    else:
        if not api_token:
            print("❌ TOGGL_API_TOKEN required for daily fetch.")
            return 1
        headers = tc.make_auth_headers(api_token)
        if not history.get("workspace_id"):
            history["workspace_id"] = tc.get_workspace_id(headers, workspace_name)

        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = today - timedelta(days=1)
        start_date = end_date - timedelta(days=DAILY_FETCH_DAYS - 1)
        print(
            f"📅 Daily window: {start_date.date()} → {end_date.date()} "
            f"({DAILY_FETCH_DAYS} days)"
        )

        fresh = tc.fetch_v9_time_entries(headers, start_date, end_date)
        print(f"📥 Fetched {len(fresh)} entries from Toggl")

        before = history["total_entries"]
        history = tc.merge_authoritative_window(history, fresh, start_date, end_date)
        delta = history["total_entries"] - before
        print(
            f"🔁 Merged daily window — total entries: {before} → "
            f"{history['total_entries']} ({delta:+d})"
        )

        history["last_incremental_at"] = datetime.now().isoformat()

    # --- 3. Persist ---------------------------------------------------------
    tc.write_history(history)
    print(
        f"💾 Wrote {tc.HISTORY_FILE}: {history['total_entries']} entries "
        f"({history['first_entry_start']} → {history['last_entry_start']})"
    )

    derived = tc.derive_raw_data(history)
    tc.write_raw_data(derived)
    print(
        f"💾 Wrote {tc.RAW_DATA_FILE}: {derived['total_entries']} entries "
        f"(window {derived['date_range']['start']} → {derived['date_range']['end']})"
    )

    print("🎉 Daily fetch complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
