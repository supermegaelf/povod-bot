from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.repositories.events import Event
from database.repositories.registrations import RegistrationStats
from handlers.states import CreateEventState, EditEventState
from keyboards import (
    cancel_event_keyboard,
    create_preview_keyboard,
    create_reminders_keyboard,
    create_step_keyboard,
    edit_field_choice_keyboard,
    edit_reminders_keyboard,
    edit_step_keyboard,
    manage_event_actions_keyboard,
    manage_events_keyboard,
    moderator_settings_keyboard,
)
from utils.callbacks import (
    CREATE_EVENT_BACK,
    CREATE_EVENT_CANCEL,
    CREATE_EVENT_PUBLISH,
    CREATE_EVENT_REMINDER_DONE,
    CREATE_EVENT_REMINDER_TOGGLE_1,
    CREATE_EVENT_REMINDER_TOGGLE_3,
    EDIT_EVENT_CANCEL_EVENT_PREFIX,
    EDIT_EVENT_CONFIRM_CANCEL_PREFIX,
    EDIT_EVENT_FIELD_PREFIX,
    EDIT_EVENT_PREFIX,
    EDIT_EVENT_BACK,
    EDIT_EVENT_CANCEL,
    EDIT_EVENT_SAVE,
    SETTINGS_CREATE_EVENT,
    SETTINGS_MANAGE_EVENTS,
    extract_event_id,
    extract_event_id_and_field,
)
from utils.di import get_services
from utils.formatters import format_event_card
from utils.messaging import safe_delete, safe_delete_message
from utils.i18n import t

router = Router()

PROMPT_KEY = "prompt_message_id"


CREATE_STATE_SEQUENCE = [
    CreateEventState.title,
    CreateEventState.datetime,
    CreateEventState.place,
    CreateEventState.description,
    CreateEventState.cost,
    CreateEventState.image,
    CreateEventState.limit,
    CreateEventState.reminders,
    CreateEventState.preview,
]

CREATE_STATE_BY_NAME = {state.state: state for state in CREATE_STATE_SEQUENCE}


@router.callback_query(F.data == SETTINGS_CREATE_EVENT)
async def start_create_event(callback: CallbackQuery, state: FSMContext) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    if not services.users.is_moderator(user):
        await callback.answer(t("common.no_permissions"), show_alert=True)
        return
    await state.clear()
    await state.update_data(history=[])
    await state.set_state(CreateEventState.title)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("create.title_prompt"),
            create_step_keyboard(back_enabled=True),
        )
    await callback.answer()


@router.callback_query(F.data == CREATE_EVENT_BACK)
async def create_event_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    history = list(data.get("history", []))
    if not history:
        await state.clear()
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
        await callback.answer()
        return
    target_state_name = history.pop()
    await state.update_data(history=history)
    target_state = CREATE_STATE_BY_NAME[target_state_name]
    await state.set_state(target_state)
    if callback.message:
        await safe_delete(callback.message)
        await _prompt_create_state(callback.message, state, target_state)
    await callback.answer()


@router.callback_query(F.data == CREATE_EVENT_CANCEL)
async def create_event_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        await safe_delete(callback.message)
        await callback.message.answer(t("create.cancelled"), reply_markup=moderator_settings_keyboard())
    await state.clear()
    await callback.answer()


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
    await state.set_state(CreateEventState.datetime)
    await _send_prompt_text(
        message,
        state,
        t("create.datetime_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.datetime)
async def process_create_datetime(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        combined = datetime.strptime(text, t("format.input_datetime"))
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.datetime_invalid"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.datetime)
    await state.update_data(event_date=combined.date(), event_time=combined.time())
    await state.set_state(CreateEventState.place)
    await _send_prompt_text(
        message,
        state,
        t("create.place_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.place)
async def process_create_place(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await _send_prompt_text(
            message,
            state,
            t("create.place_empty"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.place)
    await state.update_data(place=text)
    await state.set_state(CreateEventState.description)
    await _send_prompt_text(
        message,
        state,
        t("create.description_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.description)
async def process_create_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    await _push_create_history(state, CreateEventState.description)
    await state.update_data(description=text if text else None)
    await state.set_state(CreateEventState.cost)
    await _send_prompt_text(
        message,
        state,
        t("create.cost_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.cost)
async def process_create_cost(message: Message, state: FSMContext) -> None:
    text = (message.text or "0").replace(" ", "").replace(",", ".")
    try:
        cost = Decimal(text)
        if cost < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await _send_prompt_text(
            message,
            state,
            t("create.cost_invalid"),
            create_step_keyboard(back_enabled=True),
        )
        await safe_delete(message)
        return
    await _push_create_history(state, CreateEventState.cost)
    await state.update_data(cost=cost)
    await state.set_state(CreateEventState.image)
    await _send_prompt_text(
        message,
        state,
        t("create.image_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.image)
async def process_create_image(message: Message, state: FSMContext) -> None:
    file_id: Optional[str] = None
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        text = (message.text or "").strip().lower()
        if text not in {"", "пропустить", "skip"}:
            await _send_prompt_text(
                message,
                state,
                t("create.image_invalid"),
                create_step_keyboard(back_enabled=True),
            )
            await safe_delete(message)
            return
    await _push_create_history(state, CreateEventState.image)
    await state.update_data(image_file_id=file_id)
    await state.set_state(CreateEventState.limit)
    await _send_prompt_text(
        message,
        state,
        t("create.limit_prompt"),
        create_step_keyboard(back_enabled=True),
    )
    await safe_delete(message)


@router.message(CreateEventState.limit)
async def process_create_limit(message: Message, state: FSMContext) -> None:
    text = (message.text or "0").strip()
    try:
        value = int(text)
    except ValueError:
        await _send_prompt_text(
            message,
            state,
            t("create.limit_invalid"),
            create_step_keyboard(back_enabled=True),
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
    await _toggle_reminder(state, key="reminder_3days")
    await _edit_reminder_markup(callback, state)


@router.callback_query(F.data == CREATE_EVENT_REMINDER_TOGGLE_1)
async def toggle_create_reminder_1(callback: CallbackQuery, state: FSMContext) -> None:
    await _toggle_reminder(state, key="reminder_1day")
    await _edit_reminder_markup(callback, state)


@router.callback_query(F.data == CREATE_EVENT_REMINDER_DONE)
async def finish_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    await _push_create_history(state, CreateEventState.reminders)
    await state.set_state(CreateEventState.preview)
    if callback.message:
        await _send_preview(callback.message, state)
        await safe_delete(callback.message)
    await callback.answer()


@router.callback_query(F.data == CREATE_EVENT_PUBLISH)
async def publish_event(callback: CallbackQuery, state: FSMContext) -> None:
    services = get_services()
    data = await state.get_data()
    payload = _build_event_payload(data)
    event = await services.events.create_event(payload)
    await _notify_new_event(callback, event)
    prompt_id = data.get(PROMPT_KEY)
    if prompt_id and callback.message:
        await safe_delete_message(callback.bot, callback.message.chat.id, prompt_id)
        await state.update_data(**{PROMPT_KEY: None})
    if callback.message:
        await safe_delete(callback.message)
        await callback.message.answer(t("create.published"), reply_markup=moderator_settings_keyboard())
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == SETTINGS_MANAGE_EVENTS)
async def open_manage_events(callback: CallbackQuery, state: FSMContext) -> None:
    services = get_services()
    tg_user = callback.from_user
    user = await services.users.ensure(tg_user.id, tg_user.username)
    if not services.users.is_moderator(user):
        await callback.answer(t("common.no_permissions"), show_alert=True)
        return
    await state.clear()
    events = await services.events.get_active_events(limit=20)
    if not events:
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            await callback.message.answer(t("moderator.no_events"), reply_markup=moderator_settings_keyboard())
        await callback.answer()
        return
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            t("menu.event_selection_prompt"),
            manage_events_keyboard(events),
        )
    await state.update_data(edit_stack=[])
    await callback.answer()


@router.callback_query(F.data.startswith(EDIT_EVENT_FIELD_PREFIX))
async def handle_edit_entry(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
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
        await callback.answer()
        return
    if field == "reminders":
        await _push_edit_stack(state, "reminders")
        await state.set_state(EditEventState.reminders)
        if callback.message:
            await safe_delete(callback.message)
            await _prompt_edit_reminders(callback.message, state, event_id)
        await callback.answer()
        return
    await _push_edit_stack(state, "value")
    await state.set_state(EditEventState.value_input)
    await state.update_data(edit_field=field)
    if callback.message:
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            _edit_prompt_for(field),
            edit_step_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith(EDIT_EVENT_PREFIX))
async def open_event_actions(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return
    event_id = extract_event_id(callback.data, EDIT_EVENT_PREFIX)
    services = get_services()
    event = await services.events.get_event(event_id)
    if event is None:
        await callback.answer(t("error.event_not_found"), show_alert=True)
        return
    await state.clear()
    await state.update_data(edit_event_id=event_id, edit_stack=["actions"])
    await state.set_state(EditEventState.selecting_field)
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        await safe_delete(callback.message)
        await _send_prompt_text(
            callback.message,
            state,
            event.title,
            manage_event_actions_keyboard(event_id),
        )
    await callback.answer()


@router.callback_query(F.data == EDIT_EVENT_BACK)
async def edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    stack = list(data.get("edit_stack", []))
    if not stack:
        if callback.message:
            await _remove_prompt_message(callback.message, state)
            await safe_delete(callback.message)
            await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
        await state.clear()
        await callback.answer()
        return
    stack.pop()
    await state.update_data(edit_stack=stack)
    event_id = data.get("edit_event_id")
    if not event_id:
        await state.clear()
        await callback.answer()
        return
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
    elif current == "actions" or current is None:
        if callback.message:
            await safe_delete(callback.message)
            await _send_prompt_text(
                callback.message,
                state,
                t("edit.event_options_prompt"),
                manage_event_actions_keyboard(event_id),
            )
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
    await callback.answer()


@router.callback_query(F.data == EDIT_EVENT_CANCEL)
async def edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        await safe_delete(callback.message)
        await callback.message.answer(t("moderator.settings_title"), reply_markup=moderator_settings_keyboard())
    await callback.answer()


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
    await _notify_event_update(message, event, t("notify.event_update_notice", field=field))
    await state.update_data(edit_stack=["actions"], edit_field=None)
    await state.set_state(EditEventState.selecting_field)
    await _send_prompt_text(
        message,
        state,
        t("edit.event_options_prompt"),
        manage_event_actions_keyboard(event_id),
    )
    await safe_delete(message)


@router.callback_query(F.data == EDIT_EVENT_SAVE)
async def save_edit_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data.get("edit_event_id")
    if not event_id:
        await callback.answer(t("error.context_lost_alert"), show_alert=True)
        await state.clear()
        return
    updates = {
        "reminder_3days": data.get("reminder_3days", False),
        "reminder_1day": data.get("reminder_1day", False),
    }
    services = get_services()
    event = await services.events.update_event(event_id, updates)
    if event is None:
        await callback.answer(t("error.save_failed"), show_alert=True)
        return
    if callback.message:
        await _remove_prompt_message(callback.message, state)
        await safe_delete(callback.message)
        await _notify_event_update(callback.message, event, t("edit.reminders_saved"))
        await _send_prompt_text(
            callback.message,
            state,
            t("edit.event_options_prompt"),
            manage_event_actions_keyboard(event_id),
        )
    await state.update_data(edit_stack=["actions"])
    await state.set_state(EditEventState.selecting_field)
    await callback.answer()


@router.callback_query(F.data.startswith(EDIT_EVENT_CANCEL_EVENT_PREFIX))
async def confirm_cancel_request(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
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
    await callback.answer()


@router.callback_query(F.data.startswith(EDIT_EVENT_CONFIRM_CANCEL_PREFIX))
async def cancel_event_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
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
        await safe_delete(callback.message)
        await callback.message.answer(t("edit.event_cancelled_confirm"), reply_markup=moderator_settings_keyboard())
    await callback.answer()


async def _remove_prompt_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_id = data.get(PROMPT_KEY)
    if prompt_id:
        await safe_delete_message(message.bot, message.chat.id, prompt_id)
        await state.update_data(**{PROMPT_KEY: None})


async def _set_prompt_message(state: FSMContext, message_id: int | None) -> None:
    await state.update_data(**{PROMPT_KEY: message_id})


async def _send_prompt_text(message: Message, state: FSMContext, text: str, reply_markup) -> Message:
    await _remove_prompt_message(message, state)
    sent = await message.answer(text, reply_markup=reply_markup)
    await _set_prompt_message(state, sent.message_id)
    return sent


async def _send_prompt_photo(message: Message, state: FSMContext, photo: str, caption: str, reply_markup) -> Message:
    await _remove_prompt_message(message, state)
    sent = await message.answer_photo(photo, caption=caption, reply_markup=reply_markup)
    await _set_prompt_message(state, sent.message_id)
    return sent


async def _notify_new_event(callback: CallbackQuery, event: Event) -> None:
    services = get_services()
    bot = callback.message.bot if callback.message else callback.bot
    stats = RegistrationStats(going=0, not_going=0)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    telegram_ids = await services.users.list_all_telegram_ids()
    for telegram_id in telegram_ids:
        try:
            if event.image_file_id:
                await bot.send_photo(telegram_id, event.image_file_id, caption=text)
            else:
                await bot.send_message(telegram_id, text)
        except Exception:
            continue


async def _notify_event_update(message: Message, event: Event, notice: str) -> None:
    services = get_services()
    await message.answer(notice)
    bot = message.bot
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    telegram_ids = await services.registrations.list_participant_telegram_ids(event.id)
    for telegram_id in telegram_ids:
        try:
            if event.image_file_id:
                await bot.send_photo(
                    telegram_id,
                    event.image_file_id,
                    caption=t("notify.event_update_broadcast", details=text),
                )
            else:
                await bot.send_message(
                    telegram_id,
                    t("notify.event_update_broadcast", details=text),
                )
        except Exception:
            continue


async def _notify_cancellation(callback: CallbackQuery, event: Event) -> None:
    services = get_services()
    bot = callback.message.bot if callback.message else callback.bot
    telegram_ids = await services.registrations.list_participant_telegram_ids(event.id)
    cancel_text = t("notify.event_cancelled", title=event.title)
    for telegram_id in telegram_ids:
        try:
            await bot.send_message(telegram_id, cancel_text)
        except Exception:
            continue


async def _prompt_create_state(message: Message, state: FSMContext, target_state: Any) -> None:
    if target_state == CreateEventState.title:
        await _send_prompt_text(message, state, t("create.title_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.datetime:
        await _send_prompt_text(message, state, t("create.datetime_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.place:
        await _send_prompt_text(message, state, t("create.place_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.description:
        await _send_prompt_text(message, state, t("create.description_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.cost:
        await _send_prompt_text(message, state, t("create.cost_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.image:
        await _send_prompt_text(message, state, t("create.image_prompt"), create_step_keyboard(back_enabled=True))
    elif target_state == CreateEventState.limit:
        await _send_prompt_text(message, state, t("create.limit_prompt"), create_step_keyboard(back_enabled=True))
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
        await callback.answer()
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
    await callback.answer()


async def _send_preview(message: Message, state: FSMContext) -> None:
    services = get_services()
    data = await state.get_data()
    payload = _build_event_payload(data)
    event = Event(
        id=0,
        title=payload["title"],
        date=payload["date"],
        time=payload["time"],
        place=payload["place"],
        description=payload.get("description"),
        cost=float(payload.get("cost", Decimal("0"))),
        image_file_id=payload.get("image_file_id"),
        max_participants=payload.get("max_participants"),
        reminder_3days=payload.get("reminder_3days", False),
        reminder_1day=payload.get("reminder_1day", False),
        status="active",
    )
    stats = RegistrationStats(going=0, not_going=0)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    markup = create_preview_keyboard()
    if event.image_file_id:
        await _send_prompt_photo(message, state, event.image_file_id, text, markup)
    else:
        await _send_prompt_text(message, state, text, markup)


def _build_event_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": data.get("title"),
        "date": data.get("event_date"),
        "time": data.get("event_time"),
        "place": data.get("place"),
        "description": data.get("description"),
        "cost": data.get("cost", Decimal("0")),
        "image_file_id": data.get("image_file_id"),
        "max_participants": data.get("limit"),
        "reminder_3days": data.get("reminder_3days", False),
        "reminder_1day": data.get("reminder_1day", False),
        "status": "active",
    }


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
        "datetime": t("edit.prompt_datetime"),
        "place": t("edit.prompt_place"),
        "description": t("edit.prompt_description"),
        "cost": t("edit.prompt_cost"),
        "image": t("edit.prompt_image"),
        "limit": t("edit.prompt_limit"),
    }
    return prompts.get(field, t("edit.prompt_value_fallback"))


def _parse_edit_value(field: str, message: Message) -> dict[str, Any]:
    if field == "title" or field == "place":
        value = (message.text or "").strip()
        if not value:
            raise ValueError(t("edit.value_empty_error"))
        return {field: value}
    if field == "description":
        return {field: (message.text or "").strip() or None}
    if field == "cost":
        text = (message.text or "0").replace(" ", "").replace(",", ".")
        try:
            cost = Decimal(text)
            if cost < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise ValueError(t("edit.cost_invalid_error"))
        return {field: cost}
    if field == "limit":
        text = (message.text or "0").strip()
        try:
            value = int(text)
        except ValueError as error:
            raise ValueError(t("edit.limit_invalid_error")) from error
        return {"max_participants": value if value > 0 else None}
    if field == "datetime":
        text = (message.text or "").strip()
        try:
            combined = datetime.strptime(text, t("format.input_datetime"))
        except ValueError as error:
            raise ValueError(t("edit.datetime_invalid_error")) from error
        return {"date": combined.date(), "time": combined.time()}
    if field == "image":
        if not message.photo:
            raise ValueError(t("edit.image_required_error"))
        return {"image_file_id": message.photo[-1].file_id}
    raise ValueError(t("edit.unknown_field_error"))

