import logging
from datetime import timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import back_to_main_keyboard, event_list_keyboard, moderator_settings_keyboard

logger = logging.getLogger(__name__)
from bot.utils.callbacks import MENU_ACTUAL_EVENTS, MENU_COMMUNITY, MENU_SETTINGS
from bot.utils.di import get_config, get_services
from bot.utils.i18n import t
from bot.utils.messaging import safe_answer_callback, safe_delete

router = Router()


@router.callback_query(F.data == MENU_ACTUAL_EVENTS)
async def show_actual_events(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    events = await services.events.get_active_events()
    if not events:
        if callback.message:
            try:
                await callback.message.edit_text(t("menu.actual_empty"), reply_markup=back_to_main_keyboard())
            except Exception:
                new_message = await callback.message.answer(t("menu.actual_empty"), reply_markup=back_to_main_keyboard())
                await safe_delete(callback.message)
        await safe_answer_callback(callback)
        return
    if callback.message:
        keyboard = event_list_keyboard(events)
        message_too_old = False
        if callback.message.date:
            message_date = callback.message.date
            if message_date.tzinfo is None:
                message_date = message_date.replace(tzinfo=timezone.utc)
            from datetime import datetime
            now = datetime.now(timezone.utc)
            message_age = (now - message_date).total_seconds()
            if message_age > 3600:
                message_too_old = True
        
        if message_too_old:
            new_message = await callback.message.answer(t("menu.actual_prompt"), reply_markup=keyboard)
            await safe_delete(callback.message)
        else:
            try:
                await callback.message.edit_text(t("menu.actual_prompt"), reply_markup=keyboard)
            except Exception as e:
                logger.warning(f"[show_actual_events] Edit failed: {e}, sending new message")
                new_message = await callback.message.answer(t("menu.actual_prompt"), reply_markup=keyboard)
                await safe_delete(callback.message)
    await safe_answer_callback(callback)


@router.callback_query(F.data == MENU_COMMUNITY)
async def show_community(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    if callback.message:
        config = get_config()
        community_links = config.community
        text = t("placeholder.community").format(
            channel_main=community_links.channel_main,
            channel_reading=community_links.channel_reading,
            channel_ride=community_links.channel_ride,
            chat_social=community_links.chat_social,
            chat_discuss=community_links.chat_discuss,
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=back_to_main_keyboard(),
                disable_web_page_preview=True,
            )
        except Exception:
            new_message = await callback.message.answer(
                text,
                reply_markup=back_to_main_keyboard(),
                disable_web_page_preview=True,
            )
            await safe_delete(callback.message)
    await safe_answer_callback(callback)


@router.callback_query(F.data == MENU_SETTINGS)
async def show_settings(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    if not services.users.is_moderator(user):
        await safe_answer_callback(callback, text=t("common.no_permissions"), show_alert=True)
        return
    if callback.message:
        keyboard = moderator_settings_keyboard()
        try:
            await callback.message.edit_text(t("moderator.settings_title"), reply_markup=keyboard)
        except Exception:
            new_message = await callback.message.answer(t("moderator.settings_title"), reply_markup=keyboard)
            await safe_delete(callback.message)
    await safe_answer_callback(callback)

