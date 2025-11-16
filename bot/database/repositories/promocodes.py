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


