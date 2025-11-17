from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
from aiogram.types import Message


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


async def safe_delete_recent_bot_messages(bot: Bot, chat_id: int, start_message_id: int, count: int = 100) -> None:
    deleted_count = 0
    failed_count = 0
    max_failed = 10
    
    for i in range(count):
        message_id = start_message_id - i
        if message_id <= 0:
            break
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