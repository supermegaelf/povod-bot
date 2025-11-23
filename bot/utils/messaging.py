import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import CallbackQuery, Message

_LAST_USER_MESSAGES: dict[int, int] = {}


async def remember_bot_message(chat_id: int, message_id: int) -> None:
    try:
        from bot.utils.di import get_services
        services = get_services()
        user = await services.users.get_by_telegram_id(chat_id)
        if user:
            await services.bot_messages.save_message(user.id, chat_id, message_id)
    except Exception:
        pass


def remember_user_message(message: Message) -> None:
    if message.chat:
        _LAST_USER_MESSAGES[message.chat.id] = message.message_id


def get_last_user_message_id(chat_id: int) -> int | None:
    return _LAST_USER_MESSAGES.get(chat_id)


async def safe_delete_message(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramAPIError):
        pass
    except Exception:
        pass


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramAPIError):
        pass
    except Exception:
        pass


async def safe_delete_by_id(bot: Bot, chat_id: int | None, message_id: int | None) -> None:
    if not chat_id or not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramAPIError):
        pass
    except Exception:
        pass


async def safe_answer_callback(callback: CallbackQuery, text: str | None = None, show_alert: bool = False) -> None:
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "too old" in error_message or "timeout expired" in error_message or "query id is invalid" in error_message:
            pass
        else:
            raise
    except Exception:
        pass


async def safe_delete_stored_bot_messages(bot: Bot, chat_id: int, exclude_message_id: int | None = None) -> None:
    try:
        from bot.utils.di import get_services
        services = get_services()
        messages = await services.bot_messages.get_recent_messages(chat_id, hours=48)
        
        message_ids_to_delete = []
        for msg in messages:
            if exclude_message_id and msg.message_id == exclude_message_id:
                continue
            message_ids_to_delete.append((msg.chat_id, msg.message_id))
        
        deleted_from_telegram = []
        for chat_id_msg, msg_id in message_ids_to_delete:
            try:
                await bot.delete_message(chat_id_msg, msg_id)
                deleted_from_telegram.append((chat_id_msg, msg_id))
            except (TelegramBadRequest, TelegramAPIError):
                pass
            except Exception:
                pass
        
        if deleted_from_telegram:
            await services.bot_messages.delete_messages(deleted_from_telegram)
    except Exception:
        pass


async def safe_delete_recent_bot_messages(bot: Bot, chat_id: int, start_message_id: int, count: int = 100, exclude_message_id: int | None = None) -> None:
    deleted_count = 0
    failed_count = 0
    max_failed = 10
    last_user_message_id = get_last_user_message_id(chat_id)
    
    for i in range(count):
        message_id = start_message_id - i
        if message_id <= 0:
            break
        if last_user_message_id and message_id == last_user_message_id:
            continue
        if exclude_message_id and message_id == exclude_message_id:
            continue
        try:
            await bot.delete_message(chat_id, message_id)
            deleted_count += 1
            failed_count = 0
        except (TelegramBadRequest, TelegramAPIError) as e:
            error_code = getattr(e, 'error_code', None)
            if error_code == 400:
                failed_count += 1
                if failed_count >= max_failed:
                    break
            continue
        except Exception:
            failed_count += 1
            if failed_count >= max_failed:
                break
            continue