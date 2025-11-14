from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.callbacks import (
    EVENT_BACK_TO_LIST,
    START_MAIN_MENU,
    event_payment,
    event_payment_method,
    event_view,
)
from utils.di import get_config
from utils.i18n import t


def event_list_keyboard(events):
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.button(text=t("button.event.list_item", title=event.title), callback_data=event_view(event.id))
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()


def event_card_keyboard(event_id: int, is_paid: bool = False, is_paid_event: bool = True):
    builder = InlineKeyboardBuilder()
    config = get_config()
    if is_paid_event and not is_paid:
        builder.button(text=t("button.event.pay"), callback_data=event_payment(event_id))
    builder.button(text=t("button.event.ask_question"), url=config.support.question_url)
    builder.button(text=t("button.back"), callback_data=EVENT_BACK_TO_LIST)
    builder.adjust(1)
    return builder.as_markup()


def payment_method_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.payment.method.card"), callback_data=event_payment_method(event_id, "card"))
    builder.button(text=t("button.back"), callback_data=event_view(event_id))
    builder.adjust(1)
    return builder.as_markup()

