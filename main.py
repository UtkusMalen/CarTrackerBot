import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot.config import config
from bot.database.database import init_db
from bot.handlers import user_handlers, registration_handlers, update_handlers, notes_handlers, reminders_handlers, \
    admin_handlers, summary_handlers, insurance_handlers, expense_handlers, fuel_handlers
from bot.jobs.scheduler import check_mileage_updates, daily_scheduler
from bot.middleware.logging_middleware import LoggingMiddleware


async def main() -> None:
    """Initializes the bot."""
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("bot.log", level="DEBUG", rotation="10 MB", compression="zip")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize bot and dispatcher
    default = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=config.bot_token.get_secret_value(), default=default)
    dp = Dispatcher()

    # Register middleware
    dp.update.middleware(LoggingMiddleware())

    # Include routers
    dp.include_router(registration_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(update_handlers.router)
    dp.include_router(notes_handlers.router)
    dp.include_router(reminders_handlers.router)
    dp.include_router(admin_handlers.router)
    #dp.include_router(notification_handlers.router)
    dp.include_router(summary_handlers.router)
    dp.include_router(insurance_handlers.router)
    dp.include_router(expense_handlers.router)
    dp.include_router(fuel_handlers.router)

    logger.info("Routers included")

    asyncio.create_task(check_mileage_updates(bot))
    asyncio.create_task(daily_scheduler(bot))

    # Start polling
    logger.info("Starting polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
