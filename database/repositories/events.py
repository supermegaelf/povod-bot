from dataclasses import dataclass
from datetime import date, time
from typing import Optional, Sequence, Tuple

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
    image_file_ids: Tuple[str, ...]
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
        async with self._pool.acquire() as connection:
            records = await connection.fetch(query, limit)
            events = [self._to_event(record) for record in records]
            await self._populate_images(connection, events)
            return events

    async def get(self, event_id: int) -> Optional[Event]:
        query = """
        SELECT id, title, date, time, place, description, cost, image_file_id,
               max_participants, reminder_3days, reminder_1day, status
        FROM events
        WHERE id = $1
        """
        async with self._pool.acquire() as connection:
            record = await connection.fetchrow(query, event_id)
            if record is None:
                return None
            event = self._to_event(record)
            await self._populate_images(connection, [event])
            return event

    async def create(self, data: dict) -> Event:
        query = """
        INSERT INTO events (title, date, time, place, description, cost, image_file_id,
                            max_participants, reminder_3days, reminder_1day, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id, title, date, time, place, description, cost, image_file_id,
                  max_participants, reminder_3days, reminder_1day, status
        """
        raw_images = data.get("image_file_ids")
        images: Tuple[str, ...] = tuple(raw_images) if raw_images else ()
        if not images:
            fallback = data.get("image_file_id")
            if fallback:
                images = (fallback,)
        image_for_column = images[0] if images else None
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                record = await connection.fetchrow(
                    query,
                    data["title"],
                    data["date"],
                    data["time"],
                    data.get("place"),
                    data.get("description"),
                    data.get("cost"),
                    image_for_column,
                    data.get("max_participants"),
                    data.get("reminder_3days", False),
                    data.get("reminder_1day", False),
                    data.get("status", "active"),
                )
                event = self._to_event(record)
                await self._replace_images(connection, event.id, images)
                await self._populate_images(connection, [event])
                return event

    async def update(self, event_id: int, data: dict) -> Optional[Event]:
        fields = []
        values = []
        images_data = data.pop("image_file_ids", None)
        images: Optional[Tuple[str, ...]] = None
        if images_data is not None:
            images = tuple(images_data)
            data["image_file_id"] = images[0] if images else None
        for idx, (key, value) in enumerate(data.items(), start=1):
            fields.append(f"{key} = ${idx}")
            values.append(value)
        if not fields:
            async with self._pool.acquire() as connection:
                event = await self.get(event_id)
                if event is None:
                    return None
                if images is not None:
                    async with connection.transaction():
                        await self._replace_images(connection, event.id, images)
                        await self._populate_images(connection, [event])
                return event
        values.append(event_id)
        placeholders = ", ".join(fields)
        query = f"""
        UPDATE events
        SET {placeholders}
        WHERE id = ${len(values)}
        RETURNING id, title, date, time, place, description, cost, image_file_id,
                  max_participants, reminder_3days, reminder_1day, status
        """
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                record = await connection.fetchrow(query, *values)
                if record is None:
                    return None
                event = self._to_event(record)
                if images is not None:
                    await self._replace_images(connection, event.id, images)
                await self._populate_images(connection, [event])
                return event

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
            image_file_ids=(),
            max_participants=record["max_participants"],
            reminder_3days=record["reminder_3days"],
            reminder_1day=record["reminder_1day"],
            status=record["status"],
        )

    async def _populate_images(self, connection: asyncpg.Connection, events: Sequence[Event]) -> None:
        ids = [event.id for event in events]
        if not ids:
            return
        query = """
        SELECT event_id, file_id
        FROM event_images
        WHERE event_id = ANY($1::int[])
        ORDER BY event_id ASC, position ASC, id ASC
        """
        records = await connection.fetch(query, ids)
        grouped: dict[int, list[str]] = {event_id: [] for event_id in ids}
        for record in records:
            grouped.setdefault(record["event_id"], []).append(record["file_id"])
        for event in events:
            images = grouped.get(event.id, [])
            if not images and event.image_file_id:
                images = [event.image_file_id]
            event.image_file_ids = tuple(images)
            event.image_file_id = images[0] if images else None

    async def _replace_images(self, connection: asyncpg.Connection, event_id: int, images: Sequence[str]) -> None:
        await connection.execute("DELETE FROM event_images WHERE event_id = $1", event_id)
        if not images:
            return
        insert_query = """
        INSERT INTO event_images (event_id, file_id, position)
        VALUES ($1, $2, $3)
        """
        records = [(event_id, file_id, idx) for idx, file_id in enumerate(images)]
        await connection.executemany(insert_query, records)

