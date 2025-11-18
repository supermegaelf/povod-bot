from __future__ import annotations

import logging
from datetime import date, datetime, time

logger = logging.getLogger(__name__)
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from typing import Any, Callable, Optional, TypeVar

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message

from bot.database.repositories.events import Event
from bot.database.repositories.registrations import RegistrationStats
from bot.handlers.states import CreateEventState, EditEventState, PromocodeAdminState
from bot.keyboards import (
    cancel_event_keyboard,
    create_preview_keyboard,
    create_reminders_keyboard,
    create_step_keyboard,
    edit_field_choice_keyboard,
    edit_images_keyboard,
    edit_reminders_keyboard,
    edit_step_keyboard,
    hide_message_keyboard,
    manage_event_actions_keyboard,
    manage_events_keyboard,
    manage_promocode_actions_keyboard,
    participants_list_keyboard,
    promocode_input_keyboard,
    promocode_list_keyboard,
    moderator_settings_keyboard,
    new_event_notification_keyboard,
)
from bot.utils.callbacks import (
    CREATE_EVENT_BACK,
    CREATE_EVENT_IMAGES_CONFIRM,
    CREATE_EVENT_PUBLISH,
    CREATE_EVENT_REMINDER_DONE,
    CREATE_EVENT_REMINDER_TOGGLE_1,
    CREATE_EVENT_REMINDER_TOGGLE_3,
    CREATE_EVENT_SKIP,
    EDIT_EVENT_BACK,
    EDIT_EVENT_SAVE,
    EDIT_EVENT_FIELD_PREFIX,
    EDIT_EVENT_PREFIX,
    EDIT_EVENT_CLEAR_IMAGES,
    EDIT_EVENT_BROADCAST,
    EDIT_EVENT_CANCEL_EVENT_PREFIX,
    EDIT_EVENT_CONFIRM_CANCEL_PREFIX,
    EDIT_EVENT_PARTICIPANTS_PREFIX,
    EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX,
    HIDE_MESSAGE,
    MANAGE_EVENTS_PAGE_PREFIX,
    SETTINGS_CREATE_EVENT,
    SETTINGS_MANAGE_EVENTS,
    extract_event_id,
    extract_event_id_and_field,
    extract_event_id_and_page,
)
from bot.utils.di import get_services
from bot.utils.formatters import format_event_card
from bot.utils.constants import MAX_EVENT_IMAGES
from bot.utils.messaging import safe_delete, safe_delete_message, safe_delete_by_id
from bot.utils.i18n import t

router = Router()

PROMPT_KEY = "prompt_message_id"
PROMPT_CHAT_KEY = "prompt_chat_id"
NOTICE_KEY = "notice_message_id"
NOTICE_CHAT_KEY = "notice_chat_id"
PREVIEW_MEDIA_KEY = "preview_media_entries"


CREATE_STATE_SEQUENCE = [
    CreateEventState.title,
    CreateEventState.date,
    CreateEventState.cost,
    CreateEventState.description,
    CreateEventState.time,
    CreateEventState.place,
    CreateEventState.period,
    CreateEventState.image,
    CreateEventState.limit,
    CreateEventState.reminders,
    CreateEventState.preview,
]

CREATE_STATE_BY_NAME = {state.state: state for state in CREATE_STATE_SEQUENCE}


@router.callback_query(F.data == SETTINGS_CREATE_EVENT)
async def start_create_event(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[start_create_event] START: user_id={user_id}")
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    if not services.users.is_moderator(user):
        return
    await state.clear()
    await state.update_data(history=[], image_file_ids=[])
    await _clear_preview_media(state, callback.message.bot if callback.message else callback.bot)
    await state.set_state(CreateEventState.title)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("create.title_prompt"),
            create_step_keyboard(back_enabled=True),
        )
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[start_create_event] COMPLETED: total_elapsed={total_time:.3f}s")


@router.callback_query(F.data == CREATE_EVENT_BACK)
async def create_event_back(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[create_event_back] START: user_id={user_id}")
    data = await state.get_data()
    history = list(data.get("history", []))
    await _clear_preview_media(state, callback.message.bot if callback.message else callback.bot)
    if not history:
        await state.clear()
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
        return
    target_state_name = history.pop()
    await state.update_data(history=history)
    target_state = CREATE_STATE_BY_NAME[target_state_name]
    await state.set_state(target_state)
    if callback.message:
        await safe_delete(callback.message)
        await _prompt_create_state(callback.message, state, target_state)


@router.callback_query(F.data == CREATE_EVENT_SKIP)
async def create_event_skip(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[create_event_skip] START: user_id={user_id}")
    current_state = await state.get_state()
    if current_state is None:
        return
    if current_state == CreateEventState.cost.state:
        await _push_create_history(state, CreateEventState.cost)
        await state.update_data(cost=None)
        await state.set_state(CreateEventState.description)
        if callback.message:
            await _send_prompt_text(
                callback.message,
                state,
                t("create.description_prompt"),
                create_step_keyboard(back_enabled=True, skip_enabled=True),
            )
    elif current_state == CreateEventState.description.state:
        await _push_create_history(state, CreateEventState.description)
        await state.update_data(description=None)
        await state.set_state(CreateEventState.time)
        if callback.message:
            await _send_prompt_text(
                callback.message,
                state,
                t("create.time_prompt"),
                create_step_keyboard(back_enabled=True, skip_enabled=True),
            )
    elif current_state == CreateEventState.time.state:
        await _push_create_history(state, CreateEventState.time)
        await state.update_data(event_time=None, event_end_time=None)
        await state.set_state(CreateEventState.place)
        if callback.message:
            await _send_prompt_text(
                callback.message,
                state,
                t("create.place_prompt"),
                create_step_keyboard(back_enabled=True, skip_enabled=True),
            )
    elif current_state == CreateEventState.place.state:
        await _push_create_history(state, CreateEventState.place)
        await state.update_data(place=None)
        await state.set_state(CreateEventState.period)
        if callback.message:
            await _send_prompt_text(
                callback.message,
                state,
                t("create.period_prompt"),
                create_step_keyboard(back_enabled=True, skip_enabled=True),
            )
    elif current_state == CreateEventState.period.state:
        await _push_create_history(state, CreateEventState.period)
        await state.update_data(event_end_time=None)
        await state.set_state(CreateEventState.image)
        if callback.message:
            await _render_create_image_prompt(callback.message, state)
    elif current_state == CreateEventState.image.state:
        await _push_create_history(state, CreateEventState.image)
        data = await state.get_data()
        await state.update_data(image_file_ids=data.get("image_file_ids", []))
        await state.set_state(CreateEventState.limit)
        if callback.message:
            await _send_prompt_text(
                callback.message,
                state,
                t("create.limit_prompt"),
                create_step_keyboard(back_enabled=True, skip_enabled=True),
            )
    elif current_state == CreateEventState.limit.state:
        await _push_create_history(state, CreateEventState.limit)
        await state.update_data(limit=None)
        await state.set_state(CreateEventState.reminders)
        if callback.message:
            await _prompt_reminders(callback.message, state)


@router.callback_query(F.data == CREATE_EVENT_IMAGES_CONFIRM)
async def create_event_images_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[create_event_images_confirm] START: user_id={user_id}")
    current_state = await state.get_state()
    if current_state != CreateEventState.image.state:
        return
    await _push_create_history(state, CreateEventState.image)
    data = await state.get_data()
    await state.update_data(image_file_ids=data.get("image_file_ids", []))
    await state.set_state(CreateEventState.limit)
    if callback.message:
        await _send_prompt_text(
            callback.message,
            state,
            t("create.limit_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )


@router.message(CreateEventState.title)
async def process_create_title(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await _send_prompt_text(
            message,
            state,
            t("create.title_empty"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.title)
    await state.update_data(title=text)
    await state.set_state(CreateEventState.date)
    await _send_prompt_text(
        message,
        state,
        t("create.date_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.date)
async def process_create_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        start_date, end_date = _parse_date_input(text)
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.date_invalid"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    
    today = date.today()
    if start_date < today:
        await _send_prompt_text(
            message,
            state,
            t("create.date_past"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    
    await _push_create_history(state, CreateEventState.date)
    await state.update_data(
        event_date=start_date,
        event_end_date=end_date,
        event_time=None,
        event_end_time=None,
    )
    await state.set_state(CreateEventState.cost)
    await _send_prompt_text(
        message,
        state,
        t("create.cost_prompt"),
        create_step_keyboard(back_enabled=True, skip_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.time)
async def process_create_time(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()
    if not text:
        await _send_prompt_text(
            message,
            state,
            t("create.time_invalid"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    if lowered in {"пропустить", "skip"}:
        await _push_create_history(state, CreateEventState.time)
        await state.update_data(event_time=None, event_end_time=None)
        await state.set_state(CreateEventState.place)
        await _send_prompt_text(
            message,
            state,
            t("create.place_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    try:
        parsed_time = _parse_single_time(text)
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.time_invalid"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.time)
    await state.update_data(event_time=parsed_time, event_end_time=None)
    await state.set_state(CreateEventState.place)
    await _send_prompt_text(
        message,
        state,
        t("create.place_prompt"),
        create_step_keyboard(back_enabled=True, skip_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.period)
async def process_create_period(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()
    if not text or lowered in {"пропустить", "skip"}:
        await _push_create_history(state, CreateEventState.period)
        await state.update_data(event_end_time=None)
        await state.set_state(CreateEventState.image)
        await _render_create_image_prompt(message, state)
        await safe_delete(message)
        return
    try:
        start_time, end_time = _parse_period_input(text)
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.period_invalid"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    data = await state.get_data()
    current_start = data.get("event_time")
    if current_start and current_start != start_time:
        await _send_prompt_text(
            message,
            state,
            t("create.period_mismatch"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.period)
    await state.update_data(event_time=start_time, event_end_time=end_time)
    await state.set_state(CreateEventState.image)
    await _render_create_image_prompt(message, state)
    await safe_delete(message)


@router.message(CreateEventState.place)
async def process_create_place(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    lowered = text.lower()
    await _push_create_history(state, CreateEventState.place)
    if text and lowered not in {"пропустить", "skip"}:
        await state.update_data(place=text)
    else:
        await state.update_data(place=None)
    await state.set_state(CreateEventState.period)
    await _send_prompt_text(
        message,
        state,
        t("create.period_prompt"),
        create_step_keyboard(back_enabled=True, skip_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.description)
async def process_create_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    await _push_create_history(state, CreateEventState.description)
    if text and text.lower() not in {"пропустить", "skip"}:
        await state.update_data(description=text)
    else:
        await state.update_data(description=None)
    await state.set_state(CreateEventState.time)
    await _send_prompt_text(
        message,
        state,
        t("create.time_prompt"),
        create_step_keyboard(back_enabled=True, skip_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.cost)
async def process_create_cost(message: Message, state: FSMContext) -> None:
    raw_text = (message.text or "").strip()
    if not raw_text or raw_text.lower() in {"пропустить", "skip"}:
        await _push_create_history(state, CreateEventState.cost)
        await state.update_data(cost=None)
        await state.set_state(CreateEventState.description)
        await _send_prompt_text(
            message,
            state,
            t("create.description_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    text = raw_text.replace(" ", "").replace(",", ".")
    try:
        cost = Decimal(text)
        if cost < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await _send_prompt_text(
            message,
            state,
            t("create.cost_invalid"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.cost)
    await state.update_data(cost=cost)
    await state.set_state(CreateEventState.description)
    await _send_prompt_text(
        message,
        state,
        t("create.description_prompt"),
        create_step_keyboard(back_enabled=True, skip_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.image)
async def process_create_image(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    images = list(data.get("image_file_ids", []))
    if message.photo:
        if len(images) >= MAX_EVENT_IMAGES:
            confirm_available = len(images) > 0
            await _update_prompt_message(
                message,
                state,
                t("create.image_limit_reached", limit=MAX_EVENT_IMAGES),
                create_step_keyboard(
                    back_enabled=True,
                    skip_enabled=True,
                    confirm_enabled=confirm_available,
                ),
            )
            await safe_delete(message)
            return
        file_id = message.photo[-1].file_id
        if not file_id:
            logger.warning(f"[process_create_image] Empty file_id received")
            await safe_delete(message)
            return
        images.append(file_id)
        await state.update_data(image_file_ids=images)
        logger.info(f"[process_create_image] Image added: total={len(images)}, file_id={file_id[:20]}...")
        await _render_create_image_prompt(message, state)
        await safe_delete(message)
        return
    text_raw = (message.text or "").strip()
    lowered = text_raw.lower()
    if (
        lowered in {"", "пропустить", "skip"}
        or lowered.startswith("подтвердить")
        or lowered.startswith("confirm")
    ):
        await _push_create_history(state, CreateEventState.image)
        await state.update_data(image_file_ids=images)
        await state.set_state(CreateEventState.limit)
        await _send_prompt_text(
            message,
            state,
            t("create.limit_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    if lowered in {"очистить", "clear"}:
        images = []
        await state.update_data(image_file_ids=images)
        await _render_create_image_prompt(message, state)
        await safe_delete(message)
        return
    confirm_available = len(images) > 0
    await _update_prompt_message(
        message,
        state,
        t("create.image_invalid"),
        create_step_keyboard(
            back_enabled=True,
            skip_enabled=True,
            confirm_enabled=confirm_available,
        ),
    )
    await safe_delete(message)


@router.message(CreateEventState.limit)
async def process_create_limit(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or text.lower() in {"пропустить", "skip"}:
        await _push_create_history(state, CreateEventState.limit)
        await state.update_data(limit=None)
        await state.set_state(CreateEventState.reminders)
        await _prompt_reminders(message, state)
        await safe_delete(message)
        return
    try:
        value = int(text)
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.limit_invalid"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
        await safe_delete(message)
        return
    limit = value if value > 0 else None
    await _push_create_history(state, CreateEventState.limit)
    await state.update_data(limit=limit)
    await state.set_state(CreateEventState.reminders)
    await _prompt_reminders(message, state)
    await safe_delete(message)


@router.callback_query(F.data == CREATE_EVENT_REMINDER_TOGGLE_3)
async def toggle_create_reminder_3(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[toggle_create_reminder_3] START: user_id={user_id}")
    await _toggle_reminder(state, key="reminder_3days")
    await _edit_reminder_markup(callback, state)


@router.callback_query(F.data == CREATE_EVENT_REMINDER_TOGGLE_1)
async def toggle_create_reminder_1(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[toggle_create_reminder_1] START: user_id={user_id}")
    await _toggle_reminder(state, key="reminder_1day")
    await _edit_reminder_markup(callback, state)


@router.callback_query(F.data == CREATE_EVENT_REMINDER_DONE)
async def finish_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[finish_reminders] START: user_id={user_id}")
    await _push_create_history(state, CreateEventState.reminders)
    await state.set_state(CreateEventState.preview)
    if callback.message:
        await _clear_preview_media(state, callback.message.bot)
        await _send_preview(callback.message, state)
        await safe_delete(callback.message)


@router.callback_query(F.data == CREATE_EVENT_PUBLISH)
async def publish_event(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[publish_event] START: user_id={user_id}")
    services = get_services()
    data = await state.get_data()
    payload = _build_event_payload(data)
    images_before = len(payload.get("image_file_ids", []))
    event = await services.events.create_event(payload)
    if event:
        images_after = len(event.image_file_ids) if event.image_file_ids else 0
        logger.info(f"[publish_event] Event created: id={event.id}, images_before={images_before}, images_after={images_after}")
        if images_before != images_after:
            logger.warning(f"[publish_event] Image count mismatch: expected {images_before}, got {images_after}")
    await _notify_new_event(callback, event)
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        await _clear_preview_media(state, callback.message.bot)
        keyboard = moderator_settings_keyboard()
        try:
            await callback.message.edit_text(t("create.published"), reply_markup=keyboard)
        except Exception:
            await safe_delete(callback.message)
            await callback.message.answer(t("create.published"), reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == SETTINGS_MANAGE_EVENTS)
async def open_manage_events(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[open_manage_events] START: user_id={user_id}")
    services = get_services()
    tg_user = callback.from_user
    db_start = datetime.now()
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[open_manage_events] DB ensure user: elapsed={db_time:.3f}s")
    if not services.users.is_moderator(user):
        return
    await state.clear()
    db_start = datetime.now()
    events = await services.events.get_active_events(limit=20)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[open_manage_events] DB get_active_events: elapsed={db_time:.3f}s")
    if not events:
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            keyboard = moderator_settings_keyboard()
            try:
                await callback.message.edit_text(t("moderator.no_events"), reply_markup=keyboard)
            except Exception:
                await safe_delete(callback.message)
                await callback.message.answer(t("moderator.no_events"), reply_markup=keyboard)
        return
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("menu.actual_prompt"),
            manage_events_keyboard(events),
        )
    await state.update_data(edit_stack=[])
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[open_manage_events] COMPLETED: total_elapsed={total_time:.3f}s")


@router.callback_query(F.data.startswith(MANAGE_EVENTS_PAGE_PREFIX))
async def manage_events_page(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[manage_events_page] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    services = get_services()
    tg_user = callback.from_user
    db_start = datetime.now()
    user = await services.users.ensure(tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[manage_events_page] DB ensure user: elapsed={db_time:.3f}s")
    if not services.users.is_moderator(user):
        await callback.answer(t("common.no_permissions"), show_alert=True)
        return
    page = int(callback.data.removeprefix(MANAGE_EVENTS_PAGE_PREFIX))
    db_start = datetime.now()
    events = await services.events.get_active_events(limit=20)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[manage_events_page] DB get_active_events: elapsed={db_time:.3f}s")
    if not events:
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            keyboard = moderator_settings_keyboard()
            try:
                await callback.message.edit_text(t("moderator.no_events"), reply_markup=keyboard)
            except Exception:
                await safe_delete(callback.message)
                await callback.message.answer(t("moderator.no_events"), reply_markup=keyboard)
        return
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("menu.actual_prompt"),
            manage_events_keyboard(events, page=page),
        )
    await state.update_data(edit_stack=[])
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[manage_events_page] COMPLETED: total_elapsed={total_time:.3f}s")


@router.callback_query(F.data.startswith(EDIT_EVENT_FIELD_PREFIX))
async def handle_edit_entry(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[handle_edit_entry] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id, field = extract_event_id_and_field(callback.data, EDIT_EVENT_FIELD_PREFIX)
    await _ensure_event_context(state, event_id)
    if field == "menu":
        await _push_edit_stack(state, "fields")
        await state.set_state(EditEventState.selecting_field)
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.field_choice_prompt"),
                edit_field_choice_keyboard(event_id),
            )
        return
    if field == "reminders":
        await _push_edit_stack(state, "reminders")
        await state.set_state(EditEventState.reminders)
        if callback.message:
            await safe_delete(callback.message)
            await _prompt_edit_reminders(callback.message, state, event_id)
        return
    services = get_services()
    if field == "image":
        event = await services.events.get_event(event_id)
        if event is None:
            await callback.answer(t("error.event_not_found"), show_alert=True)
            return
        existing_images = list(event.image_file_ids)
        await _push_edit_stack(state, "images")
        await state.set_state(EditEventState.image_upload)
        await state.update_data(edit_field=field, new_image_file_ids=existing_images, images_dirty=False)
        if callback.message:
            await safe_delete(callback.message)
            await _render_edit_image_prompt(callback.message, state)
        return
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    await _push_edit_stack(state, "value")
    await state.set_state(EditEventState.value_input)
    await state.update_data(edit_field=field)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            _compose_edit_prompt(event, field),
            edit_step_keyboard(),
        )


@router.callback_query(F.data == EDIT_EVENT_BROADCAST)
async def start_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[start_broadcast] START: user_id={user_id}")
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await callback.answer(t("error.context_lost_alert"), show_alert=True)
        await state.clear()
        return
    await _push_edit_stack(state, "broadcast")
    await state.set_state(EditEventState.broadcast)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("moderator.broadcast_prompt"),
            edit_step_keyboard(),
        )


@router.message(EditEventState.broadcast)
async def process_broadcast(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await _send_prompt_text(
            message,
            state,
            t("moderator.broadcast_empty"),
            edit_step_keyboard(),
        )
        await safe_delete(message)
        return
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await message.answer(t("error.context_lost_alert"), reply_markup=moderator_settings_keyboard())
        await state.clear()
        await safe_delete(message)
        return
    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await message.answer(t("error.event_not_found"), reply_markup=moderator_settings_keyboard())
        await state.clear()
        await safe_delete(message)
        return
    
    telegram_ids = await services.registrations.list_participant_telegram_ids(event_id)
    logger = logging.getLogger(__name__)
    logger.info(f"Broadcasting message to {len(telegram_ids)} participants for event {event_id}")
    
    if not telegram_ids:
        await _send_prompt_text(
            message,
            state,
            t("moderator.broadcast_no_participants"),
            edit_step_keyboard(),
        )
        await safe_delete(message)
        return
    
    broadcast_text = t("moderator.broadcast_message", title=event.title, message=text)
    broadcast_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("button.hide"), callback_data=HIDE_MESSAGE)],
        ]
    )
    
    delivered = 0
    for telegram_id in telegram_ids:
        try:
            await message.bot.send_message(telegram_id, broadcast_text, reply_markup=broadcast_markup)
            delivered += 1
            logger.info(f"Message delivered to {telegram_id}")
        except Exception as e:
            logger.warning(f"Failed to send message to {telegram_id}: {e}")
            continue
    
    if delivered == 0:
        await _send_prompt_text(
            message,
            state,
            t("moderator.broadcast_failed"),
            edit_step_keyboard(),
        )
        await safe_delete(message)
        return
    
    success_notice = t("moderator.broadcast_sent", count=delivered)
    await state.update_data(edit_stack=["actions"])
    await state.set_state(EditEventState.selecting_field)
    await _send_admin_success_prompt(message, state, success_notice, event_id)
    await safe_delete(message)


@router.callback_query(F.data == HIDE_MESSAGE)
async def hide_message(callback: CallbackQuery) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[hide_message] START: user_id={user_id}")
    if callback.message:
        await safe_delete(callback.message)


@router.callback_query(F.data.startswith(EDIT_EVENT_CANCEL_EVENT_PREFIX))
async def confirm_cancel_request(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[confirm_cancel_request] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id = extract_event_id(callback.data, EDIT_EVENT_CANCEL_EVENT_PREFIX)
    await _ensure_event_context(state, event_id)
    await _push_edit_stack(state, "cancel")
    await state.set_state(EditEventState.confirmation)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("moderator.cancel_confirm_prompt"),
            cancel_event_keyboard(event_id),
        )


@router.callback_query(F.data.startswith(EDIT_EVENT_CONFIRM_CANCEL_PREFIX))
async def cancel_event_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[cancel_event_confirm] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id = extract_event_id(callback.data, EDIT_EVENT_CONFIRM_CANCEL_PREFIX)
    services = get_services()
    event = await services.events.cancel_event(event_id)
    if event is None:
        await callback.answer(t("error.cancel_failed"), show_alert=True)
        return
    await _notify_cancellation(callback, event)
    await state.clear()
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        keyboard = moderator_settings_keyboard()
        try:
            await callback.message.edit_text(t("edit.event_cancelled_confirm"), reply_markup=keyboard)
        except Exception:
            await safe_delete(callback.message)
            await callback.message.answer(t("edit.event_cancelled_confirm"), reply_markup=keyboard)


@router.callback_query(F.data.startswith(EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX))
async def show_participants_page(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[show_participants_page] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id, page = extract_event_id_and_page(callback.data, EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX)
    await _render_participants_list(callback, state, event_id, page=page)


@router.callback_query(F.data.startswith(EDIT_EVENT_PARTICIPANTS_PREFIX))
async def show_participants(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[show_participants] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id = extract_event_id(callback.data, EDIT_EVENT_PARTICIPANTS_PREFIX)
    await _render_participants_list(callback, state, event_id, page=0)


async def _render_participants_list(callback: CallbackQuery, state: FSMContext, event_id: int, page: int = 0) -> None:
    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    participants = await services.registrations.list_paid_participants(event_id)
    if callback.message:
        await _push_edit_stack(state, "participants")
        await state.update_data(edit_event_id=event_id, edit_stack=["actions", "participants"])
        await safe_delete(callback.message)
        if not participants:
            await _send_prompt_text(
                callback.message,
                state,
                t("moderator.participants_empty"),
                participants_list_keyboard(event_id, participants_count=0, page=0),
            )
        else:
            page_size = 10
            total_participants = len(participants)
            start_idx = page * page_size
            end_idx = min(start_idx + page_size, total_participants)
            page_participants = participants[start_idx:end_idx]
            
            lines = []
            for idx, participant in enumerate(page_participants, start=start_idx + 1):
                full_name_parts = []
                if participant.first_name:
                    full_name_parts.append(participant.first_name)
                if participant.last_name:
                    full_name_parts.append(participant.last_name)
                full_name = " ".join(full_name_parts) if full_name_parts else None
                
                if participant.username:
                    username_part = f"@{participant.username}"
                elif participant.telegram_id:
                    username_part = str(participant.telegram_id)
                else:
                    username_part = str(participant.user_id)
                
                if full_name:
                    lines.append(f"{idx}. {full_name} ({username_part})")
                else:
                    lines.append(f"{idx}. {username_part}")
            text = "\n".join(lines)
            await _send_prompt_text(
                callback.message,
                state,
                text,
                participants_list_keyboard(event_id, participants_count=total_participants, page=page),
            )


@router.callback_query(F.data.startswith(EDIT_EVENT_PREFIX))
async def open_event_actions(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[open_event_actions] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    event_id = extract_event_id(callback.data, EDIT_EVENT_PREFIX)
    services = get_services()
    db_start = datetime.now()
    event = await services.events.get_event(event_id)
    db_time = (datetime.now() - db_start).total_seconds()
    logger.info(f"[open_event_actions] DB get_event: elapsed={db_time:.3f}s")
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    await state.clear()
    await state.set_state(EditEventState.selecting_field)
    await state.update_data(
        edit_event_id=event_id,
        edit_stack=["actions"],
    )
    if callback.message:
        await _clear_notice_message(state, callback.message.bot)
        await _remove_prompt_message(callback.message, state)
        text = t("edit.event_options_prompt")
        markup = manage_event_actions_keyboard(event_id)
        try:
            edit_start = datetime.now()
            await callback.message.edit_text(text, reply_markup=markup)
            edit_time = (datetime.now() - edit_start).total_seconds()
            logger.info(f"[open_event_actions] Message edited: elapsed={edit_time:.3f}s")
            await _set_prompt_message(state, callback.message)
        except Exception as e:
            logger.warning(f"[open_event_actions] Edit failed: {e}, sending new message")
            await safe_delete(callback.message)
            sent = await callback.message.answer(text, reply_markup=markup)
            await _set_prompt_message(state, sent)
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[open_event_actions] COMPLETED: total_elapsed={total_time:.3f}s")


@router.callback_query(F.data.startswith("promocode:menu:"))
async def promocode_menu(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[promocode_menu] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    event_id = int(parts[2])
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "actions":
        existing_stack = ["actions"]
    existing_stack.append("promocodes")
    await state.set_state(EditEventState.selecting_field)
    await state.update_data(
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("promocode.admin.menu_prompt"),
            manage_promocode_actions_keyboard(event_id),
        )


@router.callback_query(F.data.startswith("promocode:") & F.data.contains(":list:"))
async def list_event_promocodes(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[list_event_promocodes] START: data={callback_data[:50]}, user_id={user_id}")
    services = get_services()
    if callback.data is None:
        return
    payload = callback.data.split(":")
    if len(payload) != 3:
        return
    event_id = int(payload[2])
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "promocodes":
        existing_stack = ["actions", "promocodes"]
    await state.set_state(EditEventState.selecting_field)
    await state.update_data(
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    promocodes = await services.promocodes.list_promocodes(event_id)
    if callback.message:
        await safe_delete(callback.message)
        if not promocodes:
            await _send_prompt_text(
                callback.message,
                state,
                t("promocode.admin.list_empty"),
                promocode_list_keyboard(event_id),
            )
        else:
            event_date_str = event.date.strftime("%d.%m.%Y")
            if event.time:
                event_start_str = f"{event_date_str} {event.time.strftime('%H:%M')}"
            else:
                event_start_str = event_date_str
            lines = []
            for p in promocodes:
                lines.append(
                    t(
                        "promocode.admin.list_item",
                        code=p.code,
                        discount=f"{p.discount_amount:.0f}",
                        event_start=event_start_str,
                    )
                )
            text = "\n".join(lines)
            await _send_prompt_text(
                callback.message,
                state,
                text,
                promocode_list_keyboard(event_id),
            )


@router.callback_query(F.data.startswith("promocode:") & F.data.contains(":add:"))
async def start_add_promocode(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[start_add_promocode] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    event_id = int(parts[2])
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "promocodes":
        existing_stack = ["actions", "promocodes"]
    await state.set_state(PromocodeAdminState.code_input)
    await state.update_data(
        promocode_event_id=event_id,
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("promocode.admin.add_code_prompt"),
            promocode_input_keyboard(event_id),
        )


@router.message(PromocodeAdminState.code_input)
async def process_promocode_code_input(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state != PromocodeAdminState.code_input.state:
        return
    data = await state.get_data()
    event_id = data.get("promocode_event_id")
    if not event_id:
        return
    code = (message.text or "").strip()
    if not code:
        await _send_prompt_text(
            message,
            state,
            t("promocode.admin.code_empty"),
            promocode_input_keyboard(event_id),
        )
        await safe_delete(message)
        return
    if data.get("promocode_delete_mode"):
        services = get_services()
        event_id = data.get("promocode_event_id")
        deleted = await services.promocodes.delete_promocode(event_id, code)
        await _remove_prompt_message(message, state)
        await safe_delete(message)
        existing_stack = list(data.get("edit_stack", []))
        if not existing_stack or existing_stack[-1] != "promocodes":
            existing_stack = ["actions", "promocodes"]
        await state.clear()
        await state.set_state(EditEventState.selecting_field)
        await state.update_data(
            edit_event_id=event_id,
            edit_stack=existing_stack,
        )
        normalized_code = code.strip().upper()
        if deleted:
            await message.answer(
                t("promocode.admin.delete_success", code=normalized_code),
                reply_markup=manage_promocode_actions_keyboard(event_id),
            )
        else:
            await state.set_state(PromocodeAdminState.code_input)
            await state.update_data(promocode_event_id=event_id, promocode_delete_mode=True)
            await message.answer(
                t("promocode.admin.delete_not_found"),
                reply_markup=promocode_input_keyboard(event_id),
            )
        return
    await state.update_data(promocode_code=code)
    await state.set_state(PromocodeAdminState.discount_input)
    event_id = data.get("promocode_event_id")
    await _send_prompt_text(
        message,
        state,
        t("promocode.admin.add_discount_prompt"),
        promocode_input_keyboard(event_id),
    )
    await safe_delete(message)


@router.message(PromocodeAdminState.discount_input)
async def process_promocode_discount_input(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    event_id = data.get("promocode_event_id")
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("promocode.admin.discount_invalid"),
            promocode_input_keyboard(event_id),
        )
        await safe_delete(message)
        return
    if value < 1:
        await _send_prompt_text(
            message,
            state,
            t("promocode.admin.discount_invalid"),
            promocode_input_keyboard(event_id),
        )
        await safe_delete(message)
        return
    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await state.clear()
        await message.answer(t("error.event_not_found"))
        await safe_delete(message)
        return
    if event.cost and value > event.cost:
        await _send_prompt_text(
            message,
            state,
            t("promocode.admin.discount_too_large", cost=f"{event.cost:.0f}"),
            promocode_input_keyboard(event_id),
        )
        await safe_delete(message)
        return
    code = data.get("promocode_code")
    try:
        await services.promocodes.create_promocode(event_id, code, value, None)
    except ValueError as e:
        await _send_prompt_text(
            message,
            state,
            str(e),
            promocode_input_keyboard(event_id),
        )
        await safe_delete(message)
        return
    await _remove_prompt_message(message, state)
    await safe_delete(message)
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "promocodes":
        existing_stack = ["actions", "promocodes"]
    await state.clear()
    await state.set_state(EditEventState.selecting_field)
    await state.update_data(
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    normalized_code = code.strip().upper()
    await message.answer(
        t("promocode.admin.add_success", code=normalized_code, discount=f"{value:.0f}"),
        reply_markup=manage_promocode_actions_keyboard(event_id),
    )


@router.callback_query(F.data.startswith("promocode:") & F.data.contains(":delete:"))
async def start_delete_promocode(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[start_delete_promocode] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    event_id = int(parts[2])
    services = get_services()
    promocodes = await services.promocodes.list_promocodes(event_id)
    if not promocodes:
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("promocode.admin.list_empty"),
                manage_promocode_actions_keyboard(event_id),
            )
        return
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "promocodes":
        existing_stack = ["actions", "promocodes"]
    await state.set_state(PromocodeAdminState.code_input)
    await state.update_data(
        promocode_event_id=event_id,
        promocode_delete_mode=True,
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("promocode.admin.delete_code_prompt"),
            promocode_input_keyboard(event_id),
        )


@router.callback_query(F.data.startswith("promocode:back_menu:"))
async def promocode_back_menu(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    callback_data = callback.data or "None"
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[promocode_back_menu] START: data={callback_data[:50]}, user_id={user_id}")
    if callback.data is None:
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    event_id = int(parts[2])
    data = await state.get_data()
    existing_stack = list(data.get("edit_stack", []))
    if not existing_stack or existing_stack[-1] != "actions":
        existing_stack = ["actions"]
    existing_stack.append("promocodes")
    await state.set_state(EditEventState.selecting_field)
    await state.update_data(
        edit_event_id=event_id,
        edit_stack=existing_stack,
    )
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("promocode.admin.menu_prompt"),
            manage_promocode_actions_keyboard(event_id),
        )


@router.callback_query(F.data == EDIT_EVENT_BACK)
async def edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[edit_back] START: user_id={user_id}")
    data = await state.get_data()
    stack = list(data.get("edit_stack", []))
    if not stack:
        if callback.message:
            await _clear_notice_message(state, callback.message.bot)
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
        await state.clear()
        return
    stack.pop()
    await state.update_data(edit_stack=stack)
    event_id = data.get("edit_event_id")
    if not event_id:
        await state.clear()
        return
    if not stack:
        services = get_services()
        db_start = datetime.now()
        events = await services.events.get_active_events()
        db_time = (datetime.now() - db_start).total_seconds()
        logger.info(f"[edit_back] DB get_active_events: elapsed={db_time:.3f}s")
        await state.clear()
        if callback.message:
            await safe_delete(callback.message)
            if events:
                await _send_prompt_text(
                    callback.message,
                    state,
                    t("menu.actual_prompt"),
                    manage_events_keyboard(events),
                )
                await state.update_data(edit_stack=[])
            else:
                await callback.message.answer(t("moderator.no_events"), reply_markup=moderator_settings_keyboard())
        return
    if callback.message:
        await _clear_notice_message(state, callback.message.bot)
    current = stack[-1] if stack else None
    if current == "fields":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.field_choice_prompt"),
                edit_field_choice_keyboard(event_id),
            )
        await state.set_state(EditEventState.selecting_field)
    elif current == "images":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.field_choice_prompt"),
                edit_field_choice_keyboard(event_id),
            )
        await state.update_data(new_image_file_ids=[])
        await state.set_state(EditEventState.selecting_field)
    elif current == "promocodes":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("promocode.admin.menu_prompt"),
                manage_promocode_actions_keyboard(event_id),
            )
        await state.set_state(EditEventState.selecting_field)
    elif current == "participants":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.event_options_prompt"),
                manage_event_actions_keyboard(event_id),
            )
        await state.update_data(edit_stack=["actions"])
        await state.set_state(EditEventState.selecting_field)
    elif current == "actions":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.event_options_prompt"),
                manage_event_actions_keyboard(event_id),
            )
        await state.update_data(edit_stack=["actions"])
        await state.set_state(EditEventState.selecting_field)
    elif current == "cancel":
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.event_options_prompt"),
                manage_event_actions_keyboard(event_id),
            )
        await state.update_data(edit_stack=["actions"])
        await state.set_state(EditEventState.selecting_field)
    else:
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.field_choice_prompt"),
                edit_field_choice_keyboard(event_id),
            )
        await state.set_state(EditEventState.selecting_field)
    
    total_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"[edit_back] COMPLETED: total_elapsed={total_time:.3f}s")


@router.message(EditEventState.value_input)
async def process_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    field = data.get("edit_field")
    if not event_id or not field:
        await message.answer(t("error.edit_context_lost"), reply_markup=moderator_settings_keyboard())
        await state.clear()
        return
    try:
        updates = _parse_edit_value(field, message)
    except ValueError as error:
        await _send_prompt_text(
            message,
            state,
            str(error),
            edit_step_keyboard(),
        )
        await safe_delete(message)
        return
    services = get_services()
    if field == "time" and "time" in updates:
        current_event = await services.events.get_event(event_id)
        if current_event and current_event.end_time:
            new_time = updates["time"]
            if new_time:
                if new_time > current_event.end_time:
                    await _send_prompt_text(
                        message,
                        state,
                        t("edit.time_after_period_error"),
                        edit_step_keyboard(),
                    )
                    await safe_delete(message)
                    return
                updates["end_time"] = current_event.end_time
    event = await services.events.update_event(event_id, updates)
    if event is None:
        await _send_prompt_text(
            message,
            state,
            t("edit.update_failed"),
            moderator_settings_keyboard(),
        )
        await safe_delete(message)
        await state.clear()
        return
    value_text = escape((message.text or "").strip())
    success_notice = t("notify.event_update_notice", field=_field_label(field), title=event.title, value=value_text)
    admin_notice = _admin_success_message(field)
    await _notify_event_update(message, state, event, success_notice, show_to_moderator=False)
    await state.update_data(edit_stack=["actions"], edit_field=None)
    await state.set_state(EditEventState.selecting_field)
    await _send_admin_success_prompt(message, state, admin_notice, event_id)
    await safe_delete(message)


@router.message(EditEventState.image_upload)
async def process_edit_images(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    images = list(data.get("new_image_file_ids", []))
    if message.photo:
        if len(images) >= MAX_EVENT_IMAGES:
            dirty = data.get("images_dirty", False)
            await _update_prompt_message(
                message,
                state,
                t("edit.image_limit_reached", limit=MAX_EVENT_IMAGES),
                edit_images_keyboard(len(images) > 0, dirty),
            )
            await safe_delete(message)
            return
        images.append(message.photo[-1].file_id)
        await state.update_data(new_image_file_ids=images, images_dirty=True)
        await _render_edit_image_prompt(message, state)
        await safe_delete(message)
        return
    text_raw = (message.text or "").strip()
    lowered = text_raw.lower()
    if lowered in {"очистить", "clear"}:
        data = await state.get_data()
        event_id = data.get("edit_event_id")
        if not event_id:
            await message.answer(t("error.context_lost_alert"), reply_markup=moderator_settings_keyboard())
            await state.clear()
            await safe_delete(message)
            return
        services = get_services()
        event = await services.events.update_event(event_id, {"image_file_ids": []})
        if event is None:
            await _send_prompt_text(
                message,
                state,
                t("error.save_failed"),
                moderator_settings_keyboard(),
            )
            await safe_delete(message)
            await state.clear()
            return
        await state.update_data(new_image_file_ids=[], images_dirty=False)
        await _update_prompt_message(
            message,
            state,
            t("edit.images_cleared", limit=MAX_EVENT_IMAGES, count=0),
            edit_images_keyboard(False, False),
        )
        await safe_delete(message)
        return
    dirty = data.get("images_dirty", False)
    await _update_prompt_message(
        message,
        state,
        t("edit.image_invalid_error"),
        edit_images_keyboard(len(images) > 0, dirty),
    )
    await safe_delete(message)


@router.callback_query(F.data == EDIT_EVENT_CLEAR_IMAGES)
async def clear_edit_images_callback(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[clear_edit_images_callback] START: user_id={user_id}")
    current_state = await state.get_state()
    if current_state != EditEventState.image_upload.state:
        return
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await callback.answer(t("error.context_lost_alert"), show_alert=True)
        await state.clear()
        return
    services = get_services()
    event = await services.events.update_event(event_id, {"image_file_ids": []})
    if event is None:
        await callback.answer(t("error.save_failed"), show_alert=True)
        return
    await state.update_data(new_image_file_ids=[], images_dirty=False)
    if callback.message:
        await _update_prompt_message(
            callback.message,
            state,
            t("edit.images_cleared", limit=MAX_EVENT_IMAGES, count=0),
            edit_images_keyboard(False, False),
        )


@router.callback_query(F.data == EDIT_EVENT_SAVE)
async def handle_edit_save(callback: CallbackQuery, state: FSMContext) -> None:
    start_time = datetime.now()
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(f"[handle_edit_save] START: user_id={user_id}")
    current_state = await state.get_state()
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await callback.answer(t("error.context_lost_alert"), show_alert=True)
        await state.clear()
        return
    services = get_services()
    if current_state == EditEventState.reminders.state:
        updates = {
            "reminder_3days": data.get("reminder_3days", False),
            "reminder_1day": data.get("reminder_1day", False),
        }
        event = await services.events.update_event(event_id, updates)
        if event is None:
            await callback.answer(t("error.save_failed"), show_alert=True)
            return
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            success_notice = t("edit.reminders_saved")
            admin_notice = _admin_success_message("reminders")
            await _notify_event_update(callback.message, state, event, success_notice, show_to_moderator=False)
            await _send_admin_success_prompt(callback.message, state, admin_notice, event_id)
        await state.update_data(edit_stack=["actions"])
        await state.set_state(EditEventState.selecting_field)
        return
    if current_state == EditEventState.image_upload.state:
        image_list = list(data.get("new_image_file_ids", []))
        event = await services.events.update_event(event_id, {"image_file_ids": image_list})
        if event is None:
            await callback.answer(t("error.save_failed"), show_alert=True)
            return
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            success_notice = t("edit.images_saved")
            admin_notice = _admin_success_message("image")
            await _notify_event_update(
                callback.message,
                state,
                event,
                success_notice,
                show_to_moderator=False,
            )
            await _send_admin_success_prompt(callback.message, state, admin_notice, event_id)
        await state.update_data(
            edit_stack=["actions"],
            new_image_file_ids=[],
            edit_field=None,
            images_dirty=False,
        )
        await state.set_state(EditEventState.selecting_field)
        return


async def _clear_notice_message(state: FSMContext, bot) -> None:
    data = await state.get_data()
    notice_id = data.get(NOTICE_KEY)
    notice_chat = data.get(NOTICE_CHAT_KEY)
    if notice_id and notice_chat and bot:
        await safe_delete_message(bot, notice_chat, notice_id)
    await state.update_data(**{NOTICE_KEY: None, NOTICE_CHAT_KEY: None})


async def _remove_prompt_message(message: Message | None, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_id = data.get(PROMPT_KEY)
    prompt_chat = data.get(PROMPT_CHAT_KEY)
    bot = message.bot if message else None
    chat_id = message.chat.id if message else None
    target_chat = prompt_chat or chat_id
    if prompt_id and target_chat and bot:
        await safe_delete_message(bot, target_chat, prompt_id)
    await state.update_data(**{PROMPT_KEY: None, PROMPT_CHAT_KEY: None})


async def _set_prompt_message(state: FSMContext, message: Message | None) -> None:
    await state.update_data(
        **{
            PROMPT_KEY: message.message_id if message else None,
            PROMPT_CHAT_KEY: message.chat.id if message else None,
        }
    )


async def _send_prompt_text(message: Message, state: FSMContext, text: str, reply_markup) -> Message:
    await _remove_prompt_message(message, state)
    sent = await message.answer(text, reply_markup=reply_markup)
    await _set_prompt_message(state, sent)
    return sent


async def _update_prompt_message(message: Message, state: FSMContext, text: str, reply_markup) -> None:
    data = await state.get_data()
    prompt_id = data.get(PROMPT_KEY)
    prompt_chat = data.get(PROMPT_CHAT_KEY)
    bot = message.bot
    if prompt_id and prompt_chat and bot:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=prompt_chat,
                message_id=prompt_id,
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest:
            pass
    await _send_prompt_text(message, state, text, reply_markup)


async def _render_create_image_prompt(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    count = len(data.get("image_file_ids", []))
    await _update_prompt_message(
        message,
        state,
        t("create.image_prompt", limit=MAX_EVENT_IMAGES, count=count),
        create_step_keyboard(
            back_enabled=True,
            skip_enabled=True,
            confirm_enabled=count > 0,
        ),
    )


async def _render_edit_image_prompt(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    count = len(data.get("new_image_file_ids", []))
    dirty = data.get("images_dirty", False)
    await _update_prompt_message(
        message,
        state,
        t("edit.prompt_image", limit=MAX_EVENT_IMAGES, count=count),
        edit_images_keyboard(count > 0, dirty),
    )


def _admin_success_message(field: str) -> str:
    mapping = {
        "title": t("edit.success.title"),
        "date": t("edit.success.date"),
        "time": t("edit.success.time"),
        "period": t("edit.success.period"),
        "place": t("edit.success.place"),
        "description": t("edit.success.description"),
        "cost": t("edit.success.cost"),
        "image": t("edit.success.image"),
        "limit": t("edit.success.limit"),
        "reminders": t("edit.success.reminders"),
    }
    return mapping.get(field, t("edit.success.description"))


async def _send_admin_success_prompt(message: Message, state: FSMContext, text: str, event_id: int) -> None:
    await _send_prompt_text(
        message,
        state,
        text,
        manage_event_actions_keyboard(event_id),
    )


async def _store_preview_media(state: FSMContext, messages: list[Message]) -> None:
    if not messages:
        return
    entries = [{"chat_id": msg.chat.id, "message_id": msg.message_id} for msg in messages]
    data = await state.get_data()
    existing = list(data.get(PREVIEW_MEDIA_KEY, []))
    existing.extend(entries)
    await state.update_data(**{PREVIEW_MEDIA_KEY: existing})


async def _clear_preview_media(state: FSMContext, bot) -> None:
    data = await state.get_data()
    entries = list(data.get(PREVIEW_MEDIA_KEY, []))
    if bot:
        for entry in entries:
            await safe_delete_by_id(bot, entry.get("chat_id"), entry.get("message_id"))
    await state.update_data(**{PREVIEW_MEDIA_KEY: []})


async def _send_prompt_photo(message: Message, state: FSMContext, photo: str, caption: str, reply_markup) -> Message:
    await _remove_prompt_message(message, state)
    sent = await message.answer_photo(photo, caption=caption, reply_markup=reply_markup)
    await _set_prompt_message(state, sent)
    return sent


async def _notify_new_event(callback: CallbackQuery, event: Event) -> None:
    services = get_services()
    bot = callback.message.bot if callback.message else callback.bot
    creator_id = callback.from_user.id if callback.from_user else None
    text = t("notify.new_event", title=event.title)
    markup = new_event_notification_keyboard(event.id)
    telegram_ids = await services.users.list_all_telegram_ids()
    for telegram_id in telegram_ids:
        if creator_id and telegram_id == creator_id:
            continue
        try:
            await bot.send_message(telegram_id, text, reply_markup=markup)
        except Exception:
            continue


async def _notify_event_update(message: Message, state: FSMContext, event: Event, notice: str, show_to_moderator: bool = True) -> None:
    await _clear_notice_message(state, message.bot)
    if show_to_moderator:
        notice_message = await message.answer(notice)
        await state.update_data(
            **{
                NOTICE_KEY: notice_message.message_id,
                NOTICE_CHAT_KEY: notice_message.chat.id,
            }
        )
    services = get_services()
    bot = message.bot
    telegram_ids = await services.registrations.list_participant_telegram_ids(event.id)
    editor_chat_id = message.chat.id
    broadcast_text = notice
    markup = new_event_notification_keyboard(event.id)
    for telegram_id in telegram_ids:
        if telegram_id == editor_chat_id:
            continue
        try:
            await bot.send_message(telegram_id, broadcast_text, reply_markup=markup)
        except Exception:
            continue


async def _notify_cancellation(callback: CallbackQuery, event: Event) -> None:
    services = get_services()
    bot = callback.message.bot if callback.message else callback.bot
    telegram_ids = await services.registrations.list_participant_telegram_ids(event.id)
    cancel_text = t("notify.event_cancelled", title=event.title)
    markup = hide_message_keyboard()
    for telegram_id in telegram_ids:
        try:
            await bot.send_message(telegram_id, cancel_text, reply_markup=markup)
        except Exception:
            continue


async def _prompt_create_state(message: Message, state: FSMContext, target_state: Any) -> None:
    if target_state == CreateEventState.title:
        await _send_prompt_text(message, state, t("create.title_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.date:
        await _send_prompt_text(message, state, t("create.date_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.time:
        await _send_prompt_text(
            message,
            state,
            t("create.time_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.period:
        await _send_prompt_text(
            message,
            state,
            t("create.period_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.place:
        await _send_prompt_text(
            message,
            state,
            t("create.place_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.description:
        await _send_prompt_text(
            message,
            state,
            t("create.description_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.cost:
        await _send_prompt_text(
            message,
            state,
            t("create.cost_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.image:
        await _render_create_image_prompt(message, state)
    elif target_state == CreateEventState.limit:
        await _send_prompt_text(
            message,
            state,
            t("create.limit_prompt"),
            create_step_keyboard(back_enabled=True, skip_enabled=True),
        )
    elif target_state == CreateEventState.reminders:
        await _prompt_reminders(message, state)
    elif target_state == CreateEventState.preview:
        await _send_preview(message, state)


async def _push_create_history(state: FSMContext, current_state: Any) -> None:
    data = await state.get_data()
    history = list(data.get("history", []))
    history.append(current_state.state)
    await state.update_data(history=history)


async def _prompt_reminders(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected_3 = data.get("reminder_3days", False)
    selected_1 = data.get("reminder_1day", False)
    await _send_prompt_text(
        message,
        state,
        t("create.reminders_prompt"),
        create_reminders_keyboard(selected_3, selected_1),
    )


async def _toggle_reminder(state: FSMContext, key: str) -> None:
    data = await state.get_data()
    current = data.get(key, False)
    await state.update_data(**{key: not current})


async def _edit_reminder_markup(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected_3 = data.get("reminder_3days", False)
    selected_1 = data.get("reminder_1day", False)
    prompt_id = data.get(PROMPT_KEY)
    if not prompt_id:
        return
    if callback.message:
        markup = (
            edit_reminders_keyboard(selected_3, selected_1)
            if data.get("edit_stack")
            else create_reminders_keyboard(selected_3, selected_1)
        )
        await callback.bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=prompt_id,
            reply_markup=markup,
        )


async def _send_preview(message: Message, state: FSMContext) -> None:
    services = get_services()
    data = await state.get_data()
    payload = _build_event_payload(data)
    cost_value = payload.get("cost")
    images = tuple(payload.get("image_file_ids", ()))
    event = Event(
        id=0,
        title=payload["title"],
        date=payload["date"],
        time=payload["time"],
        end_date=payload.get("end_date"),
        end_time=payload.get("end_time"),
        place=payload.get("place"),
        description=payload.get("description"),
        cost=float(cost_value) if cost_value is not None else None,
        image_file_id=payload.get("image_file_id"),
        image_file_ids=images,
        max_participants=payload.get("max_participants"),
        reminder_3days=payload.get("reminder_3days", False),
        reminder_1day=payload.get("reminder_1day", False),
        reminder_3days_sent_at=None,
        reminder_1day_sent_at=None,
        status="active",
    )
    stats = RegistrationStats(going=0, not_going=0)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    markup = create_preview_keyboard()
    await _clear_preview_media(state, message.bot)
    if images:
        await _remove_prompt_message(message, state)
        stored_messages: list[Message] = []
        if len(images) == 1:
            sent = await message.answer_photo(images[0])
            stored_messages.append(sent)
        else:
            media = [InputMediaPhoto(media=file_id) for file_id in images]
            media_messages = await message.answer_media_group(media)
            stored_messages.extend(media_messages)
        await _store_preview_media(state, stored_messages)
    await _send_prompt_text(message, state, text, markup)


def _build_event_payload(data: dict[str, Any]) -> dict[str, Any]:
    images = tuple(data.get("image_file_ids", []))
    logger.info(f"[_build_event_payload] Building payload: images_count={len(images)}")
    return {
        "title": data.get("title"),
        "date": data.get("event_date"),
        "time": data.get("event_time"),
        "end_date": data.get("event_end_date"),
        "end_time": data.get("event_end_time"),
        "place": data.get("place"),
        "description": data.get("description"),
        "cost": data.get("cost"),
        "image_file_ids": images,
        "image_file_id": images[0] if images else None,
        "max_participants": data.get("limit"),
        "reminder_3days": data.get("reminder_3days", False),
        "reminder_1day": data.get("reminder_1day", False),
        "status": "active",
    }


T = TypeVar("T")


def _parse_range_input(value: str, parser: Callable[[str], T]) -> tuple[T, Optional[T]]:
    normalized = value.replace("—", "-").replace("–", "-")
    stripped = normalized.strip()
    if "-" not in stripped:
        cleaned = stripped.strip('"')
        return parser(cleaned), None
    left_raw, right_raw = stripped.split("-", 1)
    left = left_raw.strip().strip('"')
    right = right_raw.strip().strip('"')
    if not left or not right:
        raise ValueError
    start = parser(left)
    end = parser(right)
    return start, end


def _parse_date_input(value: str) -> tuple[date, Optional[date]]:
    pattern = t("format.input_date")
    start, end = _parse_range_input(value, lambda chunk: datetime.strptime(chunk, pattern).date())
    if end is not None and end < start:
        raise ValueError
    return start, end


def _parse_single_time(value: str) -> time:
    if "-" in value.replace("—", "-").replace("–", "-"):
        raise ValueError
    pattern = t("format.input_time")
    cleaned = value.strip().strip('"')
    return datetime.strptime(cleaned, pattern).time()


def _parse_period_input(value: str) -> tuple[time, time]:
    pattern = t("format.input_time")
    start, end = _parse_range_input(value, lambda chunk: datetime.strptime(chunk, pattern).time())
    if end is None:
        raise ValueError
    if end < start:
        raise ValueError
    return start, end


async def _ensure_event_context(state: FSMContext, event_id: int) -> None:
    data = await state.get_data()
    if data.get("edit_event_id") != event_id:
        await state.update_data(edit_event_id=event_id, edit_stack=["actions"])


async def _push_edit_stack(state: FSMContext, value: str) -> None:
    data = await state.get_data()
    stack = list(data.get("edit_stack", []))
    stack.append(value)
    await state.update_data(edit_stack=stack)


async def _prompt_edit_reminders(message: Message, state: FSMContext, event_id: int) -> None:
    services = get_services()
    event = await services.events.get_event(event_id)
    reminder_3 = event.reminder_3days if event else False
    reminder_1 = event.reminder_1day if event else False
    await state.update_data(reminder_3days=reminder_3, reminder_1day=reminder_1)
    await _send_prompt_text(
        message,
        state,
        t("edit.reminders_prompt"),
        edit_reminders_keyboard(reminder_3, reminder_1),
    )


def _edit_prompt_for(field: str) -> str:
    prompts = {
        "title": t("edit.prompt_title"),
        "date": t("edit.prompt_date"),
        "time": t("edit.prompt_time"),
        "period": t("edit.prompt_period"),
        "place": t("edit.prompt_place"),
        "description": t("edit.prompt_description"),
        "cost": t("edit.prompt_cost"),
        "image": t("edit.prompt_image", limit=MAX_EVENT_IMAGES, count=0),
        "limit": t("edit.prompt_limit"),
    }
    return prompts.get(field, t("edit.prompt_value_fallback"))


def _compose_edit_prompt(event: Event | None, field: str) -> str:
    prompt = _edit_prompt_for(field)
    current = _current_value_text(field, event)
    if current:
        return f"{current}\n\n{prompt}"
    return prompt


def _current_value_text(field: str, event: Event | None) -> str | None:
    if event is None:
        return None
    empty = t("edit.current.empty")
    if field == "title":
        return t("edit.current.title", value=event.title or empty)
    if field == "date":
        return t("edit.current.date", value=_format_date_value(event))
    if field == "time":
        value = _format_time_value(event) or empty
        return t("edit.current.time", value=value)
    if field == "period":
        value = _format_period_value(event) or empty
        return t("edit.current.period", value=value)
    if field == "place":
        return t("edit.current.place", value=event.place or empty)
    if field == "description":
        return t("edit.current.description", value=event.description or empty)
    if field == "cost":
        return t("edit.current.cost", value=_format_cost_value(event.cost))
    if field == "limit":
        return t("edit.current.limit", value=_format_limit_value(event.max_participants))
    return None


def _format_date_value(event: Event) -> str:
    pattern = t("format.display_date")
    start = event.date.strftime(pattern)
    if event.end_date and event.end_date != event.date:
        end = event.end_date.strftime(pattern)
        return f"{start} — {end}"
    return start


def _format_time_value(event: Event) -> str | None:
    pattern = t("format.display_time")
    if event.time:
        return event.time.strftime(pattern)
    if event.end_time:
        return event.end_time.strftime(pattern)
    return None


def _format_period_value(event: Event) -> str | None:
    if not event.end_time:
        return None
    pattern = t("format.display_time")
    end = event.end_time.strftime(pattern)
    if event.time:
        start = event.time.strftime(pattern)
        return f"{start} — {end}"
    return end


def _format_cost_value(value: float | None) -> str:
    if value is None or value <= 0:
        return t("edit.current.free")
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _format_limit_value(value: int | None) -> str:
    if value is None or value <= 0:
        return t("edit.current.unlimited")
    return str(value)


def _field_label(field: str) -> str:
    labels = {
        "title": t("button.field.title"),
        "date": t("button.field.date"),
        "time": t("button.field.time"),
        "period": t("button.field.period"),
        "place": t("button.field.place"),
        "description": t("button.field.description"),
        "cost": t("button.field.cost"),
        "image": t("button.field.image"),
        "limit": t("button.field.limit"),
        "reminders": t("button.field.reminders"),
    }
    return labels.get(field, field)


def _parse_edit_value(field: str, message: Message) -> dict[str, Any]:
    if field == "title":
        value = (message.text or "").strip()
        if not value:
            raise ValueError(t("edit.title_empty_error"))
        return {field: value}
    if field == "place":
        value = (message.text or "").strip()
        if not value or value.lower() in {"пропустить", "skip"}:
            return {"place": None}
        return {"place": value}
    if field == "description":
        return {field: (message.text or "").strip() or None}
    if field == "cost":
        raw_text = (message.text or "").strip()
        if not raw_text or raw_text.lower() in {"пропустить", "skip"}:
            return {"cost": None}
        text = raw_text.replace(" ", "").replace(",", ".")
        try:
            cost = Decimal(text)
            if cost < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise ValueError(t("edit.cost_invalid_error"))
        return {field: cost}
    if field == "limit":
        text = (message.text or "").strip()
        if not text or text.lower() in {"пропустить", "skip"}:
            return {"max_participants": None}
        try:
            value = int(text)
        except ValueError as error:
            raise ValueError(t("edit.limit_invalid_error")) from error
        return {"max_participants": value if value > 0 else None}
    if field == "date":
        text = (message.text or "").strip()
        try:
            start_date, end_date = _parse_date_input(text)
        except ValueError as error:
            raise ValueError(t("edit.date_invalid_error")) from error
        today = date.today()
        if start_date < today:
            raise ValueError(t("edit.date_past_error"))
        return {"date": start_date, "end_date": end_date}
    if field == "time":
        text = (message.text or "").strip()
        lowered = text.lower()
        if not text or lowered in {"пропустить", "skip"}:
            return {"time": None, "end_time": None}
        try:
            parsed_time = _parse_single_time(text)
        except ValueError as error:
            raise ValueError(t("edit.time_invalid_error")) from error
        return {"time": parsed_time}
    if field == "period":
        text = (message.text or "").strip()
        lowered = text.lower()
        if not text or lowered in {"пропустить", "skip"}:
            return {"end_time": None}
        try:
            start_time, end_time = _parse_period_input(text)
        except ValueError as error:
            raise ValueError(t("edit.period_invalid_error")) from error
        return {"time": start_time, "end_time": end_time}
    if field == "image":
        if not message.photo:
            raise ValueError(t("edit.image_invalid_error"))
        return {"image_file_ids": [message.photo[-1].file_id]}
    raise ValueError(t("edit.unknown_field_error"))

