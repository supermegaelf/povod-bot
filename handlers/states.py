from aiogram.fsm.state import State, StatesGroup


class CreateEventState(StatesGroup):
    title = State()
    datetime = State()
    place = State()
    description = State()
    cost = State()
    image = State()
    limit = State()
    reminders = State()
    preview = State()


class EditEventState(StatesGroup):
    selecting_field = State()
    value_input = State()
    reminders = State()
    confirmation = State()


class DiscussionState(StatesGroup):
    writing = State()

