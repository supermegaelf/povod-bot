from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from keyboards import main_menu_keyboard, start_keyboard
from utils.callbacks import START_MAIN_MENU
from utils.di import get_services
from utils.messaging import safe_delete
from utils.i18n import t

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    services = get_services()
    tg_user = message.from_user
    if tg_user is None:
        return
    await services.users.ensure(tg_user.id, tg_user.username)
    raw_name = (tg_user.full_name or tg_user.username or "").strip()
    display_name = escape(raw_name) if raw_name else t("start.fallback_name")
    await message.answer(t("start.welcome", name=display_name), reply_markup=start_keyboard())


@router.callback_query(F.data == START_MAIN_MENU)
async def open_main_menu(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    keyboard = main_menu_keyboard(services.users.is_moderator(user))
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.title"), reply_markup=keyboard)
    await callback.answer()


@router.message(Command("menu"))
async def handle_menu_command(message: Message) -> None:
    services = get_services()
    tg_user = message.from_user
    if tg_user is None:
        return
    user = await services.users.ensure(tg_user.id, tg_user.username)
    keyboard = main_menu_keyboard(services.users.is_moderator(user))
    await message.answer(t("menu.title"), reply_markup=keyboard)

