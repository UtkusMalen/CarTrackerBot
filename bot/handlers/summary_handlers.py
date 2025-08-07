import asyncio

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.config import config
from bot.database.models import Car, Transaction
from bot.fsm.summary import SummaryFSM
from bot.keyboards.inline import get_summary_keyboard, get_back_keyboard, get_options_keyboard
from bot.utils.text_manager import get_text

router = Router()

async def get_summary_text_and_keyboard(car_id: int):
    """Helper function to generate the text and keyboard for the summary menu."""
    car_data = await Car.get_active_car(car_id)

    if not car_data:
        return None, None

    field_labels = get_text('summary.field_labels')

    details = {
        'make': car_data['make'],
        'model': car_data['model'],
        'year': car_data['year'],
        'engine_model': car_data['engine_model'],
        'engine_volume': car_data['engine_volume'],
        'tank_volume': car_data['tank_volume'],
        'fuel_type': car_data['fuel_type'],
        'power': car_data['power'],
        'transmission': car_data['transmission'],
        'drive_type': car_data['drive_type'],
        'body_type': car_data['body_type'],
    }

    summary_lines = [get_text('summary.header'), get_text('summary.car_name', name=car_data[2]), ""]
    for key, label in field_labels.items():
        value = details.get(key) or get_text('summary.not_specified')
        summary_lines.append(f"{label}: <b>{value}</b>")

    text = "\n".join(summary_lines)
    keyboard = get_summary_keyboard()

    return text, keyboard

@router.callback_query(F.data == "car_summary")
async def show_summary_menu(callback: CallbackQuery, state: FSMContext):
    """Display the car summary menu."""
    await state.clear()
    user_id = callback.from_user.id
    logger.info(f"User {user_id} requested car summary.")

    text, keyboard = await get_summary_text_and_keyboard(user_id)
    if not text:
        await callback.answer("Сначала добавьте автомобиль.", show_alert=True)
        return

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_summary:"))
async def start_edit_field(callback: CallbackQuery, state: FSMContext):
    """Starts the FSM to edit a specific summary field."""
    field_to_edit = callback.data.split(":")[1]
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started editing summary field: {field_to_edit}")

    option_fields = ["body_type", "transmission", "fuel_type"]

    await state.set_state(SummaryFSM.get_value)
    await state.update_data(field_to_edit=field_to_edit)

    if field_to_edit in option_fields:
        options = get_text(f"summary.options.{field_to_edit}")
        msg =await callback.message.edit_text(
            get_text('summary.options_prompt'),
            reply_markup=get_options_keyboard(field_to_edit, options)
        )
        await state.update_data(prompt_message_id=msg.message_id)
        await callback.answer()
        return

    field_labels = get_text('summary.field_labels')
    prompt_label = field_labels.get(field_to_edit, "this field")

    msg = await callback.message.edit_text(
        get_text('summary.prompt_template', field_label=prompt_label),
        reply_markup=get_back_keyboard("car_summary")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

async def _check_and_award_profile_completion(user_id: int, bot: Bot):
    """Checks if the car profile is fully filled and awards nuts if so."""
    updated_car_data = await Car.get_active_car(user_id)
    # Check all relevant fields
    summary_fields = [
        updated_car_data['make'], updated_car_data['model'], updated_car_data['year'],
        updated_car_data['engine_model'], updated_car_data['engine_volume'],
        updated_car_data['tank_volume'], updated_car_data['fuel_type'],
        updated_car_data['power'], updated_car_data['transmission'],
        updated_car_data['drive_type'], updated_car_data['body_type']
    ]

    if all(summary_fields):
        description = "Заполнение профиля авто"
        if not await Transaction.has_received_reward(user_id, description):
            amount = config.rewards.fill_profile
            await Transaction.add_transaction(user_id, amount, description)
            logger.success(f"Awarded {amount} nuts to user {user_id} for completing car profile.")
            try:
                conf_msg = await bot.send_message(user_id, f"🎉 Поздравляем! Вы заполнили профиль и получили {amount} 🔩!")
                await asyncio.sleep(5)
                await conf_msg.delete()
            except (TelegramBadRequest, TelegramForbiddenError) as e:
                logger.warning(f"Could not send or delete completion reward notification for user {user_id}: {e}")

@router.callback_query(F.data.startswith("set_summary_option:"))
async def process_option_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Processes the selection from the options keyboard."""
    user_id = callback.from_user.id
    _, field, value = callback.data.split(":", 2)

    car = await Car.get_active_car(user_id)
    if not car:
        return

    await Car.update_car_details(car['car_id'], {field: value})
    logger.success(f"User {user_id} updated summary field '{field}' to '{value}' via option.")

    await state.clear()

    await _check_and_award_profile_completion(user_id, bot)

    text, keyboard = await get_summary_text_and_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.message(SummaryFSM.get_value)
async def process_field_value(message: Message, state: FSMContext, bot: Bot):
    """Processes the user's input for a summary field"""
    data = await state.get_data()
    field = data.get("field_to_edit")
    prompt_message_id = data.get("prompt_message_id")

    user_id = message.from_user.id
    value = message.text

    await message.delete()

    if not field or not prompt_message_id:
        logger.error(f"State is missing field or prompt_message_id for user {user_id}")
        await state.clear()
        return

    car = await Car.get_active_car(user_id)
    if not car:
        await state.clear()
        return

    await Car.update_car_details(car['car_id'], {field: value})
    logger.success(f"User {user_id} updated summary field '{field}' to '{value}'")

    await _check_and_award_profile_completion(user_id, bot)

    await state.clear()

    text, keyboard = await get_summary_text_and_keyboard(user_id)

    try:
        await bot.edit_message_text(
            text=text,
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        logger.error(f"Failed to edit summary prompt message {prompt_message_id} for user {user_id}: {e}")
        await message.answer(text, reply_markup=keyboard)