import os
from dataclasses import dataclass
from datetime import time
from typing import Sequence

from dotenv import load_dotenv


@dataclass(frozen=True)
class BotConfig:
    token: str
    admin_ids: Sequence[int]


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str


@dataclass(frozen=True)
class CommunityLinks:
    channel_main: str
    channel_reading: str
    channel_ride: str
    chat_social: str
    chat_discuss: str


@dataclass(frozen=True)
class SupportLinks:
    question_url: str


@dataclass(frozen=True)
class SingleReminderConfig:
    offset_minutes: int | None
    offset_days: int
    send_time: time


@dataclass(frozen=True)
class ReminderConfig:
    rule_3: SingleReminderConfig
    rule_1: SingleReminderConfig


@dataclass(frozen=True)
class Config:
    bot: BotConfig
    database: DatabaseConfig
    community: CommunityLinks
    support: SupportLinks
    reminders: ReminderConfig


def _parse_admin_ids(raw: str | None) -> Sequence[int]:
    if not raw:
        return ()
    result: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        result.append(int(chunk))
    return tuple(result)


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS"))
    community = CommunityLinks(
        channel_main=_require_env("COMMUNITY_CHANNEL_MAIN_URL"),
        channel_reading=_require_env("COMMUNITY_CHANNEL_READING_URL"),
        channel_ride=_require_env("COMMUNITY_CHANNEL_RIDE_URL"),
        chat_social=_require_env("COMMUNITY_CHAT_SOCIAL_URL"),
        chat_discuss=_require_env("COMMUNITY_CHAT_DISCUSS_URL"),
    )
    support = SupportLinks(
        question_url=_require_env("EVENT_QUESTION_URL"),
    )
    reminders = ReminderConfig(
        rule_3=_parse_reminder_rule(prefix="3", default_days=3),
        rule_1=_parse_reminder_rule(prefix="1", default_days=1),
    )
    return Config(
        bot=BotConfig(token=token, admin_ids=admin_ids),
        database=DatabaseConfig(dsn=dsn),
        community=community,
        support=support,
        reminders=reminders,
    )


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"{key} is not set")
    return value


def _parse_reminder_rule(prefix: str, default_days: int) -> SingleReminderConfig:
    minutes_key = f"REMINDER_OFFSET_{prefix}_MINUTES"
    minutes_raw = os.getenv(minutes_key)
    offset_minutes: int | None = None
    if minutes_raw:
        offset_minutes = _parse_positive_int(minutes_raw, minutes_key)

    if offset_minutes is not None:
        # Minutes override days/time settings for quick testing.
        return SingleReminderConfig(offset_minutes=offset_minutes, offset_days=default_days, send_time=time(hour=19, minute=0))

    days_key = f"REMINDER_OFFSET_{prefix}_DAYS"
    time_key = f"REMINDER_OFFSET_{prefix}_TIME"

    days_raw = os.getenv(days_key)
    offset_days = default_days if not days_raw else _parse_non_negative_int(days_raw, days_key)

    time_raw = os.getenv(time_key)
    send_time = _parse_time_value(time_raw, default=time(hour=19, minute=0))

    return SingleReminderConfig(offset_minutes=None, offset_days=offset_days, send_time=send_time)


def _parse_positive_int(raw: str, key: str) -> int:
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{key} must be an integer") from error
    if value <= 0:
        raise RuntimeError(f"{key} must be greater than zero")
    return value


def _parse_non_negative_int(raw: str, key: str) -> int:
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{key} must be an integer") from error
    if value < 0:
        raise RuntimeError(f"{key} must be zero or positive")
    return value


def _parse_time_value(raw: str | None, default: time) -> time:
    if not raw:
        return default
    try:
        hours, minutes = raw.split(":", 1)
        return time(hour=int(hours), minute=int(minutes))
    except (ValueError, TypeError) as error:
        raise RuntimeError("Time value must be in HH:MM format") from error

