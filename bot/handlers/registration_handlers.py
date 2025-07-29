import asyncio

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.fsm.registration import RegistrationFSM
from bot.keyboards.inline import get_oil_interval_keyboard, get_back_keyboard
from bot.database.models import Car, User, Reminder
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data == "start_registration")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    """
    Starts car registration process with a context-aware 'Back' button.
    """
    user_id = callback.from_user.id
    await User.create_user(user_id, callback.from_user.username, callback.from_user.first_name)
    await state.set_state(RegistrationFSM.car_name)

    active_car = await Car.get_active_car(user_id)
    if active_car:
        back_callback_data = "my_profile"
    else:
        back_callback_data = "main_menu"

    try:
        msg = await callback.message.edit_text(
            get_text('registration.prompt_car_name'),
            reply_markup=get_back_keyboard(back_callback_data)
        )
        await state.update_data(prompt_message_id=msg.message_id)
    except TelegramBadRequest:
        logger.warning("Cannot edit message, sending new one")
        msg = await callback.message.answer(
            get_text('registration.prompt_car_name'),
            reply_markup=get_back_keyboard(back_callback_data)
        )
        await state.update_data(prompt_message_id=msg.message_id)
    finally:
        await callback.answer()

@router.message(RegistrationFSM.car_name)
async def process_car_name(message: Message, state: FSMContext, bot: Bot):
    """Processes the car name and checks for duplicates."""
    car_name = message.text
    if await Car.car_exists_by_name(message.from_user.id, car_name):
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
    """Processes the car mileage."""
    if not message.text.isdigit():
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
    """Processes the last oil change."""
    if not message.text.isdigit():
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
    data = await state.get_data()
    car_id = await Car.add_car(
        user_id,
        data['car_name'],
        data['car_mileage']
    )

    await User.set_active_car(user_id, car_id)

    # Create the initial "Oil Change" reminder
    await Reminder.add_reminder(
        car_id,
        "Замена масла",
        data['oil_change_interval'],
        data['last_oil_change']
    )

@router.message(RegistrationFSM.oil_change_interval)
async def process_oil_interval_custom(message: Message, state: FSMContext, bot: Bot):
    """Processes the custom oil interval."""
    if not message.text.isdigit():
        error_msg = await message.answer(get_text('errors.must_be_digit'))
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await state.update_data(oil_change_interval=int(message.text))
    await _finish_registration(message.from_user.id, state)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

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
            except TelegramBadRequest:
                logger.warning("Cannot edit message, sending new one")
                await show_main_menu(message, message.from_user.id, edit=False)

    await state.clear()


@router.callback_query(F.data.startswith("interval_"))
async def process_oil_interval_callback(callback: CallbackQuery, state: FSMContext):
    """Processes interval from button, saves data, and shows main menu."""
    interval = int(callback.data.split("_")[1])
    await state.update_data(oil_change_interval=interval)
    await _finish_registration(callback.from_user.id, state)

    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer()
    await state.clear()