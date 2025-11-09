from dataclasses import dataclass
from datetime import date, time
from typing import Optional, Sequence

import asyncpg


@dataclass
class Event:
    id: int
    title: str
    date: date
    time: Optional[time]
    place: Optional[str]
    description: Optional[str]
    cost: Optional[float]
    image_file_id: Optional[str]
    max_participants: Optional[int]
    reminder_3days: bool
    reminder_1day: bool
    status: str


class EventRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, limit: int = 5) -> Sequence[Event]:
        query = """
        SELECT id, title, date, time, place, description, cost, image_file_id,
               max_participants, reminder_3days, reminder_1day, status
        FROM events
        WHERE status = 'active'
        ORDER BY date ASC, time ASC
        LIMIT $1
        """
        records = await self._pool.fetch(query, limit)
        return [self._to_event(record) for record in records]

    async def get(self, event_id: int) -> Optional[Event]:
        query = """
        SELECT id, title, date, time, place, description, cost, image_file_id,
               max_participants, reminder_3days, reminder_1day, status
        FROM events
        WHERE id = $1
        """
        record = await self._pool.fetchrow(query, event_id)
        if record is None:
            return None
        return self._to_event(record)

    async def create(self, data: dict) -> Event:
        query = """
        INSERT INTO events (title, date, time, place, description, cost, image_file_id,
                            max_participants, reminder_3days, reminder_1day, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id, title, date, time, place, description, cost, image_file_id,
                  max_participants, reminder_3days, reminder_1day, status
        """
        record = await self._pool.fetchrow(
            query,
            data["title"],
            data["date"],
            data["time"],
            data.get("place"),
            data.get("description"),
            data.get("cost"),
            data.get("image_file_id"),
            data.get("max_participants"),
            data.get("reminder_3days", False),
            data.get("reminder_1day", False),
            data.get("status", "active"),
        )
        return self._to_event(record)

    async def update(self, event_id: int, data: dict) -> Optional[Event]:
        fields = []
        values = []
        for idx, (key, value) in enumerate(data.items(), start=1):
            fields.append(f"{key} = ${idx}")
            values.append(value)
        if not fields:
            return await self.get(event_id)
        values.append(event_id)
        placeholders = ", ".join(fields)
        query = f"""
        UPDATE events
        SET {placeholders}
        WHERE id = ${len(values)}
        RETURNING id, title, date, time, place, description, cost, image_file_id,
                  max_participants, reminder_3days, reminder_1day, status
        """
        record = await self._pool.fetchrow(query, *values)
        if record is None:
            return None
        return self._to_event(record)

    def _to_event(self, record: asyncpg.Record) -> Event:
        return Event(
            id=record["id"],
            title=record["title"],
            date=record["date"],
            time=record["time"],
            place=record["place"],
            description=record["description"],
            cost=float(record["cost"]) if record["cost"] is not None else None,
            image_file_id=record["image_file_id"],
            max_participants=record["max_participants"],
            reminder_3days=record["reminder_3days"],
            reminder_1day=record["reminder_1day"],
            status=record["status"],
        )

