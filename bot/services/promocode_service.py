from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional

from bot.database.pool import get_pool
from bot.database.repositories.promocodes import PromocodeRepository
from bot.services.event_service import EventService


@dataclass(frozen=True)
class PromocodeResult:
    success: bool
    discount: Optional[float] = None
    error_code: Optional[str] = None


class PromocodeService:
    def __init__(self, repository: PromocodeRepository, events: EventService) -> None:
        self._repository = repository
        self._events = events

    async def apply_promocode(self, event_id: int, user_id: int, code: str) -> PromocodeResult:
        normalized_code = code.strip().upper()
        if not normalized_code:
            return PromocodeResult(success=False, error_code="not_found")

        promocode = await self._repository.get_by_code(event_id, normalized_code)
        if promocode is None or not promocode.is_active:
            return PromocodeResult(success=False, error_code="not_found")

        event = await self._events.get_event(event_id)
        if event is None:
            return PromocodeResult(success=False, error_code="not_found")

        event_start = datetime.combine(event.date, event.time or time.min).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now >= event_start:
            return PromocodeResult(success=False, error_code="expired")

        if await self._repository.is_used_by_user(promocode.id, user_id):
            return PromocodeResult(success=False, error_code="already_used")

        await self._repository.mark_used(promocode.id, user_id, now.replace(tzinfo=None))
        return PromocodeResult(success=True, discount=promocode.discount_amount)

    async def get_user_discount(self, event_id: int, user_id: int) -> float:
        return await self._repository.get_user_discount(event_id, user_id)

    async def create_promocode(
        self,
        event_id: int,
        code: str,
        discount_amount: float,
        expires_at: Optional[datetime],
    ) -> None:
        normalized_code = code.strip().upper()
        existing = await self._repository.get_by_code(event_id, normalized_code)
        if existing is not None:
            from bot.utils.i18n import t
            raise ValueError(t("promocode.admin.duplicate"))
        await self._repository.create(event_id, normalized_code, discount_amount, expires_at)

    async def delete_promocode(self, event_id: int, code: str) -> bool:
        normalized_code = code.strip().upper()
        return await self._repository.delete_by_code(event_id, normalized_code)

    async def list_promocodes(self, event_id: int):
        return await self._repository.list_for_event(event_id)


def build_promocode_service(events: EventService) -> PromocodeService:
    pool = get_pool()
    repository = PromocodeRepository(pool)
    return PromocodeService(repository, events)


