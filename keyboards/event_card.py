from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.callbacks import (
    EVENT_BACK_TO_LIST,
    START_MAIN_MENU,
    event_payment,
    event_view,
)
from utils.i18n import t


def event_list_keyboard(events):
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.button(text=t("button.event.list_item", title=event.title), callback_data=event_view(event.id))
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()


def event_card_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.event.pay"), callback_data=event_payment(event_id))
    builder.button(text=t("button.back"), callback_data=EVENT_BACK_TO_LIST)
    builder.adjust(1)
    return builder.as_markup()

