from dataclasses import dataclass
from typing import Optional

import asyncpg


@dataclass
class User:
    id: int
    telegram_id: int
    username: Optional[str]
    role: str


class UserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        query = "SELECT id, telegram_id, username, role FROM users WHERE telegram_id = $1"
        record = await self._pool.fetchrow(query, telegram_id)
        if record is None:
            return None
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
        )

    async def create(self, telegram_id: int, username: Optional[str], role: str = "user") -> User:
        query = """
        INSERT INTO users (telegram_id, username, role)
        VALUES ($1, $2, $3)
        RETURNING id, telegram_id, username, role
        """
        record = await self._pool.fetchrow(query, telegram_id, username, role)
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
        )

    async def update_role(self, user_id: int, role: str) -> None:
        query = "UPDATE users SET role = $1 WHERE id = $2"
        await self._pool.execute(query, role, user_id)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        query = "SELECT id, telegram_id, username, role FROM users WHERE id = $1"
        record = await self._pool.fetchrow(query, user_id)
        if record is None:
            return None
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
        )

    async def list_all_telegram_ids(self) -> list[int]:
        query = "SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL"
        rows = await self._pool.fetch(query)
        return [row["telegram_id"] for row in rows]

