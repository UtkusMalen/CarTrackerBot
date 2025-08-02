import asyncio
from loguru import logger
from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.config import config
from bot.fsm.admin import AdminFSM
from bot.database.models import User, Car, Transaction
from bot.keyboards.inline import get_admin_panel_keyboard, get_mailing_confirmation_keyboard
from bot.utils.notifications import send_mileage_reminder
from bot.utils.text_manager import get_text

router = Router()
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))

@router.message(Command("admin"))
async def show_admin_panel(message: Message, state: FSMContext):
    """Displays the admin panel."""
    logger.info(f"Admin {message.from_user.id} accessed admin panel.")
    await state.clear()
    await message.answer(
        get_text("admin.panel_header"),
        reply_markup=get_admin_panel_keyboard()
    )


@router.callback_query(F.data == "create_mailing")
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    """Starts the process of creating a new broadcast message."""
    logger.info(f"Admin {callback.from_user.id} initiated a new mailing.")
    await state.set_state(AdminFSM.get_message)
    msg = await callback.message.edit_text(get_text("admin.mailing_prompt"))
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(AdminFSM.get_message)
async def get_mailing_message(message: Message, state: FSMContext, bot: Bot):
    """Receives the content for the broadcast"""
    logger.debug(f"Admin {message.from_user.id} provided content for the mailing.")
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    if prompt_message_id:
        try:
            await bot.delete_message(message.from_user.id, prompt_message_id)
        except TelegramBadRequest:
            logger.warning(f"Failed to delete prompt message {prompt_message_id} for admin {message.from_user.id}.")

    await message.delete()

    await state.update_data(
        text=message.html_text,
        photo_id=message.photo[-1].file_id if message.photo else None
    )
    await state.set_state(AdminFSM.confirm_mailing)

    logger.debug(f"Showing mailing preview to admin {message.from_user.id}.")
    await bot.send_message(message.from_user.id, get_text("admin.mailing_preview"))
    if message.photo:
        await bot.send_photo(
            chat_id=message.from_user.id,
            photo=message.photo[-1].file_id,
            caption=message.html_text
        )
    else:
        await bot.send_message(message.from_user.id, message.html_text)

    await bot.send_message(
        chat_id=message.from_user.id,
        text=get_text("admin.mailing_confirm_prompt"),
        reply_markup=get_mailing_confirmation_keyboard()
    )

@router.callback_query(F.data == "cancel_mailing", AdminFSM.confirm_mailing)
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    """Cancels the broadcast process."""
    logger.info(f"Admin {callback.from_user.id} cancelled the mailing.")
    await state.clear()
    await callback.message.edit_text(get_text("admin.mailing_cancelled"))
    await show_admin_panel(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "send_mailing", AdminFSM.confirm_mailing)
async def send_mailing(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirms and starts the broadcast process."""
    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} confirmed and started the mailing.")
    await callback.message.edit_text(get_text("admin.mailing_started"))
    await callback.answer()

    data = await state.get_data()
    text = data.get("text")
    photo_id = data.get("photo_id")
    await state.clear()

    all_users = await User.get_all_user_ids()
    logger.info(f"Starting broadcast to {len(all_users)} users.")
    success_count = 0
    fail_count = 0

    for user_id in all_users:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo=photo_id, caption=text)
            else:
                await bot.send_message(user_id, text=text)
            logger.debug(f"Successfully sent broadcast message to user {user_id}.")
            success_count += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            fail_count += 1
            logger.warning(f"Failed to send broadcast message to user {user_id}: {e}")
        except Exception as e:
            fail_count += 1
            logger.error(f"An unexpected error occurred while sending broadcast to user {user_id}: {e}")
        await asyncio.sleep(0.1)

    result_text = get_text('admin.mailing_finished', success_count=success_count, fail_count=fail_count)
    logger.success(f"Mailing finished. Success: {success_count}, Failed: {fail_count}.")
    await bot.send_message(
        chat_id=admin_id,
        text=result_text
    )

@router.message(Command("addnuts"))
async def add_nuts_command(message: Message, command: CommandObject, bot: Bot):
    admin_id = message.from_user.id

    if not command.args:
        await message.answer(get_text("admin.addnuts.usage"))
        return

    try:
        parts = command.args.split()
        if len(parts) != 2:
            raise ValueError("Incorrect number of arguments.")

        user_id_str, amount_str = parts
        user_id = int(user_id_str)
        amount = int(amount_str)

        if amount <= 0:
            await message.answer(get_text('admin.addnuts.invalid_amount'))
            return

    except (ValueError, TypeError):
        await message.answer(get_text("admin.addnuts.usage"))
        return

    target_user = await User.get_user(user_id)
    if not target_user:
        await message.answer(get_text("admin.addnuts.user_not_found", user_id=user_id))
        return

    description = "Начисление от администратора"
    await Transaction.add_transaction(user_id, amount, description)
    logger.success(f"Admin {admin_id} added {amount} nuts to user {user_id}")

    await message.answer(get_text("admin.addnuts.success", user_id=user_id, amount=amount))

    try:
        await bot.send_message(user_id, get_text('admin.addnuts.user_notification', amount=amount))
        logger.info(f"Successfully notified user {user_id} about receiving nuts.")
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(f"Could not notify user {user_id}. The bot might be blocked.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while notifying user {user_id}: {e}")


@router.message(Command("test_mileage_reminder"), lambda msg: msg.from_user.id in config.admin_ids)
async def test_mileage_update_reminder(message: Message, bot: Bot):
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} initiated a test mileage reminder.")
    active_car = await Car.get_active_car(user_id)

    if not active_car:
        logger.warning(f"Admin {user_id} tried to test reminder, but has no active car.")
        await message.reply("Нет активного автомобиля.")
        return

    car_id = active_car[0]
    car_name = active_car[2]
    await message.reply(f"Отправляю тестовое напоминание о пробеге для автомобиля '{car_name}'.")

    success = await send_mileage_reminder(bot, user_id, car_name, car_id)
    if not success:
        logger.error(f"Failed to send test mileage reminder to admin {user_id}.")
        await message.reply("Произошла ошибка при отправке тестового напоминания.")