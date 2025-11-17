from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.callbacks import HIDE_MESSAGE
from bot.utils.i18n import t


def hide_message_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.hide"), callback_data=HIDE_MESSAGE)
    builder.adjust(1)
    return builder.as_markup()


