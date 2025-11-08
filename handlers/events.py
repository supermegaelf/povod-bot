from aiogram import F, Router
from aiogram.types import CallbackQuery

from keyboards import (
    back_to_main_keyboard,
    discussion_back_keyboard,
    event_card_keyboard,
    event_list_keyboard,
)
from utils.callbacks import (
    EVENT_BACK_TO_LIST,
    EVENT_DISCUSSION_PREFIX,
    EVENT_GOING_PREFIX,
    EVENT_NOT_GOING_PREFIX,
    EVENT_PARTICIPANTS_PREFIX,
    EVENT_PAYMENT_PREFIX,
    EVENT_VIEW_PREFIX,
    extract_event_id,
)
from utils.di import get_services
from utils.formatters import format_event_card
from utils.i18n import t
from utils.messaging import safe_delete

router = Router()


@router.callback_query(F.data.startswith(EVENT_VIEW_PREFIX))
async def show_event(callback: CallbackQuery) -> None:
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_VIEW_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, stats, availability)
    markup = event_card_keyboard(event.id, stats.going, stats.not_going)
    if callback.message:
        await safe_delete(callback.message)
        if event.image_file_id:
            await callback.message.answer_photo(event.image_file_id, caption=text, reply_markup=markup)
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
            await safe_delete(callback.message)
            await callback.message.answer(
                t("menu.actual_empty"),
                reply_markup=back_to_main_keyboard(),
            )
        await callback.answer()
        return
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("menu.event_selection_prompt"), reply_markup=event_list_keyboard(events))
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_GOING_PREFIX))
async def mark_going(callback: CallbackQuery) -> None:
    await _update_registration(callback, go=True)


@router.callback_query(F.data.startswith(EVENT_NOT_GOING_PREFIX))
async def mark_not_going(callback: CallbackQuery) -> None:
    await _update_registration(callback, go=False)


@router.callback_query(F.data.startswith(EVENT_PAYMENT_PREFIX))
async def payment_placeholder(callback: CallbackQuery) -> None:
    await callback.answer(t("placeholder.feature_in_progress"), show_alert=True)


@router.callback_query(F.data.startswith(EVENT_DISCUSSION_PREFIX))
async def discussion_placeholder(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await safe_delete(callback.message)
        event_id = extract_event_id(callback.data, EVENT_DISCUSSION_PREFIX)
        await callback.message.answer(
            t("placeholder.discussion"),
            reply_markup=discussion_back_keyboard(event_id),
        )


@router.callback_query(F.data.startswith(EVENT_PARTICIPANTS_PREFIX))
async def participants_placeholder(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await safe_delete(callback.message)
        event_id = extract_event_id(callback.data, EVENT_PARTICIPANTS_PREFIX)
        await callback.message.answer(
            t("placeholder.participants"),
            reply_markup=discussion_back_keyboard(event_id),
        )


async def _update_registration(callback: CallbackQuery, go: bool) -> None:
    if callback.data is None:
        return
    services = get_services()
    event_id = extract_event_id(
        callback.data,
        EVENT_GOING_PREFIX if go else EVENT_NOT_GOING_PREFIX,
    )
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    if go:
        await services.registrations.set_going(event.id, user.id)
    else:
        await services.registrations.set_not_going(event.id, user.id)
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, stats, availability)
    markup = event_card_keyboard(event.id, stats.going, stats.not_going)
    if callback.message:
        if callback.message.photo:
            await callback.message.edit_caption(text, reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer(t("status.updated"))

