
import asyncio
import math
from datetime import datetime
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car, FuelEntry
from bot.fsm.fuel import FuelFSM
from bot.keyboards.inline import get_fuel_tracking_menu_keyboard, get_back_keyboard, get_fuel_log_keyboard, \
    get_delete_fuel_entry_keyboard
from bot.presentation.menus import show_main_menu
from bot.utils.text_manager import get_text

router = Router()

FUEL_LOG_PAGE_SIZE = 5


async def show_fuel_entry_menu(message: Message, state: FSMContext, edit: bool = True):
    """Displays or edits the message to show the interactive fuel entry menu."""
    data = await state.get_data()
    keyboard = get_fuel_tracking_menu_keyboard(data)
    text = get_text('fuel_tracking.prompt_entry_menu')

    if edit:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            # If editing fails, send a new message
            await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


async def show_fuel_log(message: Message, user_id: int, page: int = 1, edit: bool = True):
    car = await Car.get_active_car(user_id)
    if not car: return

    total_entries = await FuelEntry.get_total_fuel_entries_count(car['car_id'])
    total_pages = math.ceil(total_entries / FUEL_LOG_PAGE_SIZE) if total_entries > 0 else 1
    page = max(1, min(page, total_pages))

    entries = await FuelEntry.get_fuel_entries_paginated(car['car_id'], page, FUEL_LOG_PAGE_SIZE)

    text_lines = [get_text('fuel_log.header', car_name=car['name'])]

    # Add summary block only on the first page
    if page == 1:
        summary = await FuelEntry.get_fuel_summary(car['car_id'])
        text_lines.extend([
            get_text('fuel_log.liters_header'),
            get_text('fuel_log.liters_this_month', value=f"{summary['liters_this_month']:.2f} л."),
            get_text('fuel_log.liters_last_month', value=f"{summary['liters_last_month']:.2f} л."),
            get_text('fuel_log.liters_all_time', value=f"{summary['liters_all_time']:.2f} л."),
            "",
            get_text('fuel_log.sum_header'),
            get_text('fuel_log.sum_this_month', value=f"{summary['sum_this_month']:.2f} ₽"),
            get_text('fuel_log.sum_last_month', value=f"{summary['sum_last_month']:.2f} ₽"),
            get_text('fuel_log.sum_all_time', value=f"{summary['sum_all_time']:.2f} ₽"),
            "─" * 20
        ])

    for entry in entries:
        date_str = datetime.strptime(entry['created_at'], '%Y-%m-%d').strftime('%d.%m.%y')
        total_sum_str = f"{entry['total_sum']:.2f}р" if entry['total_sum'] else "не указана"
        distance = entry['distance']

        consumption_str = "..."  # Default value

        # 1. Prioritize the accurate, stored value if it exists
        if entry['fuel_consumption']:
            consumption_str = f"{entry['fuel_consumption']:.2f} л/100км"

        # 2. If no stored value, try to calculate an estimate for this trip
        elif distance > 0 and entry['liters'] > 0:
            # Manually calculate consumption for the distance since the last entry
            manual_consumption = (entry['liters'] / distance) * 100
            # Add a tilde ~ to show it's an estimate
            consumption_str = f"~{manual_consumption:.2f} л/100км"

        # 3. If calculation is impossible, explain why
        elif not car['tank_volume']:
            consumption_str = get_text('fuel_log.consumption_unknown')

        entry_text = get_text(
            'fuel_log.entry_line',
            date=date_str, liters=entry['liters'], distance=distance,
            total_sum=total_sum_str, consumption=consumption_str
        )
        text_lines.append(entry_text)

    text = "\n".join(text_lines)
    keyboard = get_fuel_log_keyboard(page, total_pages, car['tank_volume'])

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

async def finish_fuel_entry(user_id: int, state: FSMContext, bot: Bot, callback_query_id: Optional[str] = None) -> Optional[Message]:
    """Saves the entry, calculates consumption, and shows the main menu."""
    data = await state.get_data()
    car = await Car.get_active_car(user_id)
    if not car or not data.get("mileage") or not data.get("liters"):
        return

    new_entry_id = await FuelEntry.add_entry(
        car_id=car['car_id'],
        mileage=data["mileage"],
        liters=data["liters"],
        total_sum=data.get("total_sum"),
        is_full=data.get("is_full", False),
        date=data.get("date_sql", datetime.now().strftime('%Y-%m-%d'))
    )

    new_entry = await FuelEntry.get_entry_by_id(new_entry_id)
    if new_entry and new_entry['is_full']:
        previous_full_tank = await FuelEntry.get_previous_full_tank(car['car_id'], new_entry['created_at'])
        if previous_full_tank:
            distance = new_entry['mileage'] - previous_full_tank['mileage']
            if distance > 0:
                # Sum all liters added AFTER the previous full tank up to and including this one
                liters_sum = await FuelEntry.get_interim_fuel_sum(
                    car['car_id'],
                    previous_full_tank['created_at'],
                    new_entry['created_at']
                )
                if liters_sum > 0:
                    consumption = (liters_sum / distance) * 100
                    await FuelEntry.update_consumption(new_entry_id, consumption)
                    logger.info(f"Calculated accurate fuel consumption: {consumption:.2f} L/100km for entry {new_entry_id}")

    # Conditionally update car's main mileage
    if car['mileage'] is None or data['mileage'] > car['mileage']:
        await Car.update_mileage(car['car_id'], data['mileage'])

    total_sum = data.get("total_sum")
    text = get_text('fuel_tracking.success_message', total_sum=total_sum) if total_sum else get_text('fuel_tracking.success_message_no_sum', liters=data.get("liters"))

    if callback_query_id:
        await bot.answer_callback_query(callback_query_id, text=text, show_alert=False)
        return None
    else:
        return await bot.send_message(user_id, text)


@router.callback_query(F.data == "add_fuel")
async def start_fuel_tracking(callback: CallbackQuery, state: FSMContext):
    """Initiates the fuel tracking workflow."""
    user_id = callback.from_user.id
    await state.clear()
    car = await Car.get_active_car(user_id)

    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return

    # Check if tank volume is set
    if not car['tank_volume']:
        await state.set_state(FuelFSM.get_tank_volume)
        msg = await callback.message.edit_text(
            get_text('fuel_tracking.prompt_tank_volume'),
            reply_markup=get_back_keyboard("main_menu")  # Assuming a simple back keyboard
        )
        await state.update_data(prompt_message_id=msg.message_id)
        await callback.answer()
        return

    # Proceed to main entry menu
    await state.set_state(FuelFSM.entry_menu)

    current_mileage = car['mileage'] if car and car['mileage'] is not None else None

    await state.update_data(
        prompt_message_id=callback.message.message_id,
        is_full=False,
        mileage=current_mileage,
        date_str=datetime.now().strftime('%d.%m.%Y'),
        date_sql=datetime.now().strftime('%Y-%m-%d')
    )

    await show_fuel_entry_menu(callback.message, state, edit=True)
    await callback.answer()


@router.message(FuelFSM.get_tank_volume)
async def process_tank_volume(message: Message, state: FSMContext, bot: Bot):
    """Processes user input for tank volume."""
    if not message.text.isdigit():
        error_msg = await message.reply(get_text('errors.must_be_digit'))
        await asyncio.sleep(3)
        await error_msg.delete()
        await message.delete()
        return

    await message.delete()

    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except TelegramBadRequest:
            logger.warning(f"Could not delete tank volume prompt message {prompt_id}.")

    car = await Car.get_active_car(message.from_user.id)
    await Car.update_car_details(car['car_id'], {'tank_volume': float(message.text)})

    await state.set_state(FuelFSM.entry_menu)
    new_data = {
        "is_full": False,
        "date_str": datetime.now().strftime('%d.%m.%Y'),
        "date_sql": datetime.now().strftime('%Y-%m-%d')
    }
    await state.update_data(**new_data)

    new_msg = await bot.send_message(
        chat_id=message.chat.id,
        text=get_text('fuel_tracking.prompt_entry_menu'),
        reply_markup=get_fuel_tracking_menu_keyboard(new_data)
    )
    await state.update_data(prompt_message_id=new_msg.message_id)


@router.message(FuelFSM.entry_menu, F.text)
async def process_fast_fuel_entry(message: Message, state: FSMContext, bot: Bot):
    """Handles the quick entry format: Mileage Liters Sum"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(get_text('fuel_tracking.invalid_fast_format'))
        return

    try:
        mileage = int(parts[0])
        liters = float(parts[1])
        total_sum = float(parts[2]) if len(parts) > 2 else None

        await state.update_data(mileage=mileage, liters=liters, total_sum=total_sum)

        temp_msg = await finish_fuel_entry(message.from_user.id, state, bot)
        await state.clear()

        await message.delete()
        await show_main_menu(message, user_id=message.from_user.id, edit=False)

        if temp_msg:
            await asyncio.sleep(4)
            try:
                await temp_msg.delete()
            except TelegramBadRequest:
                pass

    except ValueError:
        await message.reply(get_text('fuel_tracking.invalid_fast_format'))


@router.callback_query(F.data.startswith("fuel:"))
async def fuel_menu_callback_router(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Routes all callbacks starting with 'fuel:'."""
    action = callback.data.split(":")[1]

    if action == "toggle_full":
        data = await state.get_data()
        new_is_full_state = not data.get("is_full", False)

        await state.update_data(is_full=new_is_full_state)
        await show_fuel_entry_menu(callback.message, state, edit=True)

    elif action == "edit":
        field = callback.data.split(":")[2]
        if field == "mileage":
            await state.set_state(FuelFSM.get_mileage)
            await callback.message.edit_text(get_text('fuel_tracking.prompt_mileage'))
        elif field == "liters":
            await state.set_state(FuelFSM.get_liters)
            await callback.message.edit_text(get_text('fuel_tracking.prompt_liters'))
        elif field == "sum":
            await state.set_state(FuelFSM.get_sum)
            await callback.message.edit_text(get_text('fuel_tracking.prompt_sum'))
        elif field == "date":
            await state.set_state(FuelFSM.get_date)
            await callback.message.edit_text(get_text('fuel_tracking.prompt_date'))

    elif action == "create":
        data = await state.get_data()
        if not data.get("mileage") or not data.get("liters"):
            await callback.answer(get_text('fuel_tracking.error_not_enough_data'), show_alert=True)
            return
        await finish_fuel_entry(callback.from_user.id, state, bot, callback.id)

        await state.clear()
        await callback.message.delete()
        await show_main_menu(callback.message, callback.from_user.id, edit=False)

    await callback.answer()


async def process_text_input(message: Message, state: FSMContext, field: str, bot: Bot):
    """Generic handler for processing text input for a specific field."""
    value = message.text
    update_data = {}

    try:
        if field == "mileage":
            update_data["mileage"] = int(value)
        elif field == "liters":
            update_data["liters"] = float(value)
        elif field == "sum":
            update_data["total_sum"] = float(value)
        elif field == "date":
            date_obj = datetime.strptime(value, "%d.%m.%Y")
            update_data["date_sql"] = date_obj.strftime("%Y-%m-%d")
            update_data["date_str"] = value

        await state.update_data(**update_data)
        await state.set_state(FuelFSM.entry_menu)

        await message.delete()

        data = await state.get_data()
        prompt_message_id = data.get("prompt_message_id")

        if prompt_message_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
            except TelegramBadRequest:
                pass

        new_data = await state.get_data()
        keyboard = get_fuel_tracking_menu_keyboard(new_data)
        text = get_text('fuel_tracking.prompt_entry_menu')
        new_msg = await bot.send_message(chat_id=message.chat.id, text=text, reply_markup=keyboard)

        await state.update_data(prompt_message_id=new_msg.message_id)

    except (ValueError, TypeError):
        msg = await message.reply("Неверный формат. Попробуйте еще раз.")
        await asyncio.sleep(3)
        await message.delete()
        await msg.delete()


@router.message(FuelFSM.get_mileage)
async def process_fuel_mileage_input(message: Message, state: FSMContext, bot: Bot):
    await process_text_input(message, state, "mileage", bot)


@router.message(FuelFSM.get_liters)
async def process_fuel_liters_input(message: Message, state: FSMContext, bot: Bot):
    await process_text_input(message, state, "liters", bot)


@router.message(FuelFSM.get_sum)
async def process_fuel_sum_input(message: Message, state: FSMContext, bot: Bot):
    await process_text_input(message, state, "sum", bot)


@router.message(FuelFSM.get_date)
async def process_fuel_date_input(message: Message, state: FSMContext, bot: Bot):
    await process_text_input(message, state, "date", bot)

@router.callback_query(F.data == "fuel_log")
async def fuel_log_start(callback: CallbackQuery):
    await show_fuel_log(callback.message, callback.from_user.id, page=1, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("fuel_log_page:"))
async def fuel_log_paginate(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_fuel_log(callback.message, callback.from_user.id, page=page, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_fuel_entry_start:"))
async def delete_fuel_entry_start(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    car = await Car.get_active_car(callback.from_user.id)
    if not car: return

    entries = await FuelEntry.get_fuel_entries_paginated(car['car_id'], page, FUEL_LOG_PAGE_SIZE)

    await callback.message.edit_text(
        get_text('fuel_log.delete_prompt'),
        reply_markup=get_delete_fuel_entry_keyboard(entries, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_fuel_entry_confirm:"))
async def delete_fuel_entry_confirm(callback: CallbackQuery):
    _, entry_id_str, page_str = callback.data.split(":")
    entry_id, page = int(entry_id_str), int(page_str)

    await FuelEntry.delete_entry(entry_id)
    await callback.answer(get_text('fuel_log.entry_deleted_success'), show_alert=True)

    # Refresh the fuel log view
    await show_fuel_log(callback.message, callback.from_user.id, page=page, edit=True)