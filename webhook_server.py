import asyncio
import logging

from aiohttp import web

from handlers.payment_webhook import setup_webhook_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    app = setup_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Webhook server started on http://0.0.0.0:8080/yookassa_payment")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

