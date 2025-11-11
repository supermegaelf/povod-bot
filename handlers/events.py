from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from keyboards import (
    back_to_main_keyboard,
    event_card_keyboard,
    event_list_keyboard,
)
from utils.callbacks import (
    EVENT_BACK_TO_LIST,
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
    stats = await services.registrations.get_stats(event.id)
    availability = services.registrations.availability(event.max_participants, stats.going)
    text = format_event_card(event, availability)
    markup = event_card_keyboard(event.id)
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


@router.callback_query(F.data.startswith(EVENT_PAYMENT_PREFIX))
async def payment_placeholder(callback: CallbackQuery) -> None:
    await callback.answer(t("placeholder.feature_in_progress"), show_alert=True)


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

