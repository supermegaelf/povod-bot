import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config
from database import close_pool, init_pool, run_schema_setup
from handlers import setup as setup_handlers
from services.container import build_services
from utils.di import set_config, set_services


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    set_config(config)
    await init_pool(config.database.dsn)
    await run_schema_setup()
    services = build_services(config)
    set_services(services)
    bot = Bot(token=config.bot.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    setup_handlers(dp)
    try:
        await dp.start_polling(bot)
    finally:
        await close_pool()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

