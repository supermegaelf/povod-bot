from dataclasses import dataclass
from typing import Optional

from bot.database.pool import get_pool

from bot.database.repositories.registrations import (
    Participant,
    RegistrationRepository,
    RegistrationStats,
)
from bot.utils.constants import STATUS_GOING, STATUS_NOT_GOING


@dataclass(frozen=True)
class Availability:
    capacity: Optional[int]
    going: int

    @property
    def free(self) -> Optional[int]:
        if self.capacity is None:
            return None
        return max(self.capacity - self.going, 0)


class RegistrationService:
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def get_stats(self, event_id: int) -> RegistrationStats:
        return await self._repository.get_stats(event_id)

    def availability(self, capacity: Optional[int], going: int) -> Availability:
        return Availability(capacity=capacity, going=going)

    async def list_participant_telegram_ids(self, event_id: int, status: str = STATUS_GOING) -> list[int]:
        return await self._repository.list_participant_telegram_ids(event_id, status)

    async def list_participants(self, event_id: int) -> list[Participant]:
        return await self._repository.list_participants(event_id)

    async def remove_participant(self, event_id: int, user_id: int) -> None:
        await self._repository.remove_participant(event_id, user_id)

    async def add_participant(self, event_id: int, user_id: int) -> None:
        await self._repository.add_participant(event_id, user_id)

    async def is_registered(self, event_id: int, user_id: int) -> bool:
        return await self._repository.is_registered(event_id, user_id)


def build_registration_service() -> RegistrationService:
    pool = get_pool()
    repository = RegistrationRepository(pool)
    return RegistrationService(repository)

