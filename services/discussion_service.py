from typing import Sequence

from database.pool import get_pool
from database.repositories.discussions import DiscussionMessage, DiscussionRepository


class DiscussionService:
    def __init__(self, repository: DiscussionRepository) -> None:
        self._repository = repository

    async def get_messages(self, event_id: int, limit: int = 20) -> Sequence[DiscussionMessage]:
        return await self._repository.list_messages(event_id, limit)

    async def add_message(self, event_id: int, user_id: int, message: str) -> None:
        await self._repository.add_message(event_id, user_id, message)


def build_discussion_service() -> DiscussionService:
    pool = get_pool()
    repository = DiscussionRepository(pool)
    return DiscussionService(repository)

