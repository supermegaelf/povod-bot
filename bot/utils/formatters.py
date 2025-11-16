from decimal import Decimal, ROUND_HALF_UP
import textwrap

from bot.database.repositories.events import Event
from bot.services.registration_service import Availability
from bot.utils.i18n import t


def format_event_card(event: Event, availability: Availability | None = None, discount: float | None = None) -> str:
    lines: list[str] = [t("event.card.header", title=event.title)]

    if event.description:
        lines.append("")
        lines.append(_format_description(event.description))

    detail_lines: list[str] = []

    detail_lines.extend(_format_schedule(event))
    if event.place:
        detail_lines.append(t("event.card.place", place=event.place))

    if event.cost is not None:
        if event.cost > 0:
            if discount and discount > 0:
                detail_lines.append(
                    t("event.card.cost_with_discount", cost=_format_cost(event.cost), discount=_format_cost(discount))
                )
            else:
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


def _format_schedule(event: Event) -> list[str]:
    lines: list[str] = []
    if event.date:
        start = event.date.strftime(t("format.display_date"))
        if event.end_date and event.end_date != event.date:
            end = event.end_date.strftime(t("format.display_date"))
            lines.append(t("event.card.date_range", start=start, end=end))
        else:
            lines.append(t("event.card.date", date=start))
    if event.time:
        start_time = event.time.strftime(t("format.display_time"))
        if event.end_time and event.end_time != event.time:
            end_time = event.end_time.strftime(t("format.display_time"))
            lines.append(t("event.card.time_range", start=start_time, end=end_time))
        else:
            lines.append(t("event.card.time", time=start_time))
    elif event.end_time:
        end_time = event.end_time.strftime(t("format.display_time"))
        lines.append(t("event.card.time", time=end_time))
    return lines

