from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.callbacks import (
    CREATE_EVENT_BACK,
    CREATE_EVENT_IMAGES_CONFIRM,
    CREATE_EVENT_SKIP,
    CREATE_EVENT_PUBLISH,
    CREATE_EVENT_REMINDER_DONE,
    CREATE_EVENT_REMINDER_TOGGLE_1,
    CREATE_EVENT_REMINDER_TOGGLE_3,
    EDIT_EVENT_BACK,
    EDIT_EVENT_SAVE,
    EDIT_EVENT_CLEAR_IMAGES,
    EDIT_EVENT_BROADCAST,
    MANAGE_EVENTS_PAGE_PREFIX,
    SETTINGS_CREATE_EVENT,
    SETTINGS_MANAGE_EVENTS,
    START_MAIN_MENU,
    cancel_event,
    confirm_cancel_event,
    edit_event,
    edit_event_field,
    event_participants,
    event_participants_page,
)
from bot.utils.i18n import t


def moderator_settings_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.create_event"), callback_data=SETTINGS_CREATE_EVENT)
    builder.button(text=t("button.manage_events"), callback_data=SETTINGS_MANAGE_EVENTS)
    builder.button(text=t("button.back"), callback_data=START_MAIN_MENU)
    builder.adjust(1)
    return builder.as_markup()


def create_step_keyboard(back_enabled: bool, skip_enabled: bool = False, confirm_enabled: bool = False):
    builder = InlineKeyboardBuilder()
    if confirm_enabled:
        builder.button(text=t("button.create.confirm_images"), callback_data=CREATE_EVENT_IMAGES_CONFIRM)
    if skip_enabled:
        builder.button(text=t("button.skip"), callback_data=CREATE_EVENT_SKIP)
    if back_enabled:
        builder.button(text=t("button.back"), callback_data=CREATE_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def create_reminders_keyboard(selected_3: bool, selected_1: bool):
    builder = InlineKeyboardBuilder()
    label_3 = (
        t("button.create.reminder_3days_selected")
        if selected_3
        else t("button.create.reminder_3days")
    )
    label_1 = (
        t("button.create.reminder_1day_selected")
        if selected_1
        else t("button.create.reminder_1day")
    )
    builder.button(text=label_3, callback_data=CREATE_EVENT_REMINDER_TOGGLE_3)
    builder.button(text=label_1, callback_data=CREATE_EVENT_REMINDER_TOGGLE_1)
    builder.button(text=t("button.create.reminder_done"), callback_data=CREATE_EVENT_REMINDER_DONE)
    builder.button(text=t("button.back"), callback_data=CREATE_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def create_preview_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.create.publish"), callback_data=CREATE_EVENT_PUBLISH)
    builder.button(text=t("button.back"), callback_data=CREATE_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def manage_events_keyboard(events, page: int = 0, page_size: int = 5):
    builder = InlineKeyboardBuilder()
    total_events = len(events)
    total_pages = (total_events + page_size - 1) // page_size if total_events > 0 else 1
    
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, total_events)
    page_events = events[start_idx:end_idx]
    
    for event in page_events:
        builder.button(text=t("button.event.list_item", title=event.title), callback_data=edit_event(event.id))
    
    if total_pages > 1:
        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(("⏪", f"{MANAGE_EVENTS_PAGE_PREFIX}{prev_page}"))
        if page < total_pages - 1:
            pagination_buttons.append(("⏩", f"{MANAGE_EVENTS_PAGE_PREFIX}{next_page}"))
        if pagination_buttons:
            for text, callback_data in pagination_buttons:
                builder.button(text=text, callback_data=callback_data)
            builder.adjust(len(pagination_buttons))
    
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def manage_event_actions_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.settings.edit"), callback_data=edit_event_field(event_id, "menu"))
    builder.button(text=t("button.settings.cancel_event"), callback_data=cancel_event(event_id))
    builder.button(text=t("button.settings.broadcast"), callback_data=EDIT_EVENT_BROADCAST)
    builder.button(text=t("button.settings.participants"), callback_data=event_participants(event_id))
    builder.button(text=t("button.settings.promocodes"), callback_data=f"promocode:menu:{event_id}")
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def manage_promocode_actions_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.promocode.add"), callback_data=f"promocode:add:{event_id}")
    builder.button(text=t("button.promocode.delete"), callback_data=f"promocode:delete:{event_id}")
    builder.button(text=t("button.promocode.list"), callback_data=f"promocode:list:{event_id}")
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def promocode_input_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=f"promocode:back_menu:{event_id}")
    builder.adjust(1)
    return builder.as_markup()


def promocode_list_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=f"promocode:menu:{event_id}")
    builder.adjust(1)
    return builder.as_markup()


def edit_field_choice_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t("button.field.title"), callback_data=edit_event_field(event_id, "title")),
        InlineKeyboardButton(text=t("button.field.date"), callback_data=edit_event_field(event_id, "date")),
    )
    builder.row(
        InlineKeyboardButton(text=t("button.field.cost"), callback_data=edit_event_field(event_id, "cost")),
        InlineKeyboardButton(text=t("button.field.description"), callback_data=edit_event_field(event_id, "description")),
    )
    builder.row(
        InlineKeyboardButton(text=t("button.field.time"), callback_data=edit_event_field(event_id, "time")),
        InlineKeyboardButton(text=t("button.field.place"), callback_data=edit_event_field(event_id, "place")),        
    )
    builder.row(
        InlineKeyboardButton(text=t("button.field.period"), callback_data=edit_event_field(event_id, "period")),
        InlineKeyboardButton(text=t("button.field.image"), callback_data=edit_event_field(event_id, "image")),
    )
    builder.row(
        InlineKeyboardButton(text=t("button.field.limit"), callback_data=edit_event_field(event_id, "limit")),
        InlineKeyboardButton(text=t("button.field.reminders"), callback_data=edit_event_field(event_id, "reminders")),
    )
    builder.row(
        InlineKeyboardButton(text=t("button.back"), callback_data=EDIT_EVENT_BACK),
    )
    return builder.as_markup()


def edit_step_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def edit_reminders_keyboard(selected_3: bool, selected_1: bool):
    builder = InlineKeyboardBuilder()
    label_3 = (
        t("button.edit.reminder_3days_selected")
        if selected_3
        else t("button.edit.reminder_3days")
    )
    label_1 = (
        t("button.edit.reminder_1day_selected")
        if selected_1
        else t("button.edit.reminder_1day")
    )
    builder.button(text=label_3, callback_data=CREATE_EVENT_REMINDER_TOGGLE_3)
    builder.button(text=label_1, callback_data=CREATE_EVENT_REMINDER_TOGGLE_1)
    builder.button(text=t("button.edit.save"), callback_data=EDIT_EVENT_SAVE)
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def edit_images_keyboard(has_images: bool, dirty: bool):
    builder = InlineKeyboardBuilder()
    if dirty and has_images:
        builder.button(text=t("button.edit.save"), callback_data=EDIT_EVENT_SAVE)
    elif has_images:
        builder.button(text=t("button.edit.clear"), callback_data=EDIT_EVENT_CLEAR_IMAGES)
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def cancel_event_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.confirm_cancel_event"), callback_data=confirm_cancel_event(event_id))
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def participants_list_keyboard(event_id: int, participants_count: int = 0, page: int = 0, page_size: int = 10):
    builder = InlineKeyboardBuilder()
    total_pages = (participants_count + page_size - 1) // page_size if participants_count > 0 else 1
    
    if total_pages > 1:
        prev_page = max(0, page - 1)
        next_page = min(total_pages - 1, page + 1)
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(("⏪", event_participants_page(event_id, prev_page)))
        if page < total_pages - 1:
            pagination_buttons.append(("⏩", event_participants_page(event_id, next_page)))
        if pagination_buttons:
            for text, callback_data in pagination_buttons:
                builder.button(text=text, callback_data=callback_data)
            builder.adjust(len(pagination_buttons))
    
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()

