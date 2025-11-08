from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import (
    back_to_main_keyboard,
    discussion_keyboard,
    discussion_write_keyboard,
    event_card_keyboard,
    event_list_keyboard,
    participants_keyboard,
)
from utils.callbacks import (
    EVENT_BACK_TO_LIST,
    EVENT_DISCUSSION_PREFIX,
    EVENT_DISCUSSION_WRITE_PREFIX,
    EVENT_DISCUSSION_CANCEL_PREFIX,
    EVENT_GOING_PREFIX,
    EVENT_NOT_GOING_PREFIX,
    EVENT_PARTICIPANTS_PREFIX,
    EVENT_PAYMENT_PREFIX,
    EVENT_VIEW_PREFIX,
    extract_event_id,
)
from utils.di import get_services
from utils.formatters import format_discussion, format_event_card, format_participants
from utils.i18n import t
from utils.messaging import safe_delete, safe_delete_message
from handlers.states import DiscussionState

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
async def open_discussion(callback: CallbackQuery) -> None:
    if callback.data is None:
        return
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_DISCUSSION_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    messages = await services.discussions.get_messages(event.id)
    text = format_discussion(messages, event.title)
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(text, reply_markup=discussion_keyboard(event.id))
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_PARTICIPANTS_PREFIX))
async def open_participants(callback: CallbackQuery) -> None:
    if callback.data is None:
        return
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_PARTICIPANTS_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    participants = await services.registrations.list_participants(event.id)
    text = format_participants(participants, event.title)
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(text, reply_markup=participants_keyboard(event.id))
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_DISCUSSION_WRITE_PREFIX))
async def start_discussion_write(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    services = get_services()
    event_id = extract_event_id(callback.data, EVENT_DISCUSSION_WRITE_PREFIX)
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    await state.set_state(DiscussionState.writing)
    prompt_message_id = None
    if callback.message:
        await safe_delete(callback.message)
        prompt = await callback.message.answer(
            t("discussion.write_prompt"),
            reply_markup=discussion_write_keyboard(event.id),
        )
        prompt_message_id = prompt.message_id
    await state.update_data(event_id=event.id, prompt_id=prompt_message_id)
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_DISCUSSION_CANCEL_PREFIX))
async def cancel_discussion_write(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        return
    data = await state.get_data()
    event_id = extract_event_id(callback.data, EVENT_DISCUSSION_CANCEL_PREFIX)
    services = get_services()
    event = await services.events.get_event(event_id)
    await state.clear()
    if callback.message:
        await safe_delete(callback.message)
        if event is not None:
            await _send_discussion_view(callback.message, event)
    await callback.answer()


@router.message(DiscussionState.writing)
async def save_discussion_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data.get("event_id")
    if event_id is None:
        await state.clear()
        await message.answer(t("error.event_not_found"))
        return
    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await state.clear()
        await message.answer(t("error.event_not_found"))
        return
    content = (message.text or "").strip()
    if not content:
        await message.answer(t("discussion.write_prompt"))
        return
    tg_user = message.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    try:
        await services.discussions.add_message(event.id, user.id, content)
    except Exception:
        await message.answer(t("discussion.error"))
        return
    prompt_id = data.get("prompt_id")
    if prompt_id:
        await safe_delete_message(message.chat.id, prompt_id, message.bot)
    await state.clear()
    await message.answer(t("discussion.saved"))
    await _send_discussion_view(message, event)


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


async def _send_discussion_view(message: Message, event) -> None:
    services = get_services()
    messages = await services.discussions.get_messages(event.id)
    text = format_discussion(messages, event.title)
    await message.answer(text, reply_markup=discussion_keyboard(event.id))

