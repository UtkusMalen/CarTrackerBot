import asyncio
from loguru import logger
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.config import config
from bot.fsm.admin import AdminFSM
from bot.database.models import User, Car
from bot.keyboards.inline import get_admin_panel_keyboard, get_mailing_confirmation_keyboard
from bot.utils.notifications import send_mileage_reminder
from bot.utils.text_manager import get_text

router = Router()
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))

@router.message(Command("admin"))
async def show_admin_panel(message: Message, state: FSMContext):
    """Displays the admin panel."""
    await state.clear()
    await message.answer(
        get_text("admin.panel_header"),
        reply_markup=get_admin_panel_keyboard()
    )

@router.callback_query(F.data == "create_mailing")
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    """Starts the process of creating a new broadcast message."""
    await state.set_state(AdminFSM.get_message)
    msg = await callback.message.edit_text(get_text("admin.mailing_prompt"))
    await state.update_data(prompt_message_id=msg.message_id)

    await callback.answer()

@router.message(AdminFSM.get_message)
async def get_mailing_message(message: Message, state: FSMContext, bot: Bot):
    """Receives the content for the broadcast"""
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    if prompt_message_id:
        try:
            await bot.delete_message(message.from_user.id, prompt_message_id)
        except TelegramBadRequest:
            logger.warning("Failed to delete prompt message.")

    await message.delete()

    await state.update_data(
        text=message.html_text,
        photo_id=message.photo[-1].file_id if message.photo else None
    )
    await state.set_state(AdminFSM.confirm_mailing)

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
    await state.clear()
    await callback.message.edit_text(get_text("admin.mailing_cancelled"))
    await show_admin_panel(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "send_mailing", AdminFSM.confirm_mailing)
async def send_mailing(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirms and starts the broadcast process."""
    await callback.message.edit_text(get_text("admin.mailing_started"))
    await callback.answer()

    data = await state.get_data()
    text = data.get("text")
    photo_id = data.get("photo_id")

    await state.clear()

    all_users = await User.get_all_user_ids()
    success_count = 0
    fail_count = 0

    for user_id in all_users:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo=photo_id, caption=text)
            else:
                await bot.send_message(user_id, text=text)
            success_count += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            fail_count += 1
            logger.warning(f"Failed to send message to user {user_id}: {e}")
        except Exception as e:
            fail_count += 1
            logger.error(f"An error occurred while sending message to user {user_id}: {e}")

        await asyncio.sleep(0.1)

    await bot.send_message(
        chat_id=callback.from_user.id,
        text=get_text('admin.mailing_finished', success_count=success_count, fail_count=fail_count)
    )

@router.message(Command("test_mileage_reminder"), lambda msg: msg.from_user.id in config.admin_ids)
async def test_mileage_update_reminder(message: Message, bot: Bot):
    user_id = message.from_user.id
    active_car = await Car.get_active_car(user_id)

    if not active_car:
        await message.reply("Нет активного автомобиля.")
        return

    car_id = active_car[0]
    car_name = active_car[2]
    await message.reply(f"Отправляю напоминание о пробеге автомобиля для {car_name}.")

    success = await send_mileage_reminder(bot, user_id, car_name, car_id)

    if not success:
        await message.reply("Произошла ошибка при отправке напоминания.")