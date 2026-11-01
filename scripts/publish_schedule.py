"""Choose the YouTube scheduled release time from data/publish_schedule.json.

Build jobs are anchored 28 hours before the fixed Eastern release slots.
Uploads stay private until processing succeeds, then receive a publishAt
at least 24 hours ahead. Delayed jobs skip slots that are too close or occupied.
"""
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SCHEDULE_PATH = ROOT / "data" / "publish_schedule.json"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def load_schedule(path=SCHEDULE_PATH):
    schedule = json.loads(Path(path).read_text(encoding="utf-8"))
    times = schedule["times"]
    if sorted(times) != sorted(DAYS):
        raise ValueError("publish_schedule.json must define a time for every weekday")
    for value in times.values():
        time.fromisoformat(value)
    ZoneInfo(schedule["timezone"])
    days = schedule.get('days', DAYS)
    if not days or len(days) != len(set(days)) or any(day not in DAYS for day in days):
        raise ValueError('Release days must be distinct weekday names')
    return schedule


def next_publish_at(now=None, schedule=None, excluded=()):
    """Next configured release time (UTC) at least the minimum lead ahead of now."""
    schedule = schedule or load_schedule()
    zone = ZoneInfo(schedule["timezone"])
    now = now or datetime.now(timezone.utc)
    earliest = now + timedelta(minutes=max(1440, schedule.get("minimum_lead_minutes", 1440)))
    excluded = set(excluded)
    local_today = now.astimezone(zone).date()
    for offset in range(8):
        day = local_today + timedelta(days=offset)
        if DAYS[day.weekday()] not in schedule.get('days', DAYS):
            continue
        slot = datetime.combine(day, time.fromisoformat(schedule["times"][DAYS[day.weekday()]]), zone)
        if slot >= earliest and slot.astimezone(timezone.utc) not in excluded:
            return slot.astimezone(timezone.utc)
    raise RuntimeError("No release time found in the next week")


def api_timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
