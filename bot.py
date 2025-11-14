import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

from config import load_config
from bot.database import close_pool, init_pool, run_schema_setup
from bot.handlers import setup as setup_handlers
from bot.handlers.payment_webhook import setup_webhook_app
from bot.services.container import build_services
from bot.utils.di import set_config, set_services


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
    
    webhook_app = setup_webhook_app()
    webhook_runner = web.AppRunner(webhook_app)
    await webhook_runner.setup()
    webhook_site = web.TCPSite(webhook_runner, "0.0.0.0", 8777)
    await webhook_site.start()
    logging.info("Webhook server started on port 8777")
    
    scheduler: AsyncIOScheduler | None = None
    try:
        scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Moscow"))
        async def reminders_job() -> None:
            await services.reminders.process_due_reminders(bot)
        scheduler.add_job(reminders_job, "cron", minute="*/5", id="reminders")
        scheduler.start()
        await dp.start_polling(bot)
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await webhook_runner.cleanup()
        await close_pool()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

