from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import asyncpg


@dataclass(frozen=True)
class DiscussionMessage:
    id: int
    event_id: int
    user_id: int
    username: str | None
    message: str
    created_at: datetime


class DiscussionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_messages(self, event_id: int, limit: int = 20) -> Sequence[DiscussionMessage]:
        query = """
        SELECT d.id,
               d.event_id,
               d.user_id,
               u.username,
               d.message,
               d.created_at
        FROM discussions AS d
        JOIN users AS u ON u.id = d.user_id
        WHERE d.event_id = $1
        ORDER BY d.created_at DESC
        LIMIT $2
        """
        rows = await self._pool.fetch(query, event_id, limit)
        return [
            DiscussionMessage(
                id=row["id"],
                event_id=row["event_id"],
                user_id=row["user_id"],
                username=row["username"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def add_message(self, event_id: int, user_id: int, message: str) -> None:
        query = """
        INSERT INTO discussions (event_id, user_id, message)
        VALUES ($1, $2, $3)
        """
        await self._pool.execute(query, event_id, user_id, message)

