from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


async def safe_delete_message(bot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        pass


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def safe_delete_by_id(bot: Bot, chat_id: int | None, message_id: int | None) -> None:
    if not chat_id or not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def safe_delete_recent_bot_messages(bot: Bot, chat_id: int, start_message_id: int, count: int = 10) -> None:
    for i in range(count):
        message_id = start_message_id - i
        if message_id <= 0:
            break
        try:
            await bot.delete_message(chat_id, message_id)
        except TelegramBadRequest:
            continue
