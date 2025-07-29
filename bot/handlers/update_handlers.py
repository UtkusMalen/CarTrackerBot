import asyncio

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car, Reminder
from bot.fsm.update import UpdateFSM
from bot.keyboards.inline import get_back_keyboard
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()


# --- Update Mileage Flow ---
@router.callback_query(F.data == "update_mileage")
async def start_mileage_update(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UpdateFSM.update_mileage)
    msg = await callback.message.edit_text(
        get_text('update.prompt_mileage'),
        reply_markup=get_back_keyboard("main_menu")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()


@router.message(UpdateFSM.update_mileage)
async def process_mileage_update(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    new_mileage = int(message.text)
    user_id = message.from_user.id
    car = await Car.get_active_car(user_id)

    if not car:
        await message.answer(get_text('errors.car_not_found'))
        await state.clear()
        return

    car_id, *_ = car

    await Car.update_mileage(car_id, new_mileage)

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')

    await state.clear()
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(user_id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(
                    text=text,
                    chat_id=message.chat.id,
                    message_id=prompt_message_id,
                    reply_markup=keyboard
                )
            except TelegramBadRequest as e:
                logger.error(f"Failed to edit mileage message into main menu: {e}")
                await show_main_menu(message, user_id, edit=False)
    else:
        # Fallback if message ID was lost
        await show_main_menu(message, user_id, edit=False)


# --- Change Reminder Interval Flow ---
@router.callback_query(F.data.startswith("change_interval:"))
async def start_interval_update(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    await state.set_state(UpdateFSM.update_reminder_interval)
    await state.update_data(reminder_id=reminder_id)

    msg =await callback.message.edit_text(get_text(
        'update.prompt_new_interval',
        name=reminder[2],
        current_interval=reminder[3]
    ),
        reply_markup=get_back_keyboard(f"manage_reminder:{reminder_id}")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()


@router.message(UpdateFSM.update_reminder_interval)
async def process_interval_update(message: Message, state: FSMContext, bot: Bot):
    """Handles the update of an existing reminder's interval."""
    if not message.text.isdigit():
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    data = await state.get_data()
    reminder_id = data.get("reminder_id")
    prompt_message_id = data.get("prompt_message_id")

    if not reminder_id:
        error_msg = await message.answer(get_text('errors.generic_error'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        await state.clear()
        return

    new_interval = int(message.text)
    await Reminder.update_interval(reminder_id, new_interval)

    await state.clear()
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(message.from_user.id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(
                    text=text,
                    chat_id=message.chat.id,
                    message_id=prompt_message_id,
                    reply_markup=keyboard
                )
            except TelegramBadRequest as e:
                logger.error(f"Failed to edit interval prompt into main menu: {e}")
                await show_main_menu(message, message.from_user.id, edit=False)
    else:
        await show_main_menu(message, message.from_user.id, edit=False)