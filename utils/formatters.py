from datetime import datetime

from typing import Sequence

from database.repositories.discussions import DiscussionMessage
from database.repositories.events import Event
from database.repositories.registrations import Participant, RegistrationStats
from services.registration_service import Availability
from utils.i18n import t
from utils.constants import STATUS_GOING, STATUS_NOT_GOING


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


def format_discussion(messages: Sequence[DiscussionMessage], event_title: str) -> str:
    if not messages:
        return t("discussion.empty", title=event_title)
    lines: list[str] = [t("discussion.header", title=event_title)]
    for message in reversed(messages):
        author = message.username or t("discussion.anonymous", id=message.user_id)
        timestamp = message.created_at.strftime(t("format.display_datetime"))
        lines.append("")
        lines.append(f"<b>{author}</b> — {timestamp}")
        lines.append(message.message)
    return "\n".join(lines)


def format_participants(participants: Sequence[Participant], event_title: str) -> str:
    if not participants:
        return t("participants.empty", title=event_title)
    going: list[str] = []
    not_going: list[str] = []
    for participant in participants:
        name = participant.username or t("participants.anonymous", id=participant.user_id)
        line = f"- {name}"
        if participant.status == STATUS_GOING:
            going.append(line)
        elif participant.status == STATUS_NOT_GOING:
            not_going.append(line)
        else:
            going.append(line)

    sections: list[tuple[str, list[str]]] = []
    if going:
        sections.append((t("participants.going"), going))
    if not_going:
        sections.append((t("participants.not_going"), not_going))

    lines: list[str] = [t("participants.header", title=event_title)]
    for title, names in sections:
        lines.append("")
        lines.append(f"<b>{title}</b>")
        lines.extend(names)
    return "\n".join(lines)

