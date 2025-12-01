#!/usr/bin/env python3
"""Backfill long-term daily history using Toggl Reports API v3.

This script uses the reports endpoint:
  POST https://api.track.toggl.com/reports/api/v3/workspace/{workspace_id}/search/time_entries

It paginates backwards using the X-Next-ID and X-Next-Row-Number headers
until it reaches a given "since" date, then writes/updates
  data/history_daily.json
using the same aggregation rules as the runtime fetch script.

Expected environment:
- TOGGL_API_TOKEN: your Toggl API token
- TOGGL_WORKSPACE: workspace name (defaults to DRE-P)

Usage (example):
  TOGGL_API_TOKEN=... python3 scripts/backfill_reports_history.py
"""

import os
import json
import base64
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

import requests


REPORTS_BASE = "https://api.track.toggl.com/reports/api/v3"
TOGGL_V9_BASE = "https://api.track.toggl.com/api/v9"


def _parse_iso_datetime(dt_str: str | None) -> datetime | None:
  if not dt_str:
    return None
  try:
    cleaned = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)
  except Exception:
    return None


def _minutes_since_midnight(dt: datetime) -> int:
  return dt.hour * 60 + dt.minute


def _build_daily_stats(time_entries):
  """Build per-day stats from raw time entries.

  Returns dict[date_str] -> {
    'billable_hours', 'total_hours', 'away_from_home_hours',
    'back_home_minutes', 'home_office_minutes', 'total_entries'
  }
  """
  per_day_entries = defaultdict(list)
  for entry in time_entries:
    duration = entry.get("duration", 0) or 0
    if duration <= 0:
      continue
    start = _parse_iso_datetime(entry.get("start"))
    stop = _parse_iso_datetime(entry.get("stop"))
    if not start:
      continue
    date_str = start.date().isoformat()
    per_day_entries[date_str].append({
      "start": start,
      "stop": stop,
      "duration": duration,
      "billable": bool(entry.get("billable")),
      "tags": entry.get("tags") or [],
    })

  daily = {}
  for date_str, entries in per_day_entries.items():
    if not entries:
      continue

    # Total and billable hours
    total_seconds = sum(e["duration"] for e in entries)
    billable_seconds = sum(e["duration"] for e in entries if e["billable"])

    # Away-from-home hours (non-HomeOffice)
    away_seconds = 0
    for e in entries:
      tags = e["tags"]
      if "HomeOffice" not in tags:
        away_seconds += e["duration"]

    # Back home time (last commuting entry end time)
    commuting_entries = [e for e in entries if "Commuting" in e["tags"] and e["stop"]]
    commuting_entries.sort(key=lambda e: e["stop"])
    if commuting_entries:
      last_commuting = commuting_entries[-1]
      back_home_minutes = _minutes_since_midnight(last_commuting["stop"])
    else:
      back_home_minutes = None

    # HomeOffice end time (pure HomeOffice day rules)
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

    home_office_minutes = None
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
        home_office_minutes = None
      else:
        # Rule 2
        entries_after_last_home = [
          e for e in all_entries
          if e["start"] > last_home["stop"] and not e["is_home"]
        ]
        if entries_after_last_home:
          home_office_minutes = None
        else:
          # Rule 3
          if last_entry_of_day["is_home"]:
            home_office_minutes = _minutes_since_midnight(last_home["stop"])

    daily[date_str] = {
      "billable_hours": round(billable_seconds / 3600.0, 2),
      "total_hours": round(total_seconds / 3600.0, 2),
      "away_from_home_hours": round(away_seconds / 3600.0, 2),
      "back_home_minutes": back_home_minutes,
      "home_office_minutes": home_office_minutes,
      "total_entries": len(entries),
    }

  return daily


def _compute_rolling_mean(values, window):
  """Simple rolling mean over non-null numeric values."""
  if window <= 1:
    return [None] * len(values)
  res = [None] * len(values)
  nums = [v if isinstance(v, (int, float)) else None for v in values]
  window_vals = []
  sum_val = 0.0
  count = 0
  for i, v in enumerate(nums):
    window_vals.append(v)
    if v is not None:
      sum_val += v
      count += 1
    if len(window_vals) > window:
      old = window_vals.pop(0)
      if old is not None:
        sum_val -= old
        count -= 1
    if count > 0 and len(window_vals) >= window:
      res[i] = sum_val / count
  return res


def _build_weekly_monthly_series(dates, values, freq):
  """Build weekly or monthly aggregates.

  dates: list[date]
  values: list[float|None]
  freq: 'weekly' or 'monthly'
  """
  buckets = {}
  for d, v in zip(dates, values):
    if v is None:
      continue
    if freq == "weekly":
      iso_year, iso_week, _ = d.isocalendar()
      key = (iso_year, iso_week)
    else:
      key = (d.year, d.month)

    bucket = buckets.get(key)
    if not bucket:
      bucket = {
        "sum": 0.0,
        "count": 0,
        "start_date": d,
        "end_date": d,
      }
      buckets[key] = bucket

    bucket["sum"] += v
    bucket["count"] += 1
    if d < bucket["start_date"]:
      bucket["start_date"] = d
    if d > bucket["end_date"]:
      bucket["end_date"] = d

  series = []
  for key, bucket in sorted(buckets.items()):
    if freq == "weekly":
      year, week = key
      period = f"{year}-W{week:02d}"
    else:
      year, month = key
      period = f"{year}-{month:02d}"
    sum_val = bucket["sum"]
    count = bucket["count"]
    mean = sum_val / count if count > 0 else None
    series.append({
      "period": period,
      "start_date": bucket["start_date"].isoformat(),
      "end_date": bucket["end_date"].isoformat(),
      "sum": round(sum_val, 2),
      "mean_per_workday": round(mean, 2) if mean is not None else None,
      "workdays": count,
    })
  return series


def _build_history_charts(daily_stats, workspace_name: str, data_dir: Path) -> None:
  """Build data/history_charts.json from per-day stats."""
  if not daily_stats:
    return

  # Sort dates
  date_strs = sorted(daily_stats.keys())
  dates = [datetime.fromisoformat(d).date() for d in date_strs]

  # Extract per-metric daily series
  def series_for(field):
    return [daily_stats[d].get(field) for d in date_strs]

  billable = series_for("billable_hours")
  total = series_for("total_hours")
  away = series_for("away_from_home_hours")
  back_home = series_for("back_home_minutes")
  ho_end = series_for("home_office_minutes")

  def build_daily_block(values, is_time=False):
    mean7 = _compute_rolling_mean(values, 7)
    mean30 = _compute_rolling_mean(values, 30)
    mean90 = _compute_rolling_mean(values, 90)
    out = []
    for d_str, v, m7, m30, m90 in zip(date_strs, values, mean7, mean30, mean90):
      if v is None:
        # skip days with no value for this metric
        continue
      out.append({
        "date": d_str,
        "value": v,
        "mean_7": m7,
        "mean_30": m30,
        "mean_90": m90,
      })
    return out

  def build_weekly_monthly_blocks(values):
    weekly = _build_weekly_monthly_series(dates, values, "weekly")
    monthly = _build_weekly_monthly_series(dates, values, "monthly")
    return weekly, monthly

  # Build all metrics
  metrics = {}

  # Hours metrics
  for key, values in (
    ("billable_hours", billable),
    ("total_hours", total),
    ("away_from_home_hours", away),
  ):
    daily_block = build_daily_block(values)
    weekly_block, monthly_block = build_weekly_monthly_blocks(values)
    metrics[key] = {
      "unit": "hours",
      "daily": daily_block,
      "weekly": weekly_block,
      "monthly": monthly_block,
    }

  # Time-of-day metrics (minutes since midnight)
  for key, values in (
    ("back_home_time", back_home),
    ("home_office_end_time", ho_end),
  ):
    daily_block = build_daily_block(values, is_time=True)
    weekly_block, monthly_block = build_weekly_monthly_blocks(values)
    metrics[key] = {
      "unit": "minutes_since_midnight",
      "daily": daily_block,
      "weekly": weekly_block,
      "monthly": monthly_block,
    }

  history = {
    "generated_at": datetime.now().isoformat(),
    "date_range": {
      "start": date_strs[0],
      "end": date_strs[-1],
    },
    "workspace_name": workspace_name,
    "metrics": metrics,
  }

  out_path = data_dir / "history_charts.json"
  with open(out_path, "w") as f:
    json.dump(history, f, indent=2)

  print(f"✅ history_charts.json written with range {date_strs[0]} to {date_strs[-1]}")


def _update_history_daily(time_entries, workspace_name: str, data_dir: Path) -> None:
  """(Legacy) Update data/history_daily.json with per-day aggregates.

  Kept for backward compatibility but not used by charts anymore.
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


class ReportsBackfillClient:
  def __init__(self):
    self.api_token = os.getenv("TOGGL_API_TOKEN")
    self.workspace_name = os.getenv("TOGGL_WORKSPACE", "DRE-P")
    if not self.api_token:
      raise ValueError("TOGGL_API_TOKEN environment variable is required")

    auth_header = base64.b64encode(f"{self.api_token}:api_token".encode()).decode()
    self.auth_headers = {
      "Authorization": f"Basic {auth_header}",
      "Content-Type": "application/json",
    }

    # Need workspace_id for reports endpoint
    self.workspace_id = self._resolve_workspace_id()

  def _resolve_workspace_id(self) -> int:
    resp = requests.get(f"{TOGGL_V9_BASE}/workspaces", headers=self.auth_headers)
    resp.raise_for_status()
    for ws in resp.json():
      if ws.get("name") == self.workspace_name:
        print(f"📡 Using workspace '{self.workspace_name}' (id={ws['id']}) for reports backfill")
        return ws["id"]
    raise RuntimeError(f"Workspace '{self.workspace_name}' not found")

  def fetch_time_entries_range(self, start: date, end: date):
    """Fetch all time entries between start and end (inclusive) using reports API.

    Uses POST /workspace/{workspace_id}/search/time_entries with pagination
    via X-Next-ID and X-Next-Row-Number headers.
    """
    all_entries = []

    url = f"{REPORTS_BASE}/workspace/{self.workspace_id}/search/time_entries"
    next_id = None
    next_row = None

    while True:
      body = {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
      }
      if next_id is not None and next_row is not None:
        body["next_id"] = next_id
        body["next_row_number"] = next_row

      print(f"📨 POST {url} with body: {body}")
      resp = requests.post(url, headers=self.auth_headers, data=json.dumps(body))
      try:
        resp.raise_for_status()
      except requests.HTTPError:
        print(f"❌ Reports API error {resp.status_code}: {resp.text}")
        raise
      batch = resp.json()

      if not batch:
        break

      print(f"  → Retrieved {len(batch)} entries")
      all_entries.extend(batch)

      # Pagination headers
      next_id = resp.headers.get("X-Next-ID")
      next_row_header = resp.headers.get("X-Next-Row-Number")
      if not next_id or not next_row_header:
        break
      try:
        next_row = int(next_row_header)
      except ValueError:
        break

    print(f"📊 Total entries from reports API: {len(all_entries)}")
    return all_entries


def main():
  client = ReportsBackfillClient()
  data_dir = Path("data")
  data_dir.mkdir(exist_ok=True)

  # Backfill from 2025-06-01 (inclusive) to 2025-08-31
  start_date = date(2025, 6, 1)
  end_date = date(2025, 8, 31)
  entries = client.fetch_time_entries_range(start_date, end_date)

  # Normalise: remove description if present
  for e in entries:
    if "description" in e:
      del e["description"]

  # Build daily stats and charts history
  daily_stats = _build_daily_stats(entries)
  _build_history_charts(daily_stats, client.workspace_name, data_dir)


if __name__ == "__main__":
  try:
    main()
  except Exception as exc:
    print(f"❌ Error during reports backfill: {exc}")
    raise
