from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.callbacks import HIDE_MESSAGE, event_view
from bot.utils.i18n import t


def hide_message_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.hide"), callback_data=HIDE_MESSAGE)
    builder.adjust(1)
    return builder.as_markup()


def event_link_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.event.go"), callback_data=event_view(event_id))
    builder.button(text=t("button.hide"), callback_data=HIDE_MESSAGE)
    builder.adjust(1)
    return builder.as_markup()


