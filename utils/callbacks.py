START_MAIN_MENU = "main:start"
MENU_ACTUAL_EVENTS = "menu:actual"
MENU_HISTORY = "menu:history"
MENU_STATS = "menu:stats"
MENU_SETTINGS = "menu:settings"
SETTINGS_CREATE_EVENT = "settings:create"
SETTINGS_MANAGE_EVENTS = "settings:manage"

EVENT_VIEW_PREFIX = "event:view:"
EVENT_PAYMENT_PREFIX = "event:payment:"
EVENT_BACK_TO_LIST = "event:back:list"

CREATE_EVENT_BACK = "create:back"
CREATE_EVENT_CANCEL = "create:cancel"
CREATE_EVENT_PUBLISH = "create:publish"
CREATE_EVENT_REMINDER_TOGGLE_3 = "create:reminder:3"
CREATE_EVENT_REMINDER_TOGGLE_1 = "create:reminder:1"
CREATE_EVENT_REMINDER_DONE = "create:reminder:done"

EDIT_EVENT_PREFIX = "edit:event:"
EDIT_EVENT_FIELD_PREFIX = "edit:field:"
EDIT_EVENT_BACK = "edit:back"
EDIT_EVENT_CANCEL = "edit:cancel"
EDIT_EVENT_SAVE = "edit:save"
EDIT_EVENT_CANCEL_EVENT_PREFIX = "edit:cancel:event:"
EDIT_EVENT_CONFIRM_CANCEL_PREFIX = "edit:confirm_cancel:"


def event_view(event_id: int) -> str:
    return f"{EVENT_VIEW_PREFIX}{event_id}"


def event_payment(event_id: int) -> str:
    return f"{EVENT_PAYMENT_PREFIX}{event_id}"


def edit_event(event_id: int) -> str:
    return f"{EDIT_EVENT_PREFIX}{event_id}"


def edit_event_field(event_id: int, field: str) -> str:
    return f"{EDIT_EVENT_FIELD_PREFIX}{event_id}:{field}"


def cancel_event(event_id: int) -> str:
    return f"{EDIT_EVENT_CANCEL_EVENT_PREFIX}{event_id}"


def confirm_cancel_event(event_id: int) -> str:
    return f"{EDIT_EVENT_CONFIRM_CANCEL_PREFIX}{event_id}"


def extract_event_id(data: str, prefix: str) -> int:
    return int(data.removeprefix(prefix))


def extract_event_id_and_field(data: str, prefix: str) -> tuple[int, str]:
    payload = data.removeprefix(prefix)
    event_id_str, field = payload.split(":", 1)
    return int(event_id_str), field

