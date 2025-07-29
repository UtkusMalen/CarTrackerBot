from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import config


async def set_user_commands(bot: Bot, user_id: int):
    """Sets the commands for a specific user."""
    default_commands = [
        BotCommand(command="start", description="Запустить/перезапустить бота"),
    ]

    # Start with the default commands
    commands_to_set = default_commands

    # Check if the user is an admin. It's safer to check if config.admin_ids is not None first.
    if config.admin_ids and user_id in config.admin_ids:
        # If they are an admin, add the admin-specific command
        commands_to_set = default_commands + [
            BotCommand(command="admin", description="Панель администратора"),
        ]

    # Use BotCommandScopeChat to apply the commands only to the specific user's chat
    try:
        await bot.set_my_commands(commands_to_set, scope=BotCommandScopeChat(chat_id=user_id))
    except Exception as e:
        # It's good practice to log potential errors
        print(f"Could not set commands for user {user_id}: {e}")