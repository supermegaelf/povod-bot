from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards import (
    back_to_main_keyboard,
    event_list_keyboard,
    moderator_settings_keyboard,
)
from utils.callbacks import MENU_ACTUAL_EVENTS, MENU_HISTORY, MENU_SETTINGS, MENU_STATS
from utils.di import get_services
from utils.formatters import format_event_summary
from utils.i18n import t
from utils.messaging import safe_delete

router = Router()


@router.callback_query(F.data == MENU_ACTUAL_EVENTS)
async def show_actual_events(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    events = await services.events.get_active_events()
    if not events:
        if callback.message:
            await safe_delete(callback.message)
            await callback.message.answer(t("menu.actual_empty"), reply_markup=back_to_main_keyboard())
        await callback.answer()
        return
    if callback.message:
        await safe_delete(callback.message)
        keyboard = event_list_keyboard(events)
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == MENU_HISTORY)
async def show_history(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    events = await services.events.get_history()
    if not events:
        text = t("history.empty")
    else:
        items = [format_event_summary(event) for event in events]
        text = "\n\n".join(items)
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == MENU_STATS)
async def show_stats(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("statistics.placeholder"), reply_markup=back_to_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == MENU_SETTINGS)
async def show_settings(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    if not services.users.is_moderator(user):
        await callback.answer(t("common.no_permissions"), show_alert=True)
        return
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
    await callback.answer()

