from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from bot.database.pool import get_pool
from bot.database.repositories.promocodes import PromocodeRepository


@dataclass(frozen=True)
class PromocodeResult:
    success: bool
    discount: Optional[float] = None
    error_code: Optional[str] = None


class PromocodeService:
    def __init__(self, repository: PromocodeRepository) -> None:
        self._repository = repository

    async def apply_promocode(self, event_id: int, user_id: int, code: str) -> PromocodeResult:
        normalized_code = code.strip()
        if not normalized_code:
            return PromocodeResult(success=False, error_code="not_found")

        promocode = await self._repository.get_by_code(normalized_code)
        if promocode is None or promocode.event_id != event_id or not promocode.is_active:
            return PromocodeResult(success=False, error_code="not_found")

        now = datetime.now(timezone.utc)
        if promocode.expires_at and promocode.expires_at < now.replace(tzinfo=None):
            return PromocodeResult(success=False, error_code="expired")

        if promocode.used_at is not None:
            return PromocodeResult(success=False, error_code="already_used")

        await self._repository.mark_used(promocode.id, user_id, now.replace(tzinfo=None))
        return PromocodeResult(success=True, discount=promocode.discount_amount)

    async def get_user_discount(self, event_id: int, user_id: int) -> float:
        return await self._repository.get_user_discount(event_id, user_id)


def build_promocode_service() -> PromocodeService:
    pool = get_pool()
    repository = PromocodeRepository(pool)
    return PromocodeService(repository)


