import asyncio

from aiogram import Bot
from loguru import logger

from bot.database.models import Car, Reminder
from bot.utils.notifications import send_mileage_reminder, send_renewal_notification


async def check_mileage_updates(bot: Bot):
    logger.info("Scheduler started. First check will run in 60 seconds.")
    await asyncio.sleep(60)

    while True:
        logger.info("Scheduler running job: check_mileage_updates")
        try:
            cars_to_remind = await Car.get_cars_needing_mileage_update()
            if cars_to_remind:
                logger.info(f"Found {len(cars_to_remind)} users to remind about mileage updates.")
                for user_id, car_name, car_id in cars_to_remind:
                    await send_mileage_reminder(bot, user_id, car_name, car_id)
            else:
                logger.info("No users need a mileage update reminder at this time.")

        except Exception as e:
            logger.error(f"An error occurred in scheduled job check_mileage_updates: {e}")

        logger.info("Scheduler job finished. Sleeping for 24 hours (86400 seconds).")
        await asyncio.sleep(86400)

async def check_expired_reminders(bot: Bot):
    """Checks for expired time-based reminders and renews them if they are repeating."""
    logger.info("Scheduler running job: check_expired_reminders")
    try:
        expired_reminders = await Reminder.get_expired_repeating_reminders()
        if expired_reminders:
            logger.info(f"Found {len(expired_reminders)} expired reminders to renew.")
            for rem in expired_reminders:
                # Renew the reminder by advancing its date
                await Reminder.reset_time_reminder(rem['reminder_id'], "", repeat=True)
                # Notify the user
                await send_renewal_notification(bot, rem['user_id'], rem['car_name'], rem['name'])
        else:
            logger.info("No expired repeating reminders found.")
    except Exception as e:
        logger.error(f"An error occurred in scheduled job check_expired_reminders: {e}")


async def daily_scheduler(bot: Bot):
    """The main scheduler that runs all daily jobs."""
    logger.info("Scheduler started. First check will run in 60 seconds.")
    await asyncio.sleep(60)

    while True:
        await check_mileage_updates(bot)
        await check_expired_reminders(bot)

        logger.info("Scheduler jobs finished. Sleeping for 24 hours (86400 seconds).")
        await asyncio.sleep(86400)