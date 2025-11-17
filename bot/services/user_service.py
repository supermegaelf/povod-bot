from typing import Optional, Sequence

from bot.database.pool import get_pool
from bot.database.repositories.users import User, UserRepository
from bot.utils.constants import ROLE_ADMIN, ROLE_MODERATOR, ROLE_USER


class UserService:
    def __init__(self, repository: UserRepository, admin_ids: Sequence[int]) -> None:
        self._repository = repository
        self._admin_ids = set(admin_ids)

    async def ensure(self, telegram_id: int, username: Optional[str], first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        user = await self._repository.get_by_telegram_id(telegram_id)
        if user is None:
            role = ROLE_ADMIN if telegram_id in self._admin_ids else ROLE_USER
            return await self._repository.create(telegram_id, username, role=role, first_name=first_name, last_name=last_name)
        if telegram_id in self._admin_ids and user.role != ROLE_ADMIN:
            await self._repository.update_role(user.id, ROLE_ADMIN)
            user = await self._repository.get_by_telegram_id(telegram_id)
        if first_name is not None or last_name is not None:
            if user.first_name != first_name or user.last_name != last_name:
                await self._repository.update_name(user.id, first_name, last_name)
                user = await self._repository.get_by_telegram_id(telegram_id)
        return user

    async def promote_to_moderator(self, user_id: int) -> None:
        await self._repository.update_role(user_id, ROLE_MODERATOR)

    async def downgrade_to_user(self, user_id: int) -> None:
        await self._repository.update_role(user_id, ROLE_USER)

    def is_moderator(self, user: User) -> bool:
        return user.role in {ROLE_ADMIN, ROLE_MODERATOR}

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self._repository.get_by_id(user_id)

    async def list_all_telegram_ids(self) -> Sequence[int]:
        return await self._repository.list_all_telegram_ids()


def build_user_service(admin_ids: Sequence[int]) -> UserService:
    pool = get_pool()
    repository = UserRepository(pool)
    return UserService(repository, admin_ids)

