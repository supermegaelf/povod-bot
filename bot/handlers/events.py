import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message
from datetime import datetime, time

from bot.keyboards import (
    back_to_main_keyboard,
    event_card_keyboard,
    event_list_keyboard,
    payment_method_keyboard,
)
from bot.handlers.states import PromocodeState
from bot.utils.callbacks import (
    EVENT_BACK_TO_LIST,
    EVENT_LIST_PAGE_PREFIX,
    EVENT_PAYMENT_METHOD_PREFIX,
    EVENT_PAYMENT_PREFIX,
    EVENT_REFUND_PREFIX,
    EVENT_PROMOCODE_PREFIX,
    EVENT_VIEW_PREFIX,
    event_payment,
    extract_event_id,
)
from bot.utils.di import get_services
from bot.utils.formatters import format_event_card
from bot.utils.i18n import t
from bot.utils.messaging import safe_delete, safe_delete_by_id, safe_delete_recent_bot_messages
from bot.keyboards.event_card import promocode_back_keyboard

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
    
    await callback.answer()
    
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    is_paid_event = bool(event.cost and event.cost > 0)
    
    tasks = [services.registrations.get_stats(event.id)]
    
    if is_paid_event:
        tasks.append(services.payments.has_successful_payment(event.id, user.id))
    
    tasks.append(services.registrations.is_registered(event.id, user.id))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    stats = results[0] if not isinstance(results[0], Exception) else None
    task_idx = 1
    is_paid = False
    if is_paid_event:
        is_paid = results[task_idx] if not isinstance(results[task_idx], Exception) else False
        task_idx += 1
    is_registered = results[task_idx] if not isinstance(results[task_idx], Exception) else False
    
    discount = 0.0
    if is_paid_event and not is_paid:
        discount = await services.promocodes.get_user_discount(event.id, user.id)
    
    if stats is None:
        stats = type('Stats', (), {'going': 0})()
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability, discount if discount > 0 else None)
    markup = event_card_keyboard(event.id, is_paid=is_paid, is_paid_event=is_paid_event, is_registered=is_registered)
    
    if callback.message:
        chat_id = callback.message.chat.id
        bot = callback.message.bot
        message_id = callback.message.message_id
        cleanup_start = message_id - 1
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        if cleanup_start > 0:
            asyncio.create_task(safe_delete_recent_bot_messages(bot, chat_id, cleanup_start, count=300))
        images = list(event.image_file_ids)
        if images:
            if len(images) == 1:
                await bot.send_photo(chat_id, images[0], caption=text, reply_markup=markup)
            else:
                media = [InputMediaPhoto(media=file_id) for file_id in images]
                media_messages = await bot.send_media_group(chat_id, media)
                text_message = await bot.send_message(chat_id, text, reply_markup=markup)
                _remember_media_group(text_message, media_messages)
        else:
            await bot.send_message(chat_id, text, reply_markup=markup)


@router.callback_query(F.data == EVENT_BACK_TO_LIST)
async def back_to_list(callback: CallbackQuery) -> None:
    await callback.answer()
    
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    events = await services.events.get_active_events()
    if not events:
        if callback.message:
            await _cleanup_media_group(callback.message)
            await safe_delete(callback.message)
            await callback.message.answer(
                t("menu.actual_empty"),
                reply_markup=back_to_main_keyboard(),
            )
        return
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=event_list_keyboard(events))


@router.callback_query(F.data.startswith(EVENT_LIST_PAGE_PREFIX))
async def event_list_page(callback: CallbackQuery) -> None:
    await callback.answer()
    
    if callback.data is None:
        return
    page = int(callback.data.removeprefix(EVENT_LIST_PAGE_PREFIX))
    services = get_services()
    events = await services.events.get_active_events()
    if not events:
        if callback.message:
            await _cleanup_media_group(callback.message)
            await safe_delete(callback.message)
            await callback.message.answer(
                t("menu.actual_empty"),
                reply_markup=back_to_main_keyboard(),
            )
        return
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=event_list_keyboard(events, page=page))


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
    
    await callback.answer()

    text = t("payment.method_prompt")
    markup = payment_method_keyboard(event_id)

    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(EVENT_PAYMENT_METHOD_PREFIX))
async def process_payment(callback: CallbackQuery) -> None:
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
    
    await callback.answer()

    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)

    discount = 0.0
    if event.cost:
        discount = await services.promocodes.get_user_discount(event.id, user.id)
    amount = max((event.cost or 0) - discount, 0)

    if method != "card":
        await callback.answer(t("payment.method_not_available"), show_alert=True)
        return

    try:
        payment_id, confirmation_url = await services.payments.create_payment(
            event_id=event.id,
            user_id=user.id,
            amount=amount,
            description=t("payment.description", title=event.title),
        )
    except Exception:
        await callback.answer(t("payment.create_failed"), show_alert=True)
        return

    if not confirmation_url:
        await callback.answer(t("payment.create_failed"), show_alert=True)
        return

    text = t("payment.prompt", amount=amount, title=event.title)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("button.payment.pay"), url=confirmation_url)],
            [InlineKeyboardButton(text=t("button.back"), callback_data=event_payment(event.id))],
        ]
    )

    payment_message = None
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        payment_message = await callback.message.answer(text, reply_markup=markup)
        
        if payment_message:
            await services.payments.update_message_id(payment_id, payment_message.message_id)


@router.callback_query(F.data.startswith(EVENT_PROMOCODE_PREFIX))
async def start_promocode(callback: CallbackQuery, state: FSMContext) -> None:
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_PROMOCODE_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    
    await callback.answer()

    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    is_paid_event = bool(event.cost and event.cost > 0)
    if not is_paid_event:
        return
    has_payment = await services.payments.has_successful_payment(event.id, user.id)
    if has_payment:
        return

    await state.set_state(PromocodeState.code)
    await state.update_data(promocode_event_id=event.id)
    if callback.message:
        await _cleanup_media_group(callback.message)
        await safe_delete(callback.message)
        await callback.message.answer(
            t("promocode.prompt"),
            reply_markup=promocode_back_keyboard(event.id),
        )


@router.message(PromocodeState.code)
async def process_promocode(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state != PromocodeState.code.state:
        return
    services = get_services()
    data = await state.get_data()
    event_id = data.get("promocode_event_id")
    if not event_id:
        await state.clear()
        await message.answer(t("error.context_lost_alert"))
        return

    event = await services.events.get_event(event_id)
    if event is None:
        await state.clear()
        await message.answer(t("error.event_not_found"))
        return

    event_time = event.time or time(0, 0)
    event_start = datetime.combine(event.date, event_time)
    if datetime.now() >= event_start:
        await state.clear()
        await message.answer(t("promocode.error.expired"), reply_markup=promocode_back_keyboard(event_id))
        return

    tg_user = message.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)

    code = (message.text or "").strip()
    result = await services.promocodes.apply_promocode(event_id, user.id, code)

    bot = message.bot
    chat_id = message.chat.id
    await safe_delete_recent_bot_messages(bot, chat_id, message.message_id - 1, count=1)

    if not result.success:
        if result.error_code == "expired":
            text = t("promocode.error.expired")
        elif result.error_code == "already_used":
            text = t("promocode.error.already_used")
        else:
            text = t("promocode.error.not_found")
        await message.answer(text, reply_markup=promocode_back_keyboard(event_id))
        return

    discount_value = result.discount or 0
    await state.clear()
    await message.answer(
        t("promocode.success", discount=f"{discount_value:.0f}"),
        reply_markup=promocode_back_keyboard(event_id),
    )


@router.callback_query(F.data.startswith(EVENT_REFUND_PREFIX))
async def refund_event(callback: CallbackQuery) -> None:
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_REFUND_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    
    await callback.answer()
    
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    
    is_registered = await services.registrations.is_registered(event.id, user.id)
    if not is_registered:
        await callback.answer(t("event.refund.not_registered"), show_alert=True)
        return
    
    payment = None
    is_paid_event = bool(event.cost and event.cost > 0)
    if is_paid_event:
        payment = await services.payments.get_successful_payment(event.id, user.id)
        if payment:
            refund_success = await services.payments.refund_payment(payment.payment_id, payment.amount)
            if not refund_success:
                await callback.answer(t("event.refund.payment_failed"), show_alert=True)
                return
    
    try:
        await services.registrations.remove_participant(event.id, user.id)
    except Exception:
        await callback.answer(t("event.refund.error"), show_alert=True)
        return
    
    if payment:
        await callback.answer(t("event.refund.success_with_payment"), show_alert=True)
    else:
        await callback.answer(t("event.refund.success"), show_alert=True)
    
    is_paid = False
    if is_paid_event:
        is_paid = await services.payments.has_successful_payment(event.id, user.id)
    is_registered = False
    
    discount = 0.0
    if is_paid_event and not is_paid:
        discount = await services.promocodes.get_user_discount(event.id, user.id)
    
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability, discount if discount > 0 else None)
    markup = event_card_keyboard(event.id, is_paid=is_paid, is_paid_event=is_paid_event, is_registered=is_registered)
    
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

