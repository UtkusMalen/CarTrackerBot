import asyncio
from datetime import timedelta, datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiosqlite import Row
from loguru import logger

from bot.config import config
from bot.database.models import Car, Reminder, Transaction, User
from bot.fsm.reminders import ReminderFSM
from bot.keyboards.inline import (
    get_tracking_menu_keyboard,
    get_back_keyboard,
    get_reminder_management_keyboard,
    get_mileage_tracking_initial_keyboard,
    get_time_tracking_keyboard,
    get_mileage_tracking_edit_keyboard,
    get_time_tracking_edit_keyboard,
    get_reset_mileage_tracking_keyboard,
    get_reset_time_tracking_keyboard,
    get_reminder_type_keyboard, get_use_current_mileage_keyboard, get_notification_config_keyboard,
    get_exact_mileage_edit_keyboard, get_use_current_date_for_start_keyboard
)
from bot.presentation.menus import show_main_menu
from bot.utils.text_manager import get_text

router = Router()


# #################################################################
# #################### CONTENT HELPER FUNCTIONS ###################
# #################################################################

async def _get_mileage_tracking_menu_content(reminder: Row, car: Row) -> tuple[str, InlineKeyboardMarkup]:
    """
    Generates the text and keyboard for the mileage tracking detail menu.
    This is now fully dynamic.
    """
    name = reminder['name']
    reminder_id = reminder['reminder_id']
    reminder_type = reminder['type']

    menu_parts = []

    if reminder_type == 'exact_mileage':
        menu_parts.append(get_text('reminders.manage_header', name=name))
        target_val = reminder['target_mileage'] if reminder['target_mileage'] is not None else get_text(
            'reminders.manage_mileage_based.value_not_set')
        menu_parts.append(get_text('reminders.manage_exact_mileage.target_line', value=target_val))

        is_fully_configured = reminder['target_mileage'] is not None and car and car['mileage'] is not None

        if is_fully_configured:
            remaining_km = reminder['target_mileage'] - car['mileage']
            remaining_val = max(0, remaining_km)
            keyboard = get_reminder_management_keyboard(reminder_id)
        else:
            remaining_val = get_text('reminders.manage_mileage_based.value_not_set')
            keyboard = get_mileage_tracking_initial_keyboard(reminder_id)

        menu_parts.append(get_text('reminders.manage_exact_mileage.remaining_line', value=remaining_val))
        if not is_fully_configured:
            menu_parts.append(get_text('reminders.manage_mileage_based.setup_prompt'))
    else:
        menu_parts.append(get_text('reminders.manage_header', name=name))
        interval_val = reminder['interval_km'] if reminder['interval_km'] is not None else get_text(
            'reminders.manage_mileage_based.value_not_set')
        menu_parts.append(get_text('reminders.manage_mileage_based.interval_line', value=interval_val))
        start_val = reminder['last_reset_mileage'] if reminder['last_reset_mileage'] is not None else get_text(
            'reminders.manage_mileage_based.value_not_set')
        menu_parts.append(get_text('reminders.manage_mileage_based.start_mileage_line', value=start_val))
        is_fully_configured = all([
            reminder['last_reset_mileage'] is not None,
            reminder['interval_km'] is not None,
            car and car['mileage'] is not None
        ])

        if is_fully_configured:
            remaining_km = (reminder['last_reset_mileage'] + reminder['interval_km']) - car['mileage']
            remaining_val = max(0, remaining_km)
            keyboard = get_reminder_management_keyboard(reminder_id)
        else:
            remaining_val = get_text('reminders.manage_mileage_based.value_not_set')
            keyboard = get_mileage_tracking_initial_keyboard(reminder_id)
        menu_parts.append(get_text('reminders.manage_mileage_based.remaining_line', value=remaining_val))
        if not is_fully_configured:
            menu_parts.append(get_text('reminders.manage_mileage_based.setup_prompt'))

    menu_text = "\n".join(menu_parts)
    return menu_text, keyboard


async def _get_time_tracking_menu_content(reminder: Row) -> tuple[str, InlineKeyboardMarkup]:
    """Generates the text and keyboard for the time tracking detail menu."""
    text = get_text('reminders.manage_time_based.header', name=reminder['name'])
    is_configured = reminder['last_reset_date'] and reminder['interval_days']

    if is_configured:
        start_date = datetime.strptime(reminder['last_reset_date'], '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=reminder['interval_days'])
        remaining_days = (end_date - datetime.now().date()).days

        text += "\n" + get_text('reminders.manage_time_based.details',
                                start_date=start_date.strftime('%d.%m.%Y'),
                                end_date=end_date.strftime('%d.%m.%Y'),
                                remaining_days=max(0, remaining_days))
        text += "\n\n" + get_text('reminders.manage_time_based.prompt_reset')
        keyboard = get_time_tracking_keyboard(reminder['reminder_id'], is_repeating=reminder['is_repeating'])
    else:
        text += "\n\n" + get_text('reminders.manage_time_based.prompt_initial')
        keyboard = get_time_tracking_keyboard(reminder['reminder_id'], is_initial=True)

    return text, keyboard


# #################################################################
# ###################### MENU NAVIGATION ##########################
# #################################################################

@router.callback_query(F.data == "manage_trackings")
async def show_tracking_list_menu(callback: CallbackQuery):
    """Displays the list of all trackings (reminders) for the active car."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} requested the tracking management menu.")

    car = await Car.get_active_car(user_id)
    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return

    user_data = await User.get_user(user_id)
    balance = user_data[3] if user_data else 0
    reminders = await Reminder.get_reminders_for_car(car['car_id'])

    text = get_text(
        'reminders.tracking_menu_header',
        car_name=car['name'],
        cost=config.costs.create_reminder,
        balance=balance
    )
    keyboard = get_tracking_menu_keyboard(reminders)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("manage_reminder:"))
async def manage_reminder_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Acts as a router to direct to the correct management menu based on reminder type."""
    await state.clear()
    reminder_id = int(callback.data.split(":")[1])
    logger.info(f"User {callback.from_user.id} managing reminder {reminder_id}.")

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    if reminder['type'] == 'time':
        await show_time_tracking_detail_menu(callback.message, reminder, bot, callback_id=callback.id)
    else:
        await show_mileage_tracking_detail_menu(callback.message, callback.from_user.id, reminder, bot,
                                                callback_id=callback.id)


async def show_mileage_tracking_detail_menu(message: Message, user_id: int, reminder: Row, bot: Bot,
                                            callback_id: str = None):
    """Displays the detail menu for a mileage-based tracking."""
    car = await Car.get_active_car(user_id)
    if not car: return

    menu_text, keyboard = await _get_mileage_tracking_menu_content(reminder, car)

    await bot.edit_message_text(menu_text, chat_id=message.chat.id, message_id=message.message_id,
                                reply_markup=keyboard)
    if callback_id:
        await bot.answer_callback_query(callback_id)


async def show_time_tracking_detail_menu(message: Message, reminder: Row, bot: Bot, callback_id: str = None):
    """Displays the detail menu for a time-based tracking."""
    text, keyboard = await _get_time_tracking_menu_content(reminder)

    await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message.message_id, reply_markup=keyboard)
    if callback_id:
        await bot.answer_callback_query(callback_id)


# #################################################################
# ################### NEW REMINDER CREATION FLOW ##################
# #################################################################

@router.callback_query(F.data == "create_reminder")
async def create_reminder_start(callback: CallbackQuery, state: FSMContext):
    """Starts the FSM for creating a new reminder by asking for a name."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} entered the new reminder creation flow.")

    cost = config.costs.create_reminder
    user_data = await User.get_user(user_id)
    balance = user_data[3] if user_data else 0

    if balance < cost:
        logger.warning(f"User {user_id} has insufficient funds to create a reminder.")
        await callback.answer(
            get_text('reminders.errors.insufficient_funds_for_reminder', cost=cost, balance=balance),
            show_alert=True
        )
        return

    await state.set_state(ReminderFSM.get_name)
    msg = await callback.message.edit_text(
        get_text('reminders_flow.prompt_name'),
        reply_markup=get_back_keyboard("manage_trackings")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()


@router.message(ReminderFSM.get_name)
async def process_reminder_name(message: Message, state: FSMContext, bot: Bot):
    """Processes the reminder name and asks for its type."""
    await state.update_data(name=message.text)
    await state.set_state(ReminderFSM.choose_type)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()

    if prompt_message_id:
        await bot.edit_message_text(
            get_text('reminders_flow.prompt_type'),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_reminder_type_keyboard()
        )


@router.callback_query(F.data.startswith("set_reminder_type:"))
async def process_reminder_type(callback: CallbackQuery, state: FSMContext):
    """Processes the chosen reminder type and asks for the next piece of data."""
    reminder_type = callback.data.split(":")[1]
    await state.update_data(type=reminder_type)

    data = await state.get_data()
    reminder_name = data.get("name", "")

    prompt_text = ""
    next_state = None
    keyboard = get_back_keyboard("create_reminder")

    if reminder_type == "mileage_interval":
        prompt_text = get_text('reminders_flow.prompt_mileage_interval', name=reminder_name)
        next_state = ReminderFSM.get_mileage_interval
    elif reminder_type == "exact_mileage":
        prompt_text = get_text('reminders_flow.prompt_exact_mileage', name=reminder_name)
        next_state = ReminderFSM.get_exact_mileage_target
    elif reminder_type == "time":
        prompt_text = get_text('reminders_flow.prompt_time_target', name=reminder_name)
        next_state = ReminderFSM.get_time_target_date

    await state.set_state(next_state)
    await callback.message.edit_text(prompt_text, reply_markup=keyboard)
    await callback.answer()


async def _finish_reminder_creation(state: FSMContext, user_id: int, message: Message, bot: Bot):
    """A helper function to save the new reminder to the DB and show the final step."""
    data = await state.get_data()
    car = await Car.get_active_car(user_id)

    if not car:
        logger.error(f"User {user_id} tried to create reminder but has no active car.")
        await state.clear()
        return

    reminder_id = await Reminder.add_reminder(
        car_id=car['car_id'],
        name=data.get('name'),
        type=data.get('type'),
        interval_km=data.get('interval_km'),
        last_reset_mileage=data.get('last_reset_mileage'),
        target_mileage=data.get('target_mileage'),
        interval_days=data.get('interval_days'),
        last_reset_date=data.get('last_reset_date'),
        target_date=data.get('target_date')
    )

    cost = config.costs.create_reminder
    await Transaction.add_transaction(user_id, -cost, f"Создание отслеживания: {data.get('name')}")
    logger.success(f"Charged {user_id} {cost} nuts for creating reminder '{data.get('name')}'.")

    await state.clear()

    final_text = get_text('reminders_flow.creation_success', name=data.get('name'))
    if data.get("type") == 'time':
        final_text += f"\n\n{get_text('reminders_flow.creation_success_time_addon')}"
    keyboard = get_notification_config_keyboard(reminder_id)

    prompt_message_id = data.get("prompt_message_id")
    if prompt_message_id:
        await bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=prompt_message_id,
                                    reply_markup=keyboard)
    else:
        await message.answer(final_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("finish_creation:"))
async def process_finish_creation(callback: CallbackQuery, state: FSMContext):
    """Handles the final confirmation button, taking the user to the main menu."""
    await state.clear()
    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer()


@router.message(ReminderFSM.get_mileage_interval)
async def process_mileage_interval(message: Message, state: FSMContext, bot: Bot):
    """Processes the mileage interval and asks for the starting mileage."""
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await state.update_data(interval_km=int(message.text))
    await state.set_state(ReminderFSM.get_mileage_interval_start)

    car = await Car.get_active_car(message.from_user.id)
    data = await state.get_data()
    reminder_name = data.get("name", "")
    prompt_text = get_text('reminders_flow.prompt_mileage_interval_start', name=reminder_name)
    keyboard = get_use_current_mileage_keyboard("create_reminder", car['mileage'] if car else 0)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    if prompt_message_id:
        await bot.edit_message_text(prompt_text, chat_id=message.chat.id, message_id=prompt_message_id,
                                    reply_markup=keyboard)


@router.message(ReminderFSM.get_mileage_interval_start)
async def process_mileage_interval_start(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await state.update_data(last_reset_mileage=int(message.text))
    await _finish_reminder_creation(state, message.from_user.id, message, bot)
    await message.delete()


@router.message(ReminderFSM.get_exact_mileage_target)
async def process_exact_mileage_target(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await state.update_data(target_mileage=int(message.text))
    await _finish_reminder_creation(state, message.from_user.id, message, bot)
    await message.delete()


@router.message(ReminderFSM.get_time_target_date)
async def process_time_end_date(message: Message, state: FSMContext, bot: Bot):
    """
    Step 1 for time reminders: Processes the END date and transitions to ask for the START date.
    """
    try:
        end_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        if end_date <= datetime.now().date():
            await message.reply("Дата окончания должна быть в будущем.")
            return

        await state.update_data(end_date=end_date)
        await state.set_state(ReminderFSM.get_time_start_date)

        data = await state.get_data()
        prompt_message_id = data.get("prompt_message_id")
        reminder_name = data.get("name", "")

        prompt_text = get_text('reminders_flow.prompt_start_date_generic', name=reminder_name)
        # We need a back button to the previous step, which was choosing the type
        keyboard = get_use_current_date_for_start_keyboard("create_reminder")

        await message.delete()
        if prompt_message_id:
            await bot.edit_message_text(
                prompt_text,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
                reply_markup=keyboard
            )
    except ValueError:
        await message.reply(get_text('errors.invalid_date_format'))
        return


# ADD THIS NEW HANDLER for text input of the start date
@router.message(ReminderFSM.get_time_start_date)
async def process_time_start_date(message: Message, state: FSMContext, bot: Bot):
    """
    Step 2 for time reminders: Processes the START date (from text) and finishes creation.
    """
    try:
        start_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(start_date=start_date)
        await _calculate_and_finish_time_reminder(state, message.from_user.id, message, bot)
        await message.delete()
    except ValueError:
        await message.reply(get_text('errors.invalid_date_format'))
        return


# ADD THIS NEW HANDLER for the "Use current date" button click
@router.callback_query(F.data == "use_current_date_for_start", ReminderFSM.get_time_start_date)
async def process_use_current_date_for_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    Step 2 for time reminders: Processes the START date (from button) and finishes creation.
    """
    start_date = datetime.now().date()
    await state.update_data(start_date=start_date)
    await _calculate_and_finish_time_reminder(state, callback.from_user.id, callback.message, bot)


# ADD THIS NEW HELPER function to calculate the interval
async def _calculate_and_finish_time_reminder(state: FSMContext, user_id: int, message: Message, bot: Bot):
    """
    Calculates the interval in days from the start and end dates and calls the final creation function.
    """
    data = await state.get_data()
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not start_date or not end_date:
        logger.error("State is missing start_date or end_date in time reminder creation.")
        await state.clear()
        return

    if start_date >= end_date:
        # This check is now inside the handlers, but we keep it here as a safeguard
        await message.answer("Дата начала должна быть раньше даты окончания. Попробуйте снова.")
        # Re-prompt for the start date
        await state.set_state(ReminderFSM.get_time_start_date)
        return

    interval_days = (end_date - start_date).days
    await state.update_data(
        interval_days=interval_days,
        last_reset_date=start_date.strftime("%Y-%m-%d"),
        target_date=end_date.strftime("%Y-%m-%d") # Also save the target date for potential future use
    )

    await _finish_reminder_creation(state, user_id, message, bot)


@router.callback_query(F.data.startswith("use_current_mileage:"))
async def process_use_current_mileage(callback: CallbackQuery, state: FSMContext, bot: Bot):
    mileage = int(callback.data.split(":")[1])
    await state.update_data(last_reset_mileage=mileage)
    await _finish_reminder_creation(state, callback.from_user.id, callback.message, bot)


# #################################################################
# #################### REMINDER EDITING FLOW ######################
# #################################################################

async def _process_fsm_edit(message: Message, state: FSMContext, bot: Bot, update_dict: dict):
    """Helper to process FSM updates for editing reminders."""
    data = await state.get_data()
    reminder_id = data.get("reminder_id")
    prompt_message_id = data.get("prompt_message_id")
    user_id = message.from_user.id

    await message.delete()
    if not reminder_id or not prompt_message_id:
        logger.error("State data missing in FSM edit process.")
        await state.clear()
        return

    await Reminder.update_reminder_details(reminder_id, update_dict)
    await state.clear()

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await show_main_menu(message, user_id, edit=False)
        return

    text = get_text('reminders_flow.edit_header', name=reminder["name"])
    if reminder['type'] == 'time':
        keyboard = get_time_tracking_edit_keyboard(reminder_id)
    elif reminder['type'] == 'exact_mileage':
        keyboard = get_exact_mileage_edit_keyboard(reminder_id)
    else:
        keyboard = get_mileage_tracking_edit_keyboard(reminder_id)

    try:
        await bot.edit_message_text(
            text=text,
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=keyboard
        )
    except TelegramBadRequest:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("edit_mileage_tracking:"))
async def show_edit_mileage_tracking_menu(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    text = get_text('reminders_flow.edit_header', name=reminder["name"])
    if reminder['type'] == 'exact_mileage':
        keyboard = get_exact_mileage_edit_keyboard(reminder_id)
    else: # Default to interval based
        keyboard = get_mileage_tracking_edit_keyboard(reminder_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_reminder_interval_km:"))
async def start_edit_reminder_interval_km(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_interval_km)
    await callback.message.edit_text(
        get_text('reminders_flow.prompt_edit_interval_km'),
        reply_markup=get_back_keyboard(f"edit_mileage_tracking:{reminder_id}")
    )


@router.message(ReminderFSM.edit_interval_km)
async def process_edit_reminder_interval_km(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await _process_fsm_edit(message, state, bot, {"interval_km": int(message.text)})


@router.callback_query(F.data.startswith("edit_reminder_last_reset_mileage:"))
async def start_edit_last_reset_mileage(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    car = await Car.get_active_car(callback.from_user.id)
    if not car or car['mileage'] is None:
        await callback.answer(get_text('errors.mileage_not_set_error'), show_alert=True)
        return

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_last_reset_mileage)
    await callback.message.edit_text(
        text=get_text('reminders_flow.prompt_start_mileage_generic', name=reminder['name']),
        reply_markup=get_reset_mileage_tracking_keyboard(reminder_id, car['mileage'])
    )


@router.message(ReminderFSM.edit_last_reset_mileage)
async def process_edit_last_reset_mileage(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await _process_fsm_edit(message, state, bot, {"last_reset_mileage": int(message.text)})


@router.callback_query(F.data.startswith("edit_time_tracking:"))
async def show_edit_time_tracking_menu(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    reminder = await Reminder.get_reminder(reminder_id)
    text = get_text('reminders_flow.edit_header', name=reminder["name"])
    keyboard = get_time_tracking_edit_keyboard(reminder_id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_reminder_name:"))
async def start_edit_reminder_name(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_name)

    if reminder['type'] == 'time':
        back_callback = f"edit_time_tracking:{reminder_id}"
    else:
        back_callback = f"edit_mileage_tracking:{reminder_id}"

    await callback.message.edit_text(
        get_text('reminders_flow.prompt_edit_name'),
        reply_markup=get_back_keyboard(back_callback)
    )


@router.message(ReminderFSM.edit_name)
async def process_edit_reminder_name(message: Message, state: FSMContext, bot: Bot):
    await _process_fsm_edit(message, state, bot, {"name": message.text})


@router.callback_query(F.data.startswith("edit_reminder_interval_days:"))
async def start_edit_reminder_interval(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_interval_days)
    await callback.message.edit_text(
        get_text('reminders_flow.prompt_edit_interval_days'),
        reply_markup=get_back_keyboard(f"edit_time_tracking:{reminder_id}")
    )


@router.message(ReminderFSM.edit_interval_days)
async def process_edit_reminder_interval(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await _process_fsm_edit(message, state, bot, {"interval_days": int(message.text)})


@router.callback_query(F.data.startswith("edit_reminder_start_date:"))
async def start_edit_reminder_start_date(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_start_date)
    await callback.message.edit_text(
        text=get_text('reminders_flow.prompt_start_date_generic', name=reminder['name']),
        reply_markup=get_reset_time_tracking_keyboard(reminder_id)
    )


@router.message(ReminderFSM.edit_start_date)
async def process_edit_reminder_start_date(message: Message, state: FSMContext, bot: Bot):
    try:
        start_date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        start_date_str = start_date_obj.strftime("%Y-%m-%d")
        await _process_fsm_edit(message, state, bot, {"last_reset_date": start_date_str})
    except ValueError:
        await message.reply(get_text('errors.invalid_date_format'))
        return


# #################################################################
# ###################### ACTION HANDLERS ##########################
# #################################################################


@router.callback_query(F.data.startswith("reset_mileage_tracking_start:"))
async def start_reset_mileage_tracking(callback: CallbackQuery, state: FSMContext):
    """Handles the 'Запустить заново' button for mileage tracking."""
    await start_edit_last_reset_mileage(callback, state)


@router.callback_query(F.data.startswith("reset_time_tracking_start:"))
async def start_reset_time_tracking(callback: CallbackQuery, state: FSMContext):
    """Handles the 'Запустить заново' button for time tracking."""
    await start_edit_reminder_start_date(callback, state)


@router.callback_query(F.data.startswith("set_current_mileage:"))
async def set_current_mileage_for_tracking(callback: CallbackQuery, bot: Bot):
    reminder_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    car = await Car.get_active_car(user_id)
    if not car or car['mileage'] is None:
        await callback.answer(get_text('errors.mileage_not_set_error'), show_alert=True)
        return

    await Reminder.update_reminder_details(reminder_id, {"last_reset_mileage": car['mileage']})

    reminder = await Reminder.get_reminder(reminder_id)
    await show_mileage_tracking_detail_menu(callback.message, user_id, reminder, bot, callback_id=callback.id)


@router.callback_query(F.data.startswith("set_current_date:"))
async def set_current_date_for_tracking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    reminder_id = int(callback.data.split(":")[1])
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    await Reminder.update_reminder_details(reminder_id, {"last_reset_date": current_date_str})

    if await state.get_state() is not None:
        await state.clear()

    reminder = await Reminder.get_reminder(reminder_id)
    await show_time_tracking_detail_menu(callback.message, reminder, bot, callback_id=callback.id)


@router.callback_query(F.data.startswith("toggle_repeat_tracking:"))
async def toggle_repeat_tracking(callback: CallbackQuery, bot: Bot):
    """Handles toggling the 'Повторять' button state."""
    reminder_id = int(callback.data.split(":")[1])
    new_state_is_repeating = await Reminder.toggle_reminder_repeat(reminder_id)

    if new_state_is_repeating:
        await callback.answer(get_text('reminders_flow.repeat_on'), show_alert=False)
    else:
        await callback.answer(get_text('reminders_flow.repeat_off'), show_alert=False)

    reminder = await Reminder.get_reminder(reminder_id)
    if reminder:
        await show_time_tracking_detail_menu(callback.message, reminder, bot)
    else:
        await show_main_menu(callback.message, callback.from_user.id, edit=True)


@router.callback_query(F.data.startswith("delete_reminder:"))
async def delete_reminder_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    reminder_id = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} is deleting reminder {reminder_id}.")
    await Reminder.delete_reminder(reminder_id)
    await show_tracking_list_menu(callback)
    await callback.answer(get_text('reminders.deleted_success'), show_alert=True)

@router.callback_query(F.data.startswith("edit_reminder_target_mileage:"))
async def start_edit_target_mileage(callback: CallbackQuery, state: FSMContext):
    reminder_id = int(callback.data.split(":")[1])
    await state.update_data(reminder_id=reminder_id, prompt_message_id=callback.message.message_id)
    await state.set_state(ReminderFSM.edit_target_mileage)
    await callback.message.edit_text(
        get_text('reminders_flow.prompt_edit_target_mileage'),
        reply_markup=get_back_keyboard(f"edit_mileage_tracking:{reminder_id}")
    )


@router.message(ReminderFSM.edit_target_mileage)
async def process_edit_target_mileage(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.reply(get_text('errors.must_be_digit'))
        return
    await _process_fsm_edit(message, state, bot, {"target_mileage": int(message.text)})

@router.callback_query(F.data.startswith("time_notify_stop:"))
async def process_time_notify_stop(callback: CallbackQuery):
    """
    Handles the 'Не напоминать' button by clearing the notification schedule.
    """
    reminder_id = int(callback.data.split(":")[1])
    logger.info(f"User {callback.from_user.id} chose to stop notifications for reminder {reminder_id}.")
    await Reminder.update_reminder_details(reminder_id, {"notification_schedule": ""})
    edited_message = await callback.message.edit_text("Хорошо, больше не буду напоминать об этом событии.", reply_markup=None)
    await callback.answer()

    await asyncio.sleep(5)
    try:
        await edited_message.delete()
    except TelegramBadRequest:
        logger.warning(f"Could not delete temporary confirmation message for user {callback.from_user.id}.")


@router.callback_query(F.data.startswith("time_notify_ack:"))
async def process_time_notify_ack(callback: CallbackQuery):
    """
    Handles the 'Спасибо!' button by acknowledging the current notification.
    """
    _, reminder_id_str, day_to_remove_str = callback.data.split(":")
    reminder_id = int(reminder_id_str)
    day_to_remove = int(day_to_remove_str)
    logger.info(f"User {callback.from_user.id} acknowledged notification for reminder {reminder_id} ({day_to_remove} days).")

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder or not reminder['notification_schedule']:
        edited_message = await callback.message.edit_text("Это напоминание уже неактуально.", reply_markup=None)
        await callback.answer()
    else:
        schedule_list = reminder['notification_schedule'].split(',')
        if str(day_to_remove) in schedule_list:
            schedule_list.remove(str(day_to_remove))

        new_schedule = ",".join(schedule_list)
        await Reminder.update_reminder_details(reminder_id, {"notification_schedule": new_schedule})

        edited_message = await callback.message.edit_text("Понял, спасибо! Напомню в следующий раз.", reply_markup=None)
        await callback.answer()

    await asyncio.sleep(5)
    try:
        await edited_message.delete()
    except TelegramBadRequest:
        logger.warning(f"Could not delete temporary confirmation message for user {callback.from_user.id}.")


@router.callback_query(F.data.startswith("restart_reminder:"))
async def restart_reminder_from_main_menu(callback: CallbackQuery, bot: Bot):
    """
    Handles the 'Запустить заново' button from the main menu for an expired reminder.
    """
    reminder_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    logger.info(f"User {user_id} restarting reminder {reminder_id} from main menu.")

    reminder = await Reminder.get_reminder(reminder_id)
    if not reminder:
        await callback.answer(get_text('reminders.not_found'), show_alert=True)
        return

    if reminder['type'] in ('mileage_interval', 'exact_mileage'):
        car = await Car.get_active_car(user_id)
        if car and car['mileage'] is not None:
            await Reminder.reset_mileage_reminder(reminder_id, car['mileage'])
            await callback.answer("Отсчёт по пробегу сброшен!", show_alert=False)
        else:
            await callback.answer(get_text('errors.mileage_not_set_error'), show_alert=True)
            return

    elif reminder['type'] == 'time':
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        await Reminder.reset_time_reminder(reminder_id, current_date_str)
        await callback.answer("Отсчёт по времени запущен заново!", show_alert=False)

    # Refresh the main menu to show the updated state
    await show_main_menu(callback.message, user_id, edit=True)