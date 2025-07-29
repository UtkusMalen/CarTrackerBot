import asyncio

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from bot.database.models import User, Car
from bot.fsm.profile import ProfileFSM
from bot.handlers import notes_handlers
from bot.keyboards.inline import get_start_keyboard, get_profile_keyboard, get_back_keyboard
from bot.presentation.menus import show_main_menu
from bot.utils.text_manager import get_text
from bot.utils.commands import set_user_commands

router = Router()

@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext, bot: Bot):
    """
    Handles the /start command.
    If user has cars, shows main menu. Otherwise, shows welcome message.
    """
    await state.clear()
    user_id = message.from_user.id

    await set_user_commands(bot, user_id)

    await User.create_user(user_id, message.from_user.username, message.from_user.first_name)

    active_car = await Car.get_active_car(user_id)

    if active_car:
        await show_main_menu(message, user_id, edit=False)
    else:
        await message.answer(get_text('start_command.welcome'), reply_markup=get_start_keyboard())

@router.callback_query(F.data == "my_profile")
async def show_profile_from_callback(callback: CallbackQuery, state: FSMContext):
    """
    This handler is ONLY for the callback button. It calls the generic display function.
    """
    await show_profile(callback, state)

async def show_profile(event: Message | CallbackQuery, state: FSMContext):
    """
    Generic function to display the user profile.
    It handles being called from either a Message or a CallbackQuery.
    """
    await state.clear()
    user = await User.get_user(event.from_user.id)
    if not user:
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(get_text('profile.profile_not_loaded'))
            await event.answer()
        else:
            await event.answer(get_text('profile.profile_not_loaded'))
        return

    profile_text = (
        f"{get_text('profile.header')}\n\n"
        f"{get_text('profile.balance', balance=user[3])}"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            profile_text,
            reply_markup=get_profile_keyboard()
        )
        await event.answer()
    else:
        await event.answer(
            profile_text,
            reply_markup=get_profile_keyboard()
        )


@router.callback_query(F.data == "my_cars")
async def show_car_list(callback: CallbackQuery):
    """Shows the list of user's cars for selection."""
    user_id = callback.from_user.id
    all_cars = await Car.get_all_cars_for_user(user_id)

    text: str
    car_buttons = []

    if not all_cars:
        text = get_text('profile.no_cars_yet')
    else:
        text = get_text('profile.select_active_car')
        active_car_id = await User.get_active_car_id(user_id)
        for car_id, name, mileage in all_cars:
            prefix = "✅ " if car_id == active_car_id else ""
            car_buttons.append([InlineKeyboardButton(
                text=f"{prefix}{name}",
                callback_data=f"select_car:{car_id}"
            )])

    car_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_profile")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=car_buttons)

    await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_car:"))
async def select_car(callback: CallbackQuery, state: FSMContext):
    """Handles the selection of an active car from the profile menu."""
    await state.clear()
    car_id = int(callback.data.split(":")[1])
    await User.set_active_car(callback.from_user.id, car_id)
    await show_main_menu(callback.message, callback.from_user.id, edit=True)
    await callback.answer(get_text('profile.active_car_changed'))

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Handles the "Back to main menu" button."""
    await state.clear()
    user_id = callback.from_user.id
    active_car = await Car.get_active_car(user_id)

    if active_car:
        await show_main_menu(callback.message, user_id, edit=True)
    else:
        await callback.message.edit_text(
            get_text('start_command.welcome'),
            reply_markup=get_start_keyboard()
        )
    await callback.answer(get_text('general.action_canceled'))

@router.callback_query(F.data == "notes")
async def notes_menu(callback: CallbackQuery):
    car = await Car.get_active_car(callback.from_user.id)
    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return
    await notes_handlers.show_notes(callback.message, callback.from_user.id)
    await callback.answer()

@router.callback_query(F.data == "change_reminder_period")
async def start_reminder_period_update(callback: CallbackQuery, state: FSMContext):
    """Starts the FSM for updating the reminder period."""
    await state.set_state(ProfileFSM.set_reminder_period)

    user_data = await User.get_user(callback.from_user.id)
    current_period = user_data[5] if user_data else 1

    prompt_text = get_text('profile.prompt_reminder_period', current_period=current_period)

    msg = await callback.message.edit_text(
        prompt_text,
        reply_markup=get_back_keyboard("my_profile")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(ProfileFSM.set_reminder_period)
async def process_reminder_period_update(message: Message, state: FSMContext, bot: Bot):
    """Processes the new period, saves it, and confirms to the user"""
    if not message.text.isdigit() or int(message.text) < 1:
        error_msg = await message.reply("Пожалуйста, введите целое положительное число.")
        await asyncio.sleep(5)
        await message.delete()
        await error_msg.delete()
        return

    days = int(message.text)
    user_id = message.from_user.id

    await User.set_mileage_reminder_period(user_id, days)

    confirmation_msg = await message.answer(
        get_text('profile.reminder_period_updated', days=days)
    )

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')

    await state.clear()
    await message.delete()

    if prompt_message_id:
        user_data = await User.get_user(user_id)
        balance = user_data[3] if user_data else 0
        profile_text = (
            f"{get_text('profile.header')}\n\n"
            f"{get_text('profile.balance', balance=balance)}"
        )

        try:
            await bot.edit_message_text(
                text=profile_text,
                chat_id=message.chat.id,
                message_id=prompt_message_id,
                reply_markup=get_profile_keyboard()
            )
        except TelegramBadRequest as e:
            logger.error(f"Failed to edit message into profile menu: {e}")
            await message.answer(profile_text, reply_markup=get_profile_keyboard())
    else:
        await show_profile(message, state)

    await asyncio.sleep(5)
    try:
        await confirmation_msg.delete()
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete temporary confirmation message: {e}")
