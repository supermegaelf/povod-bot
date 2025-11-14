from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard
from bot.utils.callbacks import START_MAIN_MENU
from bot.utils.di import get_services
from bot.utils.messaging import safe_delete
from bot.utils.i18n import t

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    services = get_services()
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await services.users.ensure(tg_user.id, tg_user.username)
    raw_name = (tg_user.full_name or tg_user.username or "").strip()
    display_name = escape(raw_name) if raw_name else t("start.fallback_name")
    keyboard = main_menu_keyboard(services.users.is_moderator(user))
    await message.answer(t("menu.title", name=display_name), reply_markup=keyboard)


@router.callback_query(F.data == START_MAIN_MENU)
async def open_main_menu(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    raw_name = (tg_user.full_name or tg_user.username or "").strip()
    display_name = escape(raw_name) if raw_name else t("start.fallback_name")
    keyboard = main_menu_keyboard(services.users.is_moderator(user))
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.title", name=display_name), reply_markup=keyboard)
    await callback.answer()


@router.message(Command("menu"))
async def handle_menu_command(message: Message) -> None:
    services = get_services()
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await services.users.ensure(tg_user.id, tg_user.username)
    raw_name = (tg_user.full_name or tg_user.username or "").strip()
    display_name = escape(raw_name) if raw_name else t("start.fallback_name")
    keyboard = main_menu_keyboard(services.users.is_moderator(user))
    await message.answer(t("menu.title", name=display_name), reply_markup=keyboard)

