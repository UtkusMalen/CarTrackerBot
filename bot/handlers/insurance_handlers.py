import asyncio
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car
from bot.fsm.insurance import InsuranceFSM
from bot.keyboards.inline import get_insurance_duration_keyboard, get_back_keyboard
from bot.presentation.menus import show_main_menu
from bot.utils.text_manager import get_text

router = Router()

@router.callback_query(F.data == "add_insurance")
async def start_add_insurance(callback: CallbackQuery, state: FSMContext):
    """Starts the process of adding an insurance."""
    await state.set_state(InsuranceFSM.get_duration)
    await callback.message.edit_text(
        get_text('insurance.prompt_duration'),
        reply_markup=get_insurance_duration_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_insurance_duration:"))
async def process_duration(callback: CallbackQuery, state: FSMContext):
    """Handles the user's selection of insurance duration."""
    duration_days = int(callback.data.split(":")[1])
    await state.update_data(duration_days=duration_days)
    await state.set_state(InsuranceFSM.get_start_date)

    msg =await callback.message.edit_text(
        get_text('insurance.prompt_start_date'),
        reply_markup=get_back_keyboard("add_insurance")
    )

    await state.update_data(prompt_message_id=msg.message_id)

    await callback.answer()

@router.message(InsuranceFSM.get_start_date)
async def process_start_date(message: Message, state: FSMContext, bot: Bot):
    """Handles the user's input for the start date."""
    user_id = message.from_user.id
    try:
        start_date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        start_date_str = start_date_obj.strftime("%Y-%m-%d")
    except ValueError:
        msg = await message.reply(get_text('errors.invalid_date_format'))
        await message.delete()
        await asyncio.sleep(5)
        await msg.delete()
        return

    data = await state.get_data()
    duration_days = data.get("duration_days")
    prompt_message_id = data.get("prompt_message_id")

    active_car = await Car.get_active_car(user_id)
    if not active_car:
        await state.clear()
        return

    if prompt_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
        except TelegramBadRequest:
            logger.warning(f"Could not delete prompt message {prompt_message_id}. It might have been deleted already.")

    car_id = active_car[0]
    await Car.update_insurance(car_id, start_date_str, duration_days)

    await state.clear()
    await message.delete()

    conf_msg = await message.answer(get_text('insurance.success_message'))

    await show_main_menu(message, user_id, edit=False)

    await asyncio.sleep(3)
    await conf_msg.delete()