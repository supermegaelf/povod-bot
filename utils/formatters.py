from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import textwrap

from database.repositories.events import Event
from services.registration_service import Availability
from utils.i18n import t


def format_event_summary(event: Event) -> str:
    if event.time:
        event_datetime = datetime.combine(event.date, event.time)
        moment_line = t("event.summary.datetime", datetime=event_datetime.strftime(t("format.display_datetime")))
    else:
        moment_line = t("event.summary.date", date=event.date.strftime(t("format.display_date")))
    lines = [
        t("event.summary.header", title=event.title),
        moment_line,
    ]
    if event.place:
        lines.append(t("event.summary.place", place=event.place))
    if event.cost is not None:
        if event.cost > 0:
            lines.append(t("event.summary.cost", cost=_format_cost(event.cost)))
        elif event.cost == 0:
            lines.append(t("event.summary.cost_free"))
    return "\n".join(lines)


def format_event_card(event: Event, availability: Availability | None = None) -> str:
    lines: list[str] = [t("event.card.header", title=event.title)]

    if event.description:
        lines.append("")
        lines.append(_format_description(event.description))

    detail_lines: list[str] = []

    if event.date and event.time:
        event_datetime = datetime.combine(event.date, event.time)
        detail_lines.append(t("event.card.date", date=event_datetime.strftime(t("format.display_date"))))
        detail_lines.append(t("event.card.time", time=event_datetime.strftime(t("format.display_time"))))
    elif event.date:
        detail_lines.append(t("event.card.date", date=event.date.strftime(t("format.display_date"))))
    if event.place:
        detail_lines.append(t("event.card.place", place=event.place))

    if event.cost is not None:
        if event.cost > 0:
            detail_lines.append(t("event.card.cost", cost=_format_cost(event.cost)))
        elif event.cost == 0:
            detail_lines.append(t("event.card.cost_free"))

    if availability is not None:
        if availability.capacity is None:
            detail_lines.append(t("event.card.capacity_unlimited"))
        else:
            detail_lines.append(
                t(
                    "event.card.capacity",
                    free=availability.free,
                    capacity=availability.capacity,
                )
            )

    if detail_lines:
        lines.append("")
        lines.extend(detail_lines)

    return "\n".join(lines)


def _format_cost(value: float | None) -> str:
    if value is None:
        return "0"
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cost_str = format(decimal_value, "f")
    if "." in cost_str:
        cost_str = cost_str.rstrip("0").rstrip(".")
    return cost_str or "0"


def _format_description(text: str, width: int = 60) -> str:
    paragraphs = text.splitlines()
    wrapped: list[str] = []
    for paragraph in paragraphs:
        chunk = paragraph.strip()
        if not chunk:
            wrapped.append("")
            continue
        if "<" in chunk and ">" in chunk:
            wrapped.append(chunk)
            continue
        wrapped.append("\n".join(textwrap.wrap(chunk, width=width, break_long_words=False, break_on_hyphens=False)) or chunk)
    return "\n".join(wrapped).strip()

