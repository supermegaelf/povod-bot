from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.callbacks import (
    MENU_ACTUAL_EVENTS,
    MENU_HISTORY,
    MENU_SETTINGS,
    MENU_STATS,
    START_MAIN_MENU,
)
from utils.i18n import t


def start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.start"), callback_data=START_MAIN_MENU)
    return builder.as_markup()


def main_menu_keyboard(show_settings: bool):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.menu.actual"), callback_data=MENU_ACTUAL_EVENTS)
    builder.button(text=t("button.menu.history"), callback_data=MENU_HISTORY)
    builder.button(text=t("button.menu.stats"), callback_data=MENU_STATS)
    if show_settings:
        builder.button(text=t("button.menu.settings"), callback_data=MENU_SETTINGS)
    builder.adjust(1)
    return builder.as_markup()


def back_to_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    return builder.as_markup()

