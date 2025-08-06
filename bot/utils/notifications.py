from loguru import logger
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.keyboards.inline import get_to_main_menu_keyboard, get_time_based_notification_keyboard
from bot.utils.message_manager import track_message
from bot.utils.text_manager import get_text

async def send_mileage_reminder(bot: Bot, user_id: int, car_name: str, car_id: int) -> bool:
    """Sends a reminder to a user to update their car's mileage."""
    logger.info(f"Attempting to send mileage reminder to user {user_id} for car '{car_name}' (ID: {car_id}).")
    try:
        text = get_text('mileage_update_reminder.message', car_name=car_name)
        keyboard = get_to_main_menu_keyboard()
        sent_message =await bot.send_message(user_id, text, reply_markup=keyboard)
        track_message(sent_message)
        logger.success(f"Successfully sent mileage reminder to user {user_id}.")
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to send mileage reminder to user {user_id}. Reason: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending mileage reminder to user {user_id}: {e}")
        return False

async def send_renewal_notification(bot: Bot, user_id: int, car_name: str, reminder_name: str) -> bool:
    """Notifies a user that their time-based reminder has been automatically renewed."""
    logger.info(f"Sending renewal notification to user {user_id} for reminder '{reminder_name}'.")
    try:
        text = (f"✅ Ваше отслеживание \"{reminder_name}\" для автомобиля \"{car_name}\" было автоматически продлено.\n\n"
                "Вы можете отключить автопродление в меню отслеживаний.")
        keyboard = get_to_main_menu_keyboard()
        sent_message = await bot.send_message(user_id, text, reply_markup=keyboard)
        track_message(sent_message)
        logger.success(f"Successfully sent renewal notification to user {user_id}.")
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to send renewal notification to user {user_id}. Reason: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending renewal notification to user {user_id}: {e}")
        return False

async def send_time_based_notification(bot: Bot, user_id: int, car_name: str, reminder_name: str, days_left: int, reminder_id: int):
    """Sends a notification for a time-based reminder that is due soon."""
    logger.info(f"Sending time-based notification to {user_id} for '{reminder_name}' ({days_left} days left).")
    try:
        text = get_text('reminders.notification_time_based', car_name=car_name, reminder_name=reminder_name, days_left=days_left)
        keyboard = get_time_based_notification_keyboard(reminder_id, days_left)
        sent_message = await bot.send_message(user_id, text, reply_markup=keyboard)
        track_message(sent_message)
        logger.success(f"Successfully sent time-based notification to {user_id}.")
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Failed to send time-based notification to user {user_id}. Reason: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending time-based notification to {user_id}: {e}")
        return False