from aiogram import Dispatcher

from . import events, menu, moderation, start


def setup(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(events.router)
    dp.include_router(moderation.router)

