from bot.database.pool import get_pool
from bot.database.repositories.bot_messages import BotMessage, BotMessageRepository


class BotMessageService:
    def __init__(self, repository: BotMessageRepository) -> None:
        self._repository = repository

    async def save_message(self, user_id: int, chat_id: int, message_id: int) -> None:
        await self._repository.save(user_id, chat_id, message_id)

    async def get_recent_messages(self, chat_id: int, hours: int = 48) -> list[BotMessage]:
        return await self._repository.get_recent_by_chat_id(chat_id, hours)

    async def get_all_messages(self, chat_id: int, limit: int = 100) -> list[BotMessage]:
        return await self._repository.get_by_chat_id(chat_id, limit)

    async def delete_messages(self, message_ids: list[tuple[int, int]]) -> None:
        await self._repository.delete_by_ids(message_ids)

    async def cleanup_old_messages(self, older_than_hours: int = 48) -> int:
        return await self._repository.delete_old_messages(older_than_hours)


def build_bot_message_service() -> BotMessageService:
    pool = get_pool()
    repository = BotMessageRepository(pool)
    return BotMessageService(repository)

