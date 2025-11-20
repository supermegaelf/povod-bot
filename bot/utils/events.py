from datetime import datetime, time


def has_event_started(event) -> bool:
    event_time = event.time or time(0, 0)
    event_start = datetime.combine(event.date, event_time)
    return datetime.now() >= event_start


