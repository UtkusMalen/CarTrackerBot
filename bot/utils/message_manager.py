from typing import Dict
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

# In-memory storage for {chat_id: message_id}
user_last_message: Dict[int, int] = {}

async def delete_previous_message(message: Message):
    """Delete the previous message from the user."""
    chat_id = message.chat.id
    if chat_id in user_last_message:
        try:
            await message.bot.delete_message(chat_id, user_last_message[chat_id])
            logger.debug(f"Deleted previous message {user_last_message[chat_id]} for chat {chat_id}")
        except TelegramBadRequest:
            logger.warning(f"Failed to delete message {user_last_message[chat_id]} for chat {chat_id}")

def track_message(message: Message):
    """Track the last message sent by the user."""
    user_last_message[message.chat.id] = message.message_id