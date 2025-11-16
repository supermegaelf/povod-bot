from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import asyncpg


@dataclass(frozen=True)
class Promocode:
    id: int
    event_id: int
    code: str
    discount_amount: float
    expires_at: Optional[datetime]
    is_active: bool
    used_by_user_id: Optional[int]
    used_at: Optional[datetime]


class PromocodeRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_code(self, code: str) -> Optional[Promocode]:
        query = """
        SELECT id, event_id, code, discount_amount, expires_at, is_active, used_by_user_id, used_at
        FROM promocodes
        WHERE code = $1
        """
        record = await self._pool.fetchrow(query, code)
        if record is None:
            return None
        return self._to_promocode(record)

    async def mark_used(self, promocode_id: int, user_id: int, used_at: datetime) -> None:
        query = """
        UPDATE promocodes
        SET used_by_user_id = $2, used_at = $3
        WHERE id = $1
        """
        await self._pool.execute(query, promocode_id, user_id, used_at)

    async def get_user_discount(self, event_id: int, user_id: int) -> float:
        query = """
        SELECT COALESCE(MAX(discount_amount), 0)
        FROM promocodes
        WHERE event_id = $1
          AND used_by_user_id = $2
        """
        value = await self._pool.fetchval(query, event_id, user_id)
        return float(value or 0)

    async def create(
        self,
        event_id: int,
        code: str,
        discount_amount: float,
        expires_at: Optional[datetime],
    ) -> Promocode:
        query = """
        INSERT INTO promocodes (event_id, code, discount_amount, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, event_id, code, discount_amount, expires_at, is_active, used_by_user_id, used_at
        """
        record = await self._pool.fetchrow(query, event_id, code, discount_amount, expires_at)
        return self._to_promocode(record)

    async def delete_by_code(self, event_id: int, code: str) -> bool:
        query = """
        DELETE FROM promocodes
        WHERE event_id = $1 AND code = $2
        """
        result = await self._pool.execute(query, event_id, code)
        return result.upper().startswith("DELETE") and "0" not in result.split()[-1]

    async def list_for_event(self, event_id: int) -> list[Promocode]:
        query = """
        SELECT id, event_id, code, discount_amount, expires_at, is_active, used_by_user_id, used_at
        FROM promocodes
        WHERE event_id = $1
        ORDER BY id DESC
        """
        records = await self._pool.fetch(query, event_id)
        return [self._to_promocode(record) for record in records]

    def _to_promocode(self, record: asyncpg.Record) -> Promocode:
        return Promocode(
            id=record["id"],
            event_id=record["event_id"],
            code=record["code"],
            discount_amount=float(record["discount_amount"]),
            expires_at=record["expires_at"],
            is_active=record["is_active"],
            used_by_user_id=record["used_by_user_id"],
            used_at=record["used_at"],
        )


