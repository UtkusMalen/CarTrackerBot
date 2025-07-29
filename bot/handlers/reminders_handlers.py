# bot/handlers/reminders_handlers.py
import asyncio

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.fsm.reminders import ReminderFSM
from bot.database.models import Car, Reminder
from bot.keyboards.inline import get_create_reminder_keyboard, get_reminder_management_keyboard, get_back_keyboard
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data == "create_reminder")
async def create_reminder_entry(callback: CallbackQuery, state: FSMContext):
    """Entry point for the reminder creation flow."""
    car = await Car.get_active_car(callback.from_user.id)
    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return

    text = get_text('reminders.creation_prompt')
    try:
        msg = await callback.message.edit_text(
            text,
            reply_markup=get_create_reminder_keyboard()
        )
        await state.update_data(prompt_message_id=msg.message_id)
    except TelegramBadRequest:
        logger.warning("Could not edit message to start reminder creation, sending new one")
        msg = await callback.message.answer(
            text,
            reply_markup=get_create_reminder_keyboard()
        )
        await state.update_data(prompt_message_id=msg.message_id)
    finally:
        await callback.answer()


# --- Reminder Creation Flow ---
@router.callback_query(F.data == "create_reminder_custom")
async def create_custom_reminder_start(callback: CallbackQuery, state: FSMContext):
    """Handles custom reminder button press, edits the prompt."""
    await state.set_state(ReminderFSM.set_name)
    await callback.message.edit_text(get_text(
        'reminders.creation_custom_prompt'),
        reply_markup=get_back_keyboard("create_reminder")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("create_reminder_preset:"))
async def create_preset_reminder_start(callback: CallbackQuery, state: FSMContext):
    """Handles a preset button press, edits the prompt to ask for the interval."""
    name = callback.data.split(":")[1]
    await state.update_data(name=name)
    await state.set_state(ReminderFSM.set_interval)
    text = f"{get_text('reminders.preset_header', name=name)}\n\n{get_text('reminders.ask_interval')}"
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("create_reminder")
    )
    await callback.answer()


@router.message(ReminderFSM.set_name)
async def process_reminder_name(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(name=message.text)
    await state.set_state(ReminderFSM.set_interval)
    text = f"{get_text('reminders.preset_header', name=message.text)}\n\n{get_text('reminders.ask_interval')}"

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await message.delete()

    if prompt_message_id:
        await bot.edit_message_text(
            text,
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_back_keyboard("create_reminder")
        )


@router.message(ReminderFSM.set_interval)
async def process_reminder_interval(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(interval_km=int(message.text))
    await state.set_state(ReminderFSM.set_last_reset_mileage)
    car = await Car.get_active_car(message.from_user.id)

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await message.delete()

    if prompt_message_id:
        await bot.edit_message_text(
            get_text('reminders.ask_last_reset', mileage=car[3]),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_back_keyboard("create_reminder")
        )

@router.message(ReminderFSM.set_last_reset_mileage)
async def process_reminder_last_reset(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    data = await state.get_data()
    car = await Car.get_active_car(message.from_user.id)

    await Reminder.add_reminder(
        car_id=car[0],
        name=data['name'],
        interval=data['interval_km'],
        last_reset=int(message.text)
    )

    prompt_message_id = data.get('prompt_message_id')
    await state.clear()
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(message.from_user.id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=message.chat.id,
                    message_id=prompt_message_id,
                    reply_markup=keyboard
                )
            except TelegramBadRequest as e:
                logger.error(f"Failed to edit message into main menu: {e}")
                await show_main_menu(message, message.from_user.id, edit=False)
    else:
        await show_main_menu(message, message.from_user.id, edit=True)

# --- Reminder Management Flow ---
@router.callback_query(F.data.startswith("manage_reminder:"))
async def manage_reminder_menu(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    _, _, name, interval, last_reset = reminder
    car = await Car.get_active_car(callback.from_user.id)
    remaining_km = (last_reset + interval) - car[3]

    menu_text = (
        f"{get_text('reminders.manage_header', name=name)}\n"
        f"{get_text('reminders.manage_regularity', interval=interval)}\n"
        f"{get_text('reminders.manage_remaining', remaining_km=max(0, remaining_km))}\n\n"
        f"{get_text('reminders.manage_prompt')}"
    )

    await callback.message.edit_text(
        menu_text,
        reply_markup=get_reminder_management_keyboard(reminder_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reset_reminder:"))
async def reset_reminder_counter(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    car = await Car.get_active_car(callback.from_user.id)
    await Reminder.reset_reminder(reminder_id, car[3])
    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer(get_text('reminders.reset_success'), show_alert=True)


@router.callback_query(F.data.startswith("delete_reminder:"))
async def delete_reminder_confirm(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    await Reminder.delete_reminder(reminder_id)
    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer(get_text('reminders.deleted_success'), show_alert=True)