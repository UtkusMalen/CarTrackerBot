import asyncio

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.config import config
from bot.fsm.registration import RegistrationFSM
from bot.keyboards.inline import get_oil_interval_keyboard, get_back_keyboard
from bot.database.models import Car, User, Reminder, Transaction
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started registration process.")
    await User.create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    await state.set_state(RegistrationFSM.car_name)

    active_car = await Car.get_active_car(user_id)
    back_callback_data = "my_profile" if active_car else "main_menu"

    try:
        msg = await callback.message.edit_text(
            get_text('registration.prompt_car_name'),
            reply_markup=get_back_keyboard(back_callback_data)
        )
        await state.update_data(prompt_message_id=msg.message_id)
    except TelegramBadRequest:
        logger.warning(f"Cannot edit message for user {user_id}, sending new one for registration.")
        msg = await callback.message.answer(
            get_text('registration.prompt_car_name'),
            reply_markup=get_back_keyboard(back_callback_data)
        )
        await state.update_data(prompt_message_id=msg.message_id)
    finally:
        await callback.answer()

@router.message(RegistrationFSM.car_name)
async def process_car_name(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    car_name = message.text
    logger.debug(f"User {user_id} (State: car_name) entered car name: '{car_name}'")
    if await Car.car_exists_by_name(user_id, car_name):
        logger.warning(f"User {user_id} entered a duplicate car name: '{car_name}'.")
        error_msg = await message.answer(get_text('errors.car_exists', car_name=car_name))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(car_name=car_name)
    await state.set_state(RegistrationFSM.car_mileage)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    if prompt_message_id:
        await bot.edit_message_text(
            get_text('registration.prompt_mileage'),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_back_keyboard("start_registration")
        )

@router.message(RegistrationFSM.car_mileage)
async def process_car_mileage(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: car_mileage) entered mileage: '{message.text}'")
    if not message.text.isdigit():
        logger.warning(f"User {user_id} entered non-digit mileage: '{message.text}'.")
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(car_mileage=int(message.text))
    await state.set_state(RegistrationFSM.last_oil_change)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    if prompt_message_id:
        await bot.edit_message_text(
            get_text('registration.prompt_last_oil_change'),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_back_keyboard("start_registration")
        )

@router.message(RegistrationFSM.last_oil_change)
async def process_last_oil_change(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: last_oil_change) entered last oil change: '{message.text}'")
    if not message.text.isdigit():
        logger.warning(f"User {user_id} entered non-digit for last oil change: '{message.text}'.")
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(last_oil_change=int(message.text))
    await state.set_state(RegistrationFSM.oil_change_interval)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    if prompt_message_id:
        await bot.edit_message_text(
            get_text('registration.prompt_oil_interval'),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_oil_interval_keyboard("start_registration")
        )

async def _finish_registration(user_id: int, state: FSMContext):
    logger.info(f"Finishing registration for user {user_id}.")
    data = await state.get_data()
    car_id = await Car.add_car(
        user_id,
        data['car_name'],
        data['car_mileage']
    )
    await User.set_active_car(user_id, car_id)
    await Reminder.add_reminder(
        car_id, "Замена масла", data['oil_change_interval'], data['last_oil_change']
    )

    description = "Добавление авто"
    if not await Transaction.has_received_reward(user_id, description):
        await Transaction.add_transaction(
            user_id,
            config.rewards.add_car,
            description
        )

    logger.success(f"Registration finished for user {user_id}. Car '{data['car_name']}' (ID: {car_id}) created.")

@router.message(RegistrationFSM.oil_change_interval)
async def process_oil_interval_custom(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: oil_change_interval) entered custom interval: '{message.text}'")
    if not message.text.isdigit():
        logger.warning(f"User {user_id} entered non-digit for oil interval: '{message.text}'.")
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(oil_change_interval=int(message.text))
    await _finish_registration(user_id, state)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()

    if prompt_message_id:
        content = await _get_main_menu_content(user_id)
        if content:
            text, keyboard = content
            try:
                await bot.edit_message_text(text, chat_id=message.chat.id, message_id=prompt_message_id, reply_markup=keyboard)
            except TelegramBadRequest:
                logger.warning(f"Cannot edit message to main menu for user {user_id}, sending new one.")
                await show_main_menu(message, user_id, edit=False)
    await state.clear()

@router.callback_query(F.data.startswith("interval_"))
async def process_oil_interval_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    interval = int(callback.data.split("_")[1])
    logger.debug(f"User {user_id} (State: oil_change_interval) selected interval button: {interval}km")
    await state.update_data(oil_change_interval=interval)
    await _finish_registration(user_id, state)

    await show_main_menu(callback.message, user_id, edit=True)
    await callback.answer()
    await state.clear()