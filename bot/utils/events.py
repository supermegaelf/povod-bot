from datetime import datetime, time
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
UTC_TZ = ZoneInfo("UTC")


def get_event_start(event) -> datetime:
    event_time = event.time or time(0, 0)
    return datetime.combine(event.date, event_time, tzinfo=MOSCOW_TZ)


def now_moscow() -> datetime:
    return datetime.now(MOSCOW_TZ)


def has_event_started(event, *, now: datetime | None = None) -> bool:
    current = now or now_moscow()
    return current >= get_event_start(event)


