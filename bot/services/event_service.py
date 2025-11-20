from typing import Sequence

from bot.database.pool import get_pool
from bot.database.repositories.events import Event, EventRepository
from bot.utils.events import has_event_started


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    async def get_active_events(self, limit: int | None = None, include_started: bool = False) -> Sequence[Event]:
        events = await self._repository.list_active(limit)
        if include_started:
            return events
        return [event for event in events if not has_event_started(event)]

    async def get_event(self, event_id: int) -> Event | None:
        return await self._repository.get(event_id)

    async def create_event(self, data: dict) -> Event:
        return await self._repository.create(data)

    async def update_event(self, event_id: int, data: dict) -> Event | None:
        return await self._repository.update(event_id, data)

    async def cancel_event(self, event_id: int) -> Event | None:
        return await self._repository.update(event_id, {"status": "cancelled"})

    async def list_reminder_candidates(self) -> Sequence[Event]:
        return await self._repository.list_reminder_candidates()


def build_event_service() -> EventService:
    pool = get_pool()
    repository = EventRepository(pool)
    return EventService(repository)

