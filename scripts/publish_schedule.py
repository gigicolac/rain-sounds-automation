"""Publish when the US audience is online, after YouTube has had time to finish HD processing."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
# Recommended posting windows in US Eastern time, Monday=0.
WINDOWS = {
    0: [(time(12), time(16))],
    1: [(time(13), time(19))],
    2: [(time(12), time(21))],
    3: [(time(9), time(14))],
    4: [(time(11), time(15))],
    5: [(time(9), time(12)), (time(21), time(23))],
    6: [(time(9), time(12)), (time(21), time(23))],
}
# HD/4K renditions plus copyright and ad-suitability checks take about two hours.
PROCESSING_LEAD = timedelta(hours=2)
MINIMUM_REMAINING = timedelta(minutes=30)


def _round_up_quarter_hour(moment):
    floored = moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)
    return floored if floored == moment else floored + timedelta(minutes=15)


def next_publish_time(now=None, lead=PROCESSING_LEAD):
    """Earliest moment inside a posting window that is at least `lead` from now, in UTC."""
    now = now or datetime.now(timezone.utc)
    earliest = _round_up_quarter_hour((now + lead).astimezone(EASTERN))
    for offset in range(8):
        day = earliest.date() + timedelta(days=offset)
        for start, end in WINDOWS[day.weekday()]:
            opens = datetime.combine(day, start, EASTERN)
            closes = datetime.combine(day, end, EASTERN)
            candidate = max(opens, earliest)
            if candidate + MINIMUM_REMAINING <= closes:
                return candidate.astimezone(timezone.utc)
    raise RuntimeError('No posting window found in the next week')


def rfc3339(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
