from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg


@dataclass
class BotMessage:
    id: int
    user_id: int
    chat_id: int
    message_id: int
    sent_at: datetime


class BotMessageRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(self, user_id: int, chat_id: int, message_id: int) -> None:
        query = """
        INSERT INTO bot_messages (user_id, chat_id, message_id, sent_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (chat_id, message_id) DO NOTHING
        """
        await self._pool.execute(query, user_id, chat_id, message_id)

    async def get_by_user_id(self, user_id: int, limit: int = 100) -> list[BotMessage]:
        query = """
        SELECT id, user_id, chat_id, message_id, sent_at
        FROM bot_messages
        WHERE user_id = $1
        ORDER BY sent_at DESC
        LIMIT $2
        """
        rows = await self._pool.fetch(query, user_id, limit)
        return [
            BotMessage(
                id=row["id"],
                user_id=row["user_id"],
                chat_id=row["chat_id"],
                message_id=row["message_id"],
                sent_at=row["sent_at"],
            )
            for row in rows
        ]

    async def get_by_chat_id(self, chat_id: int, limit: int = 100) -> list[BotMessage]:
        query = """
        SELECT id, user_id, chat_id, message_id, sent_at
        FROM bot_messages
        WHERE chat_id = $1
        ORDER BY sent_at DESC
        LIMIT $2
        """
        rows = await self._pool.fetch(query, chat_id, limit)
        return [
            BotMessage(
                id=row["id"],
                user_id=row["user_id"],
                chat_id=row["chat_id"],
                message_id=row["message_id"],
                sent_at=row["sent_at"],
            )
            for row in rows
        ]

    async def delete_by_ids(self, message_ids: list[tuple[int, int]]) -> None:
        if not message_ids:
            return
        for chat_id, message_id in message_ids:
            query = """
            DELETE FROM bot_messages
            WHERE chat_id = $1 AND message_id = $2
            """
            await self._pool.execute(query, chat_id, message_id)

    async def delete_old_messages(self, older_than_hours: int = 48) -> int:
        query = """
        DELETE FROM bot_messages
        WHERE sent_at < NOW() - INTERVAL '1 hour' * $1
        """
        result = await self._pool.execute(query, older_than_hours)
        return int(result.split()[-1]) if result else 0

    async def get_recent_by_chat_id(self, chat_id: int, hours: int = 48) -> list[BotMessage]:
        query = """
        SELECT id, user_id, chat_id, message_id, sent_at
        FROM bot_messages
        WHERE chat_id = $1 AND sent_at > NOW() - INTERVAL '1 hour' * $2
        ORDER BY sent_at DESC
        """
        rows = await self._pool.fetch(query, chat_id, hours)
        return [
            BotMessage(
                id=row["id"],
                user_id=row["user_id"],
                chat_id=row["chat_id"],
                message_id=row["message_id"],
                sent_at=row["sent_at"],
            )
            for row in rows
        ]

