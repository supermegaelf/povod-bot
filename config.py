import os
from dataclasses import dataclass
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
class Config:
    bot: BotConfig
    database: DatabaseConfig
    community: CommunityLinks
    support: SupportLinks


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
    return Config(
        bot=BotConfig(token=token, admin_ids=admin_ids),
        database=DatabaseConfig(dsn=dsn),
        community=community,
        support=support,
    )


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"{key} is not set")
    return value

