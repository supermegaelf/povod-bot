import json
import logging

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from config import load_config
from bot.database import close_pool, init_pool, run_schema_setup
from bot.services.container import build_services
from bot.utils.di import set_config, set_services

logger = logging.getLogger(__name__)

_services_initialized = False


async def _ensure_services_initialized() -> None:
    global _services_initialized
    if _services_initialized:
        return

    config = load_config()
    set_config(config)
    await init_pool(config.database.dsn)
    await run_schema_setup()
    services = build_services(config)
    set_services(services)
    _services_initialized = True


async def yookassa_webhook_handler(request: Request) -> Response:
    logger.info(f"Received {request.method} request to {request.path_qs}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        await _ensure_services_initialized()
        from bot.utils.di import get_services

        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            body = await request.text()
            logger.error(f"Request body: {body}")
            return web.json_response({"status": "error", "message": "invalid json"}, status=400)
        
        logger.info(f"Received webhook: {json.dumps(data, ensure_ascii=False)}")
        
        event = data.get("event")
        payment_object = data.get("object", {})

        logger.info(f"Webhook event: {event}")

        if event != "payment.succeeded":
            logger.info(f"Ignoring event: {event}")
            return web.json_response({"status": "ok"})

        payment_id = payment_object.get("id")
        if not payment_id:
            logger.warning("Payment ID not found in webhook data")
            return web.json_response({"status": "error", "message": "payment_id not found"}, status=400)

        logger.info(f"Processing payment: {payment_id}")

        services = get_services()
        
        existing_payment = await services.payments.get_payment(payment_id)
        if existing_payment and existing_payment.status == "succeeded":
            logger.info(f"Payment {payment_id} already processed, skipping")
            return web.json_response({"status": "ok"})

        payment = await services.payments.handle_webhook(payment_id)

        if payment is None:
            logger.warning(f"Payment {payment_id} not found in database, trying to create from webhook data")
            metadata = payment_object.get("metadata", {})
            event_id_str = metadata.get("event_id")
            user_id_str = metadata.get("user_id")
            
            if event_id_str and user_id_str:
                try:
                    event_id = int(event_id_str)
                    user_id = int(user_id_str)
                    amount_value = payment_object.get("amount", {}).get("value", "0")
                    amount = float(amount_value)
                    confirmation_url = None
                    confirmation = payment_object.get("confirmation")
                    if confirmation:
                        confirmation_url = confirmation.get("confirmation_url")
                    
                    logger.info(f"Creating payment from webhook: payment_id={payment_id}, event_id={event_id}, user_id={user_id}, amount={amount}")
                    from bot.database.repositories.payments import PaymentRepository
                    from bot.database.pool import get_pool
                    pool = get_pool()
                    repo = PaymentRepository(pool)
                    await repo.create(
                        payment_id=payment_id,
                        event_id=event_id,
                        user_id=user_id,
                        amount=amount,
                        confirmation_url=confirmation_url,
                        payment_message_id=None,
                    )
                    logger.info(f"Payment created from webhook data: {payment_id}")
                    payment = await services.payments.handle_webhook(payment_id)
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to create payment from webhook data: {e}")
                    return web.json_response({"status": "error", "message": "invalid metadata"}, status=400)
            
            if payment is None:
                logger.warning(f"Payment {payment_id} not found in database and could not be created from webhook")
                return web.json_response({"status": "error", "message": "payment not found"}, status=404)

        logger.info(f"Payment {payment_id} status: {payment.status}")

        if payment.status == "succeeded":
            logger.info(f"Payment succeeded, registering participant for event {payment.event_id}, user {payment.user_id}")
            
            await services.registrations.add_participant(payment.event_id, payment.user_id)
            logger.info(f"Participant registered successfully")

            try:
                user = await services.users.get_by_id(payment.user_id)
                if user and user.telegram_id:
                    from aiogram import Bot
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    from bot.utils.callbacks import event_view
                    from bot.utils.di import get_config
                    from bot.utils.i18n import t

                    config = get_config()
                    bot = Bot(token=config.bot.token)
                    event_obj = await services.events.get_event(payment.event_id)
                    if event_obj:
                        if payment.payment_message_id:
                            try:
                                await bot.delete_message(user.telegram_id, payment.payment_message_id)
                                logger.info(f"Deleted payment message {payment.payment_message_id}")
                            except Exception as e:
                                logger.warning(f"Failed to delete payment message: {e}")
                        
                        logger.info(f"Sending success notification to user {user.telegram_id}")
                        markup = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text=t("button.back"), callback_data=event_view(payment.event_id))],
                            ]
                        )
                        await bot.send_message(
                            user.telegram_id,
                            t("payment.success", title=event_obj.title),
                            reply_markup=markup,
                        )
                        logger.info(f"Success notification sent")
                    await bot.session.close()
                else:
                    logger.warning(f"User {payment.user_id} not found or has no telegram_id")
            except Exception as e:
                logger.error(f"Failed to send payment success notification: {e}", exc_info=True)

        return web.json_response({"status": "ok"})

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def health_check_handler(request: Request) -> Response:
    logger.info(f"Health check request: {request.method} {request.path_qs}")
    return web.json_response({"status": "ok"})


def setup_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/yookassa_payment", health_check_handler)
    app.router.add_post("/yookassa_payment", yookassa_webhook_handler)
    logger.info("Webhook routes registered: GET /yookassa_payment, POST /yookassa_payment")
    
    access_logger = logging.getLogger("aiohttp.access")
    access_logger.setLevel(logging.WARNING)
    
    return app

