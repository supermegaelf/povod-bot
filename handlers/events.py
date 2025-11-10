from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

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
    text = format_event_card(event, availability)
    markup = event_card_keyboard(event.id)
    if callback.message:
        await safe_delete(callback.message)
        images = list(event.image_file_ids)
        if images:
            if len(images) == 1:
                await callback.message.answer_photo(images[0], caption=text, reply_markup=markup)
            else:
                media = [InputMediaPhoto(media=file_id) for file_id in images]
                await callback.message.answer_media_group(media)
                await callback.message.answer(text, reply_markup=markup)
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
        await callback.message.answer(t("menu.actual_prompt"), reply_markup=event_list_keyboard(events))
    await callback.answer()


@router.callback_query(F.data.startswith(EVENT_PAYMENT_PREFIX))
async def payment_placeholder(callback: CallbackQuery) -> None:
    await callback.answer(t("placeholder.feature_in_progress"), show_alert=True)

