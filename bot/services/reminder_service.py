from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from config import ReminderConfig
from bot.database.repositories.events import Event
from bot.keyboards import event_link_keyboard
from bot.services.event_service import EventService
from bot.services.registration_service import RegistrationService
from bot.utils.i18n import t


@dataclass(frozen=True)
class ReminderRule:
    enabled_attr: str
    sent_attr: str
    text_key: str
    fallback_text_key: str | None = None
    offset_minutes: int | None
    offset_days: int
    send_time: time


class ReminderService:
    def __init__(
        self,
        events: EventService,
        registrations: RegistrationService,
        reminder_config: ReminderConfig,
        timezone: ZoneInfo | None = None,
    ) -> None:
        self._events = events
        self._registrations = registrations
        self._timezone = timezone or ZoneInfo("Europe/Moscow")
        self._default_time = time(hour=19, minute=0)
        self._schedule = {
            "3days": ReminderRule(
                enabled_attr="reminder_3days",
                sent_attr="reminder_3days_sent_at",
                text_key="notify.reminder_3days",
                fallback_text_key=None,
                offset_minutes=reminder_config.rule_3.offset_minutes,
                offset_days=reminder_config.rule_3.offset_days,
                send_time=reminder_config.rule_3.send_time,
            ),
            "1day": ReminderRule(
                enabled_attr="reminder_1day",
                sent_attr="reminder_1day_sent_at",
                text_key="notify.reminder_1day",
                fallback_text_key="notify.reminder_1day_fallback",
                offset_minutes=reminder_config.rule_1.offset_minutes,
                offset_days=reminder_config.rule_1.offset_days,
                send_time=reminder_config.rule_1.send_time,
            ),
        }

    async def process_due_reminders(self, bot: Bot, now: datetime | None = None) -> None:
        current = now.astimezone(self._timezone) if now else datetime.now(self._timezone)
        candidates = await self._events.list_reminder_candidates()
        for event in candidates:
            due_marks: list[str] = []
            for key, rule in self._schedule.items():
                enabled = getattr(event, rule.enabled_attr)
                already_sent = getattr(event, rule.sent_attr)
                if enabled and already_sent is None and self._is_due(event, rule, current):
                    due_marks.append(key)
            if not due_marks:
                continue
            recipients = await self._registrations.list_participant_telegram_ids(event.id)
            for mark in due_marks:
                await self._send_reminder(bot, event, self._schedule[mark], recipients)
            await self._mark_sent(event, due_marks, current)

    def _is_due(self, event: Event, rule: ReminderRule, current: datetime) -> bool:
        if rule.offset_minutes is not None:
            event_time = event.time or self._default_time
            event_datetime = datetime.combine(event.date, event_time, tzinfo=self._timezone)
            scheduled = event_datetime - timedelta(minutes=rule.offset_minutes)
        else:
            target_date = event.date - timedelta(days=rule.offset_days)
            send_time = rule.send_time or self._default_time
            scheduled = datetime.combine(target_date, send_time, tzinfo=self._timezone)
        return current >= scheduled

    async def _send_reminder(
        self,
        bot: Bot,
        event: Event,
        rule: ReminderRule,
        recipients: list[int],
    ) -> None:
        time_display = event.time.strftime(t("format.display_time")) if event.time else None
        text_key = rule.text_key
        if not time_display and rule.fallback_text_key:
            text_key = rule.fallback_text_key
        text = t(text_key, title=event.title, time=time_display)
        markup = event_link_keyboard(event.id)
        for telegram_id in recipients:
            try:
                await bot.send_message(telegram_id, text, reply_markup=markup)
            except Exception:
                continue

    async def _mark_sent(self, event: Event, marks: list[str], current: datetime) -> None:
        payload: dict[str, datetime | None] = {}
        naive_timestamp = current.astimezone(self._timezone).replace(tzinfo=None)
        for mark in marks:
            rule = self._schedule[mark]
            payload[rule.sent_attr] = naive_timestamp
        if payload:
            await self._events.update_event(event.id, payload)


def build_reminder_service(
    events: EventService,
    registrations: RegistrationService,
    reminder_config: ReminderConfig,
) -> ReminderService:
    return ReminderService(
        events,
        registrations,
        reminder_config=reminder_config,
    )

