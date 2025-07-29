from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.config import config


async def set_user_commands(bot: Bot, user_id: int):
    """Sets the default commands for the bot."""
    default_commands = [
        BotCommand(command="start", description="Запустить/перезапустить бота"),
    ]

    if user_id in config.admin_ids:
        admin_commands = default_commands + [
            BotCommand(command="admin", description="Панель администратора"),
        ]
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeDefault(chat_id=user_id))
    else:
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault(chat_id=user_id))