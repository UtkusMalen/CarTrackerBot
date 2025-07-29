from loguru import logger
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards.inline import get_mileage_reminder_keyboard
from bot.utils.text_manager import get_text

async def send_mileage_reminder(bot: Bot, user_id: int, car_name: str, car_id: int) -> bool:
    """Sends a reminder to a user to update their car's mileage."""

    try:
        text= get_text('mileage_update_reminder.message', car_name=car_name)
        keyboard = get_mileage_reminder_keyboard(car_id=car_id)
        await bot.send_message(user_id, text, reply_markup=keyboard)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to send mileage reminder to user {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"An error occurred while sending mileage reminder to user {user_id}: {e}")
        return False