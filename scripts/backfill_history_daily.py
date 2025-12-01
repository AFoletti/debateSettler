#!/usr/bin/env python3
"""Backfill long-term daily history from Toggl for charts.

This script is meant to be run manually to build a full history_daily.json
starting from a fixed date, fetching data in 60-day windows up to yesterday.

It reuses the same aggregation rules as the runtime fetch script, but does
NOT touch raw_data.json (it only updates data/history_daily.json).
"""

import os
import json
import base64
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import defaultdict

import requests


def _parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO datetime string from Toggl, handling trailing 'Z'."""
    if not dt_str:
        return None
    try:
        cleaned = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _update_history_daily(time_entries, workspace_name: str, data_dir: Path) -> None:
    """Update data/history_daily.json with per-day aggregates.

    Similar to the logic in fetch-toggl-data.py, but operates on an
    arbitrary set of entries (potentially many years).
    """
    history_path = data_dir / "history_daily.json"

    # Load existing history (if any)
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
            existing_days = {d["date"]: d for d in history.get("daily_metrics", [])}
        except Exception:
            history = {}
            existing_days = {}
    else:
        history = {}
        existing_days = {}

    per_day = defaultdict(list)
    for entry in time_entries:
        duration = entry.get("duration", 0) or 0
        if duration <= 0:
            continue
        start = _parse_iso_datetime(entry.get("start"))
        stop = _parse_iso_datetime(entry.get("stop"))
        if not start:
            continue
        date_str = start.date().isoformat()
        per_day[date_str].append({
            "start": start,
            "stop": stop,
            "duration": duration,
            "billable": bool(entry.get("billable")),
            "tags": entry.get("tags") or [],
        })

    def _minutes_since_midnight(dt: datetime) -> int:
        return dt.hour * 60 + dt.minute

    # Compute metrics for each day
    for date_str, entries in per_day.items():
        if not entries:
            continue

        billable_seconds = sum(e["duration"] for e in entries if e["billable"])
        billable_hours = billable_seconds / 3600.0

        away_seconds = 0
        for e in entries:
            tags = e["tags"]
            if "HomeOffice" not in tags:
                away_seconds += e["duration"]
        away_hours = away_seconds / 3600.0

        # Back home time (last commuting entry end time)
        commuting_entries = [e for e in entries if "Commuting" in e["tags"] and e["stop"]]
        commuting_entries.sort(key=lambda e: e["stop"])
        if commuting_entries:
            last_commuting = commuting_entries[-1]
            back_home_minutes = _minutes_since_midnight(last_commuting["stop"])
            back_home_time = f"{back_home_minutes // 60:02d}:{back_home_minutes % 60:02d}"
        else:
            back_home_time = None

        # HomeOffice end time for pure HomeOffice days
        all_entries = []
        home_office_entries = []
        for e in entries:
            is_home = "HomeOffice" in e["tags"]
            all_entries.append({
                "start": e["start"],
                "stop": e["stop"],
                "is_home": is_home,
                "tags": e["tags"],
            })
            if is_home:
                home_office_entries.append({
                    "start": e["start"],
                    "stop": e["stop"],
                    "tags": e["tags"],
                })

        home_office_end_time = None
        if home_office_entries:
            all_entries.sort(key=lambda e: e["start"])
            home_office_entries.sort(key=lambda e: e["start"])

            last_entry_of_day = all_entries[-1]
            last_home = home_office_entries[-1]

            commuting_for_day = [e for e in all_entries if "Commuting" in e["tags"]]
            commuting_for_day.sort(key=lambda e: e["start"])
            last_commuting_any = commuting_for_day[-1] if commuting_for_day else None

            # Rule 1
            if last_commuting_any and last_home["start"] > last_commuting_any["stop"]:
                home_office_end_time = None
            else:
                # Rule 2
                entries_after_last_home = [
                    e for e in all_entries
                    if e["start"] > last_home["stop"] and not e["is_home"]
                ]
                if entries_after_last_home:
                    home_office_end_time = None
                else:
                    # Rule 3
                    if last_entry_of_day["is_home"]:
                        ho_minutes = _minutes_since_midnight(last_home["stop"])
                        home_office_end_time = f"{ho_minutes // 60:02d}:{ho_minutes % 60:02d}"

        # Late work
        late_work = False
        for e in entries:
            start = e["start"]
            stop = e["stop"]
            if start.hour >= 20 or (stop and stop.hour >= 20):
                late_work = True
                break

        day_record = {
            "date": date_str,
            "billable_hours": round(billable_hours, 2),
            "away_from_home_hours": round(away_hours, 2),
            "back_home_time": back_home_time,
            "home_office_end_time": home_office_end_time,
            "late_work": late_work,
            "total_entries": len(entries),
        }

        existing_days[date_str] = day_record

    if not existing_days:
        return

    all_dates = sorted(existing_days.keys())
    history = {
        "generated_at": datetime.now().isoformat(),
        "date_range": {
            "start": all_dates[0],
            "end": all_dates[-1],
        },
        "workspace_name": workspace_name,
        "daily_metrics": [existing_days[d] for d in all_dates],
    }

    history_path = data_dir / "history_daily.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    print(f"✅ history_daily.json updated with {len(all_dates)} days")


class TogglBackfillFetcher:
    def __init__(self):
        self.api_token = os.getenv("TOGGL_API_TOKEN")
        self.workspace_name = os.getenv("TOGGL_WORKSPACE", "DRE-P")
        self.base_url = "https://api.track.toggl.com/api/v9"

        if not self.api_token:
            raise ValueError("TOGGL_API_TOKEN environment variable is required")

        auth_header = base64.b64encode(f"{self.api_token}:api_token".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json",
        }

    def get_time_entries(self, start_iso: str, end_iso: str):
        params = {
            "start_date": start_iso,
            "end_date": end_iso,
        }
        print(f"📡 Requesting entries from {start_iso} to {end_iso}")
        resp = requests.get(f"{self.base_url}/me/time_entries", headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()


def main():
    fetcher = TogglBackfillFetcher()
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Backfill from 2025-06-01 to yesterday, 60-day windows
    start = date(2025, 6, 1)
    yesterday = datetime.now().date() - timedelta(days=1)
    window_days = 60

    all_entries = []

    current_start = start
    while current_start <= yesterday:
        current_end = current_start + timedelta(days=window_days - 1)
        if current_end > yesterday:
            current_end = yesterday

        start_iso = datetime.combine(current_start, datetime.min.time()).isoformat() + "Z"
        end_iso = datetime.combine(current_end, datetime.max.time()).isoformat() + "Z"

        entries = fetcher.get_time_entries(start_iso, end_iso)
        print(f"  → Retrieved {len(entries)} entries")

        for e in entries:
            if "description" in e:
                del e["description"]
        all_entries.extend(entries)

        current_start = current_end + timedelta(days=1)

    print(f"📊 Total entries across all windows: {len(all_entries)}")

    _update_history_daily(all_entries, fetcher.workspace_name, data_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"❌ Error during backfill: {exc}")
        raise
