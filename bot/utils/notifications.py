from loguru import logger
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.keyboards.inline import get_mileage_reminder_keyboard
from bot.utils.text_manager import get_text

async def send_mileage_reminder(bot: Bot, user_id: int, car_name: str, car_id: int) -> bool:
    """Sends a reminder to a user to update their car's mileage."""
    logger.info(f"Attempting to send mileage reminder to user {user_id} for car '{car_name}' (ID: {car_id}).")
    try:
        text = get_text('mileage_update_reminder.message', car_name=car_name)
        keyboard = get_mileage_reminder_keyboard(car_id=car_id)
        await bot.send_message(user_id, text, reply_markup=keyboard)
        logger.success(f"Successfully sent mileage reminder to user {user_id}.")
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to send mileage reminder to user {user_id}. Reason: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending mileage reminder to user {user_id}: {e}")
        return False