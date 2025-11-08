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
class Config:
    bot: BotConfig
    database: DatabaseConfig


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
    return Config(
        bot=BotConfig(token=token, admin_ids=admin_ids),
        database=DatabaseConfig(dsn=dsn),
    )

