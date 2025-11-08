from datetime import datetime

from database.repositories.events import Event
from database.repositories.registrations import RegistrationStats
from services.registration_service import Availability
from utils.i18n import t


def format_event_summary(event: Event) -> str:
    event_datetime = datetime.combine(event.date, event.time)
    datetime_str = event_datetime.strftime(t("format.display_datetime"))
    cost_value = f"{event.cost:.2f}"
    cost_line = (
        t("event.summary.cost", cost=cost_value)
        if event.cost and event.cost > 0
        else t("event.summary.cost_free")
    )
    lines = [
        t("event.summary.header", title=event.title),
        t("event.summary.datetime", datetime=datetime_str),
        t("event.summary.place", place=event.place),
        cost_line,
    ]
    return "\n".join(lines)


def format_event_card(event: Event, stats: RegistrationStats, availability: Availability) -> str:
    event_datetime = datetime.combine(event.date, event.time)
    date_str = event_datetime.strftime(t("format.display_date"))
    time_str = event_datetime.strftime(t("format.display_time"))
    lines = [
        t("event.card.header", title=event.title),
        t("event.card.date", date=date_str),
        t("event.card.time", time=time_str),
        t("event.card.place", place=event.place),
    ]
    if event.description:
        lines.append("")
        lines.append(t("event.card.description", description=event.description))
    if event.cost and event.cost > 0:
        lines.append("")
        lines.append(t("event.card.cost", cost=f"{event.cost:.2f}"))
    else:
        lines.append("")
        lines.append(t("event.card.cost_free"))
    if availability.capacity is None:
        lines.append(t("event.card.capacity_unlimited"))
    else:
        lines.append(
            t(
                "event.card.capacity",
                free=availability.free,
                capacity=availability.capacity,
            )
        )
    lines.append("")
    lines.append(t("event.card.going", count=stats.going))
    lines.append(t("event.card.not_going", count=stats.not_going))
    return "\n".join(lines)

