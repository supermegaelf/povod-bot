from dataclasses import dataclass
from typing import Optional

import asyncpg


@dataclass
class User:
    id: int
    telegram_id: int
    username: Optional[str]
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        query = "SELECT id, telegram_id, username, role, first_name, last_name FROM users WHERE telegram_id = $1"
        record = await self._pool.fetchrow(query, telegram_id)
        if record is None:
            return None
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
            first_name=record.get("first_name"),
            last_name=record.get("last_name"),
        )

    async def create(self, telegram_id: int, username: Optional[str], role: str = "user", first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        query = """
        INSERT INTO users (telegram_id, username, role, first_name, last_name)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, telegram_id, username, role, first_name, last_name
        """
        record = await self._pool.fetchrow(query, telegram_id, username, role, first_name, last_name)
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
            first_name=record.get("first_name"),
            last_name=record.get("last_name"),
        )

    async def update_role(self, user_id: int, role: str) -> None:
        query = "UPDATE users SET role = $1 WHERE id = $2"
        await self._pool.execute(query, role, user_id)

    async def update_name(self, user_id: int, first_name: Optional[str], last_name: Optional[str]) -> None:
        query = "UPDATE users SET first_name = $1, last_name = $2 WHERE id = $3"
        await self._pool.execute(query, first_name, last_name, user_id)

    async def get_by_id(self, user_id: int) -> Optional[User]:
        query = "SELECT id, telegram_id, username, role, first_name, last_name FROM users WHERE id = $1"
        record = await self._pool.fetchrow(query, user_id)
        if record is None:
            return None
        return User(
            id=record["id"],
            telegram_id=record["telegram_id"],
            username=record["username"],
            role=record["role"],
            first_name=record.get("first_name"),
            last_name=record.get("last_name"),
        )

    async def list_all_telegram_ids(self) -> list[int]:
        query = "SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL"
        rows = await self._pool.fetch(query)
        return [row["telegram_id"] for row in rows]

