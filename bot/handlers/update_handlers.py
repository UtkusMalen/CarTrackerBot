import asyncio
import math
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.config import config
from bot.database.models import Car, Reminder, Transaction
from bot.fsm.update import UpdateFSM
from bot.keyboards.inline import get_back_keyboard
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data == "update_mileage")
async def start_mileage_update(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started mileage update.")
    await state.set_state(UpdateFSM.update_mileage)
    msg = await callback.message.edit_text(
        get_text('update.prompt_mileage'),
        reply_markup=get_back_keyboard("main_menu")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(UpdateFSM.update_mileage)
async def process_mileage_update(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: update_mileage) sent new mileage: '{message.text}'.")
    if not message.text.isdigit():
        logger.warning(f"User {user_id} entered non-digit for mileage update: '{message.text}'.")
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    new_mileage = int(message.text)
    active_car = await Car.get_active_car(user_id)
    if not active_car:
        logger.error(f"User {user_id} tried to update mileage but no active car was found.")
        await message.answer(get_text('errors.car_not_found'))
        await state.clear()
        return

    car_id = active_car[0]

    car_data = await Car.get_car_for_allowance_update(car_id)
    if not car_data:
        logger.error(f"Could not fetch car {car_id} for allowance update.")
        await state.clear()
        return

    old_mileage, current_allowance, last_update_str = car_data

    today = datetime.now().date()
    last_update_date = datetime.strptime(last_update_str, "%Y-%m-%d").date()
    days_passed = (today - last_update_date).days

    if days_passed > 0:
        allowance_to_add = days_passed * config.rewards.mileage_allowance_per_day
        current_allowance += allowance_to_add
        logger.info(f"User {user_id} gets {allowance_to_add}km allowance for {days_passed} days. New total: {current_allowance}km.")

    mileage_added = new_mileage - old_mileage
    rewardable_km = min(mileage_added, current_allowance)

    if rewardable_km > 0 and config.rewards.km_per_nut > 0:
        nuts_to_award = math.floor(rewardable_km / config.rewards.km_per_nut)
        if nuts_to_award > 0:
            await Transaction.add_transaction(
                user_id,
                nuts_to_award,
                f"Обновление пробега ({rewardable_km} км)"
            )
            logger.success(f"Awarded {nuts_to_award} nuts to user {user_id} for {rewardable_km}km mileage update.")

    remaining_allowance = current_allowance - rewardable_km
    await Car.update_mileage_and_allowance(car_id, new_mileage, remaining_allowance)

    logger.success(f"User {user_id} updated mileage for car {car_id} to {new_mileage}.")

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await state.clear()
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(user_id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=prompt_message_id, reply_markup=keyboard)
            except TelegramBadRequest as e:
                logger.error(f"Failed to edit mileage message into main menu for user {user_id}: {e}")
                await show_main_menu(message, user_id, edit=False)
    else:
        await show_main_menu(message, user_id, edit=False)

@router.callback_query(F.data.startswith("change_interval:"))
async def start_interval_update(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    reminder_id = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} started updating interval for reminder {reminder_id}.")
    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    await state.set_state(UpdateFSM.update_reminder_interval)
    await state.update_data(reminder_id=reminder_id)
    msg = await callback.message.edit_text(
        get_text('update.prompt_new_interval', name=reminder[2], current_interval=reminder[3]),
        reply_markup=get_back_keyboard(f"manage_reminder:{reminder_id}")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(UpdateFSM.update_reminder_interval)
async def process_interval_update(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: update_reminder_interval) sent new interval: '{message.text}'.")
    if not message.text.isdigit():
        logger.warning(f"User {user_id} entered non-digit for interval update: '{message.text}'.")
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    data = await state.get_data()
    reminder_id = data.get("reminder_id")
    prompt_message_id = data.get("prompt_message_id")
    if not reminder_id:
        logger.error(f"User {user_id} was in interval update FSM but reminder_id was not in state data.")
        error_msg = await message.answer(get_text('errors.generic_error'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        await state.clear()
        return

    new_interval = int(message.text)
    await Reminder.update_interval(reminder_id, new_interval)
    logger.success(f"User {user_id} updated interval for reminder {reminder_id} to {new_interval}.")
    await state.clear()
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(user_id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=prompt_message_id, reply_markup=keyboard)
            except TelegramBadRequest as e:
                logger.error(f"Failed to edit interval prompt into main menu for {user_id}: {e}")
                await show_main_menu(message, user_id, edit=False)
    else:
        await show_main_menu(message, user_id, edit=False)