import asyncio
import math
import re
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.config import config
from bot.database.models import Car, Transaction
from bot.fsm.update import UpdateFSM
from bot.keyboards.inline import get_back_keyboard
from bot.presentation.menus import show_main_menu, _get_main_menu_content
from bot.utils.text_manager import get_text

router = Router()


async def _process_and_update_mileage(user_id: int, new_mileage: int) -> bool:
    """
    Handles the business logic of updating mileage, calculating rewards, and persisting changes.
    Returns True if successful, False otherwise.
    """
    active_car = await Car.get_active_car(user_id)
    if not active_car:
        logger.error(f"User {user_id} tried to update mileage but no active car was found.")
        return False

    car_id = active_car['car_id']
    car_data = await Car.get_car_for_allowance_update(car_id)
    if not car_data:
        logger.error(f"Could not fetch car {car_id} for allowance update.")
        return False

    old_mileage, current_allowance, last_update_str = car_data

    if old_mileage is None:
        old_mileage = 0

    today = datetime.now().date()
    last_update_date = datetime.strptime(last_update_str, "%Y-%m-%d").date()
    days_passed = (today - last_update_date).days

    if days_passed > 0:
        allowance_to_add = days_passed * config.rewards.mileage_allowance_per_day
        current_allowance += allowance_to_add
        logger.info(
            f"User {user_id} gets {allowance_to_add}km allowance for {days_passed} days. New total: {current_allowance}km.")

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
    return True


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

    success = await _process_and_update_mileage(user_id, new_mileage)
    if not success:
        error_msg = await message.answer(
            "Не удалось обновить пробег. Возможно, у вас нет активного авто.")
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        await state.clear()
        return

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await state.clear()
    await message.delete()

    if prompt_message_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete mileage update prompt message {prompt_message_id}: {e}")

    await show_main_menu(message, user_id, edit=False)


@router.message(F.text.regexp(r'(?i)^пробег\s+(\d+)$'))
async def handle_direct_mileage_update(message: Message):
    """
    Handles direct mileage update from a text message like "Пробег 12345".
    """
    user_id = message.from_user.id
    match = re.match(r'(?i)^пробег\s+(\d+)', message.text)
    if not match:
        return

    new_mileage = int(match.group(1))
    logger.info(f"User {user_id} initiated a direct mileage update to {new_mileage}.")

    success = await _process_and_update_mileage(user_id, new_mileage)

    if success:
        await show_main_menu(message, user_id, edit=False)
        conf_msg = await message.answer("✅ Пробег успешно обновлён!")
        await asyncio.sleep(3)
        await conf_msg.delete()
    else:
        await message.reply("Не удалось обновить пробег. Убедитесь, что у вас есть активный автомобиль и новое значение пробега больше текущего.")