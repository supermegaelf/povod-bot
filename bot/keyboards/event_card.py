from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.callbacks import (
    EVENT_BACK_TO_LIST,
    EVENT_LIST_PAGE_PREFIX,
    START_MAIN_MENU,
    event_payment,
    event_payment_method,
    event_promocode,
    event_refund,
    event_view,
)
from bot.utils.di import get_config
from bot.utils.i18n import t
from .common import event_link_keyboard


def event_list_keyboard(events, page: int = 0, page_size: int = 5):
    builder = InlineKeyboardBuilder()
    total_events = len(events)
    total_pages = (total_events + page_size - 1) // page_size if total_events > 0 else 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_events)
    page_events = events[start_idx:end_idx]
    
    for event in page_events:
        builder.button(text=t("button.event.list_item", title=event.title), callback_data=event_view(event.id))
    
    if total_pages > 1:
        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(("⏪", f"{EVENT_LIST_PAGE_PREFIX}{prev_page}"))
        if page < total_pages - 1:
            pagination_buttons.append(("⏩", f"{EVENT_LIST_PAGE_PREFIX}{next_page}"))
        if pagination_buttons:
            for text, callback_data in pagination_buttons:
                builder.button(text=text, callback_data=callback_data)
            builder.adjust(len(pagination_buttons))
    
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()


def event_card_keyboard(event_id: int, is_paid: bool = False, is_paid_event: bool = True, is_registered: bool = False):
    builder = InlineKeyboardBuilder()
    config = get_config()
    if is_paid_event and not is_paid:
        builder.button(text=t("button.event.pay"), callback_data=event_payment(event_id))
        builder.button(text=t("button.event.promocode"), callback_data=event_promocode(event_id))
    if is_registered:
        builder.button(text=t("button.event.refund"), callback_data=event_refund(event_id))
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


def promocode_back_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=event_view(event_id))
    builder.adjust(1)
    return builder.as_markup()


def new_event_notification_keyboard(event_id: int):
    return event_link_keyboard(event_id)

