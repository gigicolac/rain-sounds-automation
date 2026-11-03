"""Choose the YouTube scheduled release time from data/publish_schedule.json.

Build jobs are anchored 28 hours before the fixed Eastern release slots.
Uploads stay private until processing succeeds, then receive a publishAt
at least 24 hours after transfer. A short lead delays the intended release instead of
skipping it. Occupied release days remain reserved for their existing video.
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


def next_publish_at(now=None, schedule=None, excluded=(), intended=None, uploaded_at=None):
    """Keep the next intended slot, delaying only enough to meet the lead time."""
    schedule = schedule or load_schedule()
    zone = ZoneInfo(schedule["timezone"])
    now = now or datetime.now(timezone.utc)
    earliest = (uploaded_at or now) + timedelta(minutes=max(1440, schedule.get("minimum_lead_minutes", 1440)))
    if uploaded_at is not None:
        earliest = max(earliest, now + timedelta(minutes=1))
    excluded = set(excluded)
    local_today = (intended or now).astimezone(zone).date()
    occupied_days = {moment.astimezone(zone).date() for moment in excluded}
    for offset in range(8):
        day = local_today + timedelta(days=offset)
        if DAYS[day.weekday()] not in schedule.get('days', DAYS):
            continue
        slot = datetime.combine(day, time.fromisoformat(schedule["times"][DAYS[day.weekday()]]), zone)
        slot = slot.astimezone(timezone.utc)
        if day in occupied_days or (intended is None and slot < now):
            continue
        release = max(slot, earliest)
        if release.astimezone(zone).date() in occupied_days:
            continue
        return release
    raise RuntimeError("No release time found in the next week")


def api_timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
