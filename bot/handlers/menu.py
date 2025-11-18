import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import back_to_main_keyboard, event_list_keyboard, moderator_settings_keyboard

logger = logging.getLogger(__name__)
from bot.utils.callbacks import MENU_ACTUAL_EVENTS, MENU_COMMUNITY, MENU_SETTINGS
from bot.utils.di import get_config, get_services
from bot.utils.i18n import t
from bot.utils.messaging import safe_delete

router = Router()


@router.callback_query(F.data == MENU_ACTUAL_EVENTS)
async def show_actual_events(callback: CallbackQuery) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[show_actual_events] START: user_id={user_id}")
    services = get_services()
    tg_user = callback.from_user
    db_start = datetime.now()
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[show_actual_events] DB ensure user: elapsed={db_time:.3f}s")
    db_start = datetime.now()
    events = await services.events.get_active_events()
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[show_actual_events] DB get_active_events: elapsed={db_time:.3f}s")
    if not events:
        if callback.message:
            await safe_delete(callback.message)
            await callback.message.answer(t("menu.actual_empty"), reply_markup=back_to_main_keyboard())
        return
    if callback.message:
        await safe_delete(callback.message)
        keyboard = event_list_keyboard(events)
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=keyboard)
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[show_actual_events] COMPLETED: total_elapsed={total_time:.3f}s")


@router.callback_query(F.data == MENU_COMMUNITY)
async def show_community(callback: CallbackQuery) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[show_community] START: user_id={user_id}")
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    if callback.message:
        await safe_delete(callback.message)
        config = get_config()
        community_links = config.community
        text = t("placeholder.community").format(
            channel_main=community_links.channel_main,
            channel_reading=community_links.channel_reading,
            channel_ride=community_links.channel_ride,
            chat_social=community_links.chat_social,
            chat_discuss=community_links.chat_discuss,
        )
        await callback.message.answer(
            text,
            reply_markup=back_to_main_keyboard(),
            disable_web_page_preview=True,
        )


@router.callback_query(F.data == MENU_SETTINGS)
async def show_settings(callback: CallbackQuery) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[show_settings] START: user_id={user_id}")
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    if not services.users.is_moderator(user):
        await callback.answer(t("common.no_permissions"), show_alert=True)
        return
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())

