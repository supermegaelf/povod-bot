from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import asyncpg


@dataclass(frozen=True)
class Payment:
    id: int
    payment_id: str
    event_id: int
    user_id: int
    amount: float
    status: str
    created_at: datetime
    paid_at: Optional[datetime]
    confirmation_url: Optional[str]


class PaymentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        payment_id: str,
        event_id: int,
        user_id: int,
        amount: float,
        confirmation_url: Optional[str] = None,
    ) -> Payment:
        query = """
        INSERT INTO payments (payment_id, event_id, user_id, amount, confirmation_url)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, payment_id, event_id, user_id, amount, status, created_at, paid_at, confirmation_url
        """
        record = await self._pool.fetchrow(
            query, payment_id, event_id, user_id, amount, confirmation_url
        )
        return self._to_payment(record)

    async def get_by_payment_id(self, payment_id: str) -> Optional[Payment]:
        query = """
        SELECT id, payment_id, event_id, user_id, amount, status, created_at, paid_at, confirmation_url
        FROM payments
        WHERE payment_id = $1
        """
        record = await self._pool.fetchrow(query, payment_id)
        if record is None:
            return None
        return self._to_payment(record)

    async def update_status(
        self,
        payment_id: str,
        status: str,
        paid_at: Optional[datetime] = None,
    ) -> None:
        query = """
        UPDATE payments
        SET status = $2, paid_at = $3
        WHERE payment_id = $1
        """
        await self._pool.execute(query, payment_id, status, paid_at)

    def _to_payment(self, record: asyncpg.Record) -> Payment:
        return Payment(
            id=record["id"],
            payment_id=record["payment_id"],
            event_id=record["event_id"],
            user_id=record["user_id"],
            amount=float(record["amount"]),
            status=record["status"],
            created_at=record["created_at"],
            paid_at=record["paid_at"],
            confirmation_url=record["confirmation_url"],
        )

