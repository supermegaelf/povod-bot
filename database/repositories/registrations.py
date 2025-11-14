from dataclasses import dataclass
from typing import Optional

import asyncpg

from utils.constants import STATUS_GOING, STATUS_NOT_GOING


@dataclass(frozen=True)
class RegistrationStats:
    going: int
    not_going: int


@dataclass(frozen=True)
class Participant:
    user_id: int
    telegram_id: Optional[int]
    username: Optional[str]


class RegistrationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_stats(self, event_id: int) -> RegistrationStats:
        query = """
        SELECT
            COUNT(*) FILTER (WHERE status = $2) AS going,
            COUNT(*) FILTER (WHERE status = $3) AS not_going
        FROM registrations
        WHERE event_id = $1
        """
        record = await self._pool.fetchrow(query, event_id, STATUS_GOING, STATUS_NOT_GOING)
        going = record["going"] or 0
        not_going = record["not_going"] or 0
        return RegistrationStats(going=going, not_going=not_going)

    async def list_participant_telegram_ids(self, event_id: int, status: str = STATUS_GOING) -> list[int]:
        query = """
        SELECT u.telegram_id
        FROM registrations AS r
        JOIN users AS u ON u.id = r.user_id
        WHERE r.event_id = $1 AND r.status = $2 AND u.telegram_id IS NOT NULL
        """
        rows = await self._pool.fetch(query, event_id, status)
        return [row["telegram_id"] for row in rows]

    async def list_participants(self, event_id: int) -> list[Participant]:
        query = """
        SELECT u.id AS user_id, u.telegram_id, u.username
        FROM registrations AS r
        JOIN users AS u ON u.id = r.user_id
        WHERE r.event_id = $1 AND r.status = $2
        ORDER BY r.registered_at ASC
        """
        rows = await self._pool.fetch(query, event_id, STATUS_GOING)
        return [
            Participant(
                user_id=row["user_id"],
                telegram_id=row["telegram_id"],
                username=row["username"],
            )
            for row in rows
        ]

    async def remove_participant(self, event_id: int, user_id: int) -> None:
        query = """
        DELETE FROM registrations
        WHERE event_id = $1 AND user_id = $2
        """
        await self._pool.execute(query, event_id, user_id)

    async def add_participant(self, event_id: int, user_id: int, status: str = STATUS_GOING) -> None:
        query = """
        INSERT INTO registrations (event_id, user_id, status)
        VALUES ($1, $2, $3)
        ON CONFLICT (event_id, user_id) DO UPDATE SET status = $3
        """
        await self._pool.execute(query, event_id, user_id, status)

