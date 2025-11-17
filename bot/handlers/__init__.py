from aiogram import Dispatcher

from bot.middleware.message_refresh import MessageRefreshMiddleware

from . import events, menu, moderation, start


def setup(dp: Dispatcher) -> None:
    dp.callback_query.middleware(MessageRefreshMiddleware())
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(moderation.router)
    dp.include_router(events.router)

