from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from bot.utils.callbacks import (
    EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX,
    EDIT_EVENT_PARTICIPANTS_PREFIX,
    EDIT_EVENT_PREFIX,
    EVENT_LIST_PAGE_PREFIX,
    EVENT_VIEW_PREFIX,
    MANAGE_EVENTS_PAGE_PREFIX,
    MENU_ACTUAL_EVENTS,
    MENU_COMMUNITY,
    MENU_SETTINGS,
    SETTINGS_CREATE_EVENT,
    SETTINGS_MANAGE_EVENTS,
    START_MAIN_MENU,
    extract_event_id,
    extract_event_id_and_page,
)


class MessageRefreshMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery) or not event.message:
            return await handler(event, data)
        
        if not await self._should_refresh(event):
            return await handler(event, data)
        
        await self._refresh_message(event)
        return await handler(event, data)
    
    async def _should_refresh(self, callback: CallbackQuery) -> bool:
        if not callback.message or not callback.data:
            return False
        
        message_date = callback.message.date
        if not message_date:
            return False
        
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = now - message_date
        
        return age > timedelta(hours=48)
    
    async def _refresh_message(self, callback: CallbackQuery) -> None:
        if not callback.message or not callback.data:
            return
        
        try:
            refreshed = await self._try_refresh_by_callback_data(callback)
            if not refreshed:
                await self._fallback_refresh(callback)
        except Exception:
            pass
    
    async def _try_refresh_by_callback_data(self, callback: CallbackQuery) -> bool:
        data = callback.data
        if not data:
            return False
        
        from bot.utils.di import get_services
        from bot.keyboards import (
            event_card_keyboard,
            event_list_keyboard,
            main_menu_keyboard,
            manage_event_actions_keyboard,
            manage_events_keyboard,
            moderator_settings_keyboard,
            participants_list_keyboard,
        )
        from bot.utils.i18n import t
        from bot.utils.formatters import format_event_card
        
        services = get_services()
        
        if data.startswith(EVENT_VIEW_PREFIX):
            event_id = extract_event_id(data, EVENT_VIEW_PREFIX)
            event = await services.events.get_event(event_id)
            if event:
                user_id = callback.from_user.id if callback.from_user else 0
                user = await services.users.ensure(user_id, callback.from_user.username if callback.from_user else None, callback.from_user.first_name if callback.from_user else None, callback.from_user.last_name if callback.from_user else None)
                is_paid_event = bool(event.cost and event.cost > 0)
                is_paid = False
                if is_paid_event:
                    is_paid = await services.payments.has_successful_payment(event.id, user.id)
                is_registered = await services.registrations.is_registered(event.id, user.id)
                discount = 0.0
                if is_paid_event and not is_paid:
                    discount = await services.promocodes.get_user_discount(event.id, user.id)
                stats = await services.registrations.get_stats(event_id)
                availability = services.registrations.availability(event.max_participants, stats.going)
                text = format_event_card(event, availability, discount if discount > 0 else None)
                markup = event_card_keyboard(
                    event_id,
                    is_paid=is_paid,
                    is_paid_event=is_paid_event,
                    is_registered=is_registered,
                )
                if callback.message.photo:
                    await callback.message.edit_caption(caption=text, reply_markup=markup)
                else:
                    await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data.startswith(EDIT_EVENT_PREFIX):
            event_id = extract_event_id(data, EDIT_EVENT_PREFIX)
            event = await services.events.get_event(event_id)
            if event:
                markup = manage_event_actions_keyboard(event_id)
                text = t("edit.event_options_prompt")
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data.startswith(EDIT_EVENT_PARTICIPANTS_PREFIX) or data.startswith(EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX):
            if data.startswith(EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX):
                event_id, page = extract_event_id_and_page(data, EDIT_EVENT_PARTICIPANTS_PAGE_PREFIX)
            else:
                event_id = extract_event_id(data, EDIT_EVENT_PARTICIPANTS_PREFIX)
                page = 0
            
            participants = await services.registrations.list_paid_participants(event_id)
            if participants:
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
                markup = participants_list_keyboard(event_id, participants_count=total_participants, page=page)
                await callback.message.edit_text(text, reply_markup=markup)
                return True
            else:
                text = t("moderator.participants_empty")
                markup = participants_list_keyboard(event_id, participants_count=0, page=0)
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data.startswith(EVENT_LIST_PAGE_PREFIX):
            page = int(data.removeprefix(EVENT_LIST_PAGE_PREFIX))
            events = await services.events.get_active_events()
            if events:
                markup = event_list_keyboard(events, page=page)
                text = t("menu.actual_prompt")
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data.startswith(MANAGE_EVENTS_PAGE_PREFIX):
            page = int(data.removeprefix(MANAGE_EVENTS_PAGE_PREFIX))
            events = await services.events.get_active_events(limit=20)
            if events:
                markup = manage_events_keyboard(events, page=page)
                text = t("menu.actual_prompt")
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data == MENU_ACTUAL_EVENTS:
            events = await services.events.get_active_events()
            if events:
                markup = event_list_keyboard(events)
                text = t("menu.actual_prompt")
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data == MENU_SETTINGS or data == SETTINGS_MANAGE_EVENTS or data == SETTINGS_CREATE_EVENT:
            user_id = callback.from_user.id if callback.from_user else 0
            user = await services.users.ensure(user_id, callback.from_user.username if callback.from_user else None, callback.from_user.first_name if callback.from_user else None, callback.from_user.last_name if callback.from_user else None)
            if services.users.is_moderator(user):
                markup = moderator_settings_keyboard()
                text = t("moderator.settings_title")
                await callback.message.edit_text(text, reply_markup=markup)
                return True
        
        elif data == START_MAIN_MENU:
            user_id = callback.from_user.id if callback.from_user else 0
            user = await services.users.ensure(user_id, callback.from_user.username if callback.from_user else None, callback.from_user.first_name if callback.from_user else None, callback.from_user.last_name if callback.from_user else None)
            markup = main_menu_keyboard(services.users.is_moderator(user))
            raw_name = (callback.from_user.full_name or callback.from_user.username or "").strip() if callback.from_user else ""
            from html import escape
            display_name = escape(raw_name) if raw_name else t("start.fallback_name")
            text = t("menu.title", name=display_name)
            await callback.message.edit_text(text, reply_markup=markup)
            return True
        
        return False
    
    async def _fallback_refresh(self, callback: CallbackQuery) -> None:
        if not callback.message:
            return
        
        try:
            old_text = callback.message.text or callback.message.caption or ""
            old_markup = callback.message.reply_markup
            
            if old_markup:
                await callback.message.edit_reply_markup(reply_markup=old_markup)
        except Exception:
            pass

