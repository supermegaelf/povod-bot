from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message

from keyboards import (
    back_to_main_keyboard,
    event_card_keyboard,
    event_list_keyboard,
    payment_method_keyboard,
)
from utils.callbacks import (
    EVENT_BACK_TO_LIST,
    EVENT_PAYMENT_METHOD_PREFIX,
    EVENT_PAYMENT_PREFIX,
    EVENT_VIEW_PREFIX,
    extract_event_id,
)
from utils.di import get_services
from utils.formatters import format_event_card
from utils.i18n import t
from utils.messaging import safe_delete, safe_delete_by_id

router = Router()

_MEDIA_MESSAGE_MAP: dict[tuple[int, int], list[int]] = {}


@router.callback_query(F.data.startswith(EVENT_VIEW_PREFIX))
async def show_event(callback: CallbackQuery) -> None:
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_VIEW_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    is_paid = False
    if event.cost and event.cost > 0:
        is_paid = await services.payments.has_successful_payment(event.id, user.id)
    
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    markup = event_card_keyboard(event.id, is_paid=is_paid)
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        images = list(event.image_file_ids)
        if images:
            if len(images) == 1:
                await callback.message.answer_photo(images[0], caption=text, reply_markup=markup)
            else:
                media = [InputMediaPhoto(media=file_id) for file_id in images]
                media_messages = await callback.message.answer_media_group(media)
                text_message = await callback.message.answer(text, reply_markup=markup)
                _remember_media_group(text_message, media_messages)
        else:
            await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == EVENT_BACK_TO_LIST)
async def back_to_list(callback: CallbackQuery) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    events = await services.events.get_active_events()
    if not events:
        if callback.message:
            await _cleanup_media_group(callback.message)
            await safe_delete(callback.message)
            await callback.message.answer(
                t("menu.actual_empty"),
                reply_markup=back_to_main_keyboard(),
            )
        await callback.answer()
        return
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=event_list_keyboard(events))
    await callback.answer()


@router.callback_query(
    F.data.startswith(EVENT_PAYMENT_PREFIX) & ~F.data.startswith(EVENT_PAYMENT_METHOD_PREFIX)
)
async def show_payment_methods(callback: CallbackQuery) -> None:
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_PAYMENT_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return

    if not event.cost or event.cost <= 0:
        await callback.answer(t("payment.event_free"), show_alert=True)
        return

    text = t("payment.method_prompt")
    markup = payment_method_keyboard(event_id)

    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_PAYMENT_METHOD_PREFIX))
async def process_payment(callback: CallbackQuery) -> None:
    """Создаёт платёж после выбора способа оплаты"""
    if callback.data is None:
        await callback.answer()
        return

    payload = callback.data.removeprefix(EVENT_PAYMENT_METHOD_PREFIX)
    try:
        event_id_str, method = payload.split(":", 1)
        event_id = int(event_id_str)
    except ValueError:
        await callback.answer()
        return

    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return

    if not event.cost or event.cost <= 0:
        await callback.answer(t("payment.event_free"), show_alert=True)
        return

    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    is_paid = await services.payments.has_successful_payment(event.id, user.id)
    if is_paid:
        await callback.answer(t("payment.already_paid"), show_alert=True)
        return

    if method != "card":
        await callback.answer(t("payment.method_not_available"), show_alert=True)
        return

    try:
        payment_id, confirmation_url = await services.payments.create_payment(
            event_id=event.id,
            user_id=user.id,
            amount=event.cost,
            description=t("payment.description", title=event.title),
        )
    except Exception:
        await callback.answer(t("payment.create_failed"), show_alert=True)
        return

    if not confirmation_url:
        await callback.answer(t("payment.create_failed"), show_alert=True)
        return

    text = t("payment.prompt", amount=event.cost, title=event.title)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("button.payment.pay"), url=confirmation_url)],
            [InlineKeyboardButton(text=t("button.back"), callback_data=EVENT_BACK_TO_LIST)],
        ]
    )

    payment_message = None
    if callback.message:
        await safe_delete(callback.message)
        payment_message = await callback.message.answer(text, reply_markup=markup)
        
        if payment_message:
            await services.payments.update_message_id(payment_id, payment_message.message_id)
    await callback.answer()


def _remember_media_group(anchor: Message, media_messages: list[Message]) -> None:
    if not media_messages:
        return
    key = (anchor.chat.id, anchor.message_id)
    _MEDIA_MESSAGE_MAP[key] = [message.message_id for message in media_messages]


async def _cleanup_media_group(message: Message) -> None:
    key = (message.chat.id, message.message_id)
    media_ids = _MEDIA_MESSAGE_MAP.pop(key, [])
    if not media_ids:
        return
    bot = message.bot
    for media_id in media_ids:
        await safe_delete_by_id(bot, message.chat.id, media_id)

