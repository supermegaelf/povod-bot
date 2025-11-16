from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.callbacks import MENU_ACTUAL_EVENTS, MENU_COMMUNITY, MENU_SETTINGS, START_MAIN_MENU
from bot.utils.i18n import t


def main_menu_keyboard(show_settings: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.menu.actual"), callback_data=MENU_ACTUAL_EVENTS)
    builder.button(text=t("button.menu.community"), callback_data=MENU_COMMUNITY)
    if show_settings:
        builder.button(text=t("button.menu.settings"), callback_data=MENU_SETTINGS)
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    return builder.as_markup()

