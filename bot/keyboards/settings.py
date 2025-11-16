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
    SETTINGS_CREATE_EVENT,
    SETTINGS_MANAGE_EVENTS,
    START_MAIN_MENU,
    cancel_event,
    confirm_cancel_event,
    edit_event,
    edit_event_field,
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


def manage_events_keyboard(events):
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.button(text=t("button.event.list_item", title=event.title), callback_data=edit_event(event.id))
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def manage_event_actions_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.settings.edit"), callback_data=edit_event_field(event_id, "menu"))
    builder.button(text=t("button.settings.broadcast"), callback_data=EDIT_EVENT_BROADCAST)
    builder.button(text=t("button.settings.cancel_event"), callback_data=cancel_event(event_id))
    builder.button(text=t("button.settings.promocodes"), callback_data=f"promocode:list:{event_id}")
    builder.button(text=t("button.back"), callback_data=EDIT_EVENT_BACK)
    builder.adjust(1)
    return builder.as_markup()


def manage_promocode_actions_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.promocode.add"), callback_data=f"promocode:add:{event_id}")
    builder.button(text=t("button.promocode.delete"), callback_data=f"promocode:delete:{event_id}")
    builder.button(text=t("button.promocode.list"), callback_data=f"promocode:list:{event_id}")
    builder.button(text=t("button.back"), callback_data=f"promocode:back:{event_id}")
    builder.adjust(1)
    return builder.as_markup()


def promocode_input_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=t("button.back"), callback_data=f"promocode:back:{event_id}")
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

