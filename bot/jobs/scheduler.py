import asyncio

from aiogram import Bot
from loguru import logger

from bot.database.models import Car
from bot.utils.notifications import send_mileage_reminder

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