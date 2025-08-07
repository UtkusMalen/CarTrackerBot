import asyncio
import math
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.config import config
from bot.database.models import User, Car, Transaction, Reminder
from bot.fsm.profile import ProfileFSM
from bot.handlers import notes_handlers
from bot.keyboards.inline import get_start_keyboard, get_profile_keyboard, get_back_keyboard, get_delete_car_keyboard, \
    get_to_main_menu_keyboard, get_detailed_rating_keyboard, get_transaction_history_keyboard, \
    get_garage_keyboard
from bot.presentation.menus import show_main_menu
from bot.utils.commands import set_user_commands
from bot.utils.text_manager import get_text

router = Router()
RATING_PAGE_SIZE = 10
TOP_USERS_LIMIT = 100
TRANSACTION_PAGE_SIZE = 10

@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext, bot: Bot, command: CommandObject):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    user_exists = await User.get_user(user_id)
    is_new_user = not user_exists

    logger.info(f"User {user_id} ({username}) initiated /start. Referrer: {command.args}. New user: {is_new_user}")

    referrer_id = None
    promo_code = None

    if command.args:
        # Case 1: The argument is a numeric user ID
        if command.args.isdigit():
            ref_id = int(command.args)
            # A user cannot refer themselves
            if ref_id != user_id:
                referrer_id = ref_id
                logger.info(f"User {user_id} ({username}) initiated /start. Referrer user: {referrer_id}. New user: {is_new_user}")
        # Case 2: The argument is a non-numeric promo code
        else:
            promo_code = command.args
            logger.info(f"User {user_id} ({username}) initiated /start via promo code: '{promo_code}'. New user: {is_new_user}")
    else:
        logger.info(f"User {user_id} ({username}) initiated /start without a referrer. New user: {is_new_user}")

    await User.create_user(user_id, username, first_name, referrer_id=referrer_id, referral_code=promo_code)
    await set_user_commands(bot, user_id)

    if is_new_user and referrer_id:
        amount = config.rewards.referral_bonus
        description = "Приглашение друга"

        await Transaction.add_transaction(referrer_id, amount, description)
        logger.success(f"User {referrer_id} received {amount} nuts for referring new user {user_id}")

        try:
            friend_details = first_name
            if username:
                friend_details += f" (@{username})"
            friend_details += f" (ID: {user_id})"

            await bot.send_message(
                referrer_id,
                get_text('rating_menu.friend_joined_notification', friend_details=friend_details, amount=amount),
                reply_markup=get_to_main_menu_keyboard()
            )
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"Could not notify referrer {referrer_id}: {e}")

    active_car = await Car.get_active_car(user_id)
    if active_car:
        await show_main_menu(message, user_id, edit=False)
    else:
        await message.answer(get_text('start_command.welcome'), reply_markup=get_start_keyboard())

@router.callback_query(F.data == "my_profile")
async def show_profile_from_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    logger.info(f"User {callback.from_user.id} requested to see profile.")
    await show_profile(callback.message, user_id=callback.from_user.id, edit=True)
    await callback.answer()

async def show_profile(message: Message, user_id: int, edit: bool):
    user_data_task = User.get_user(user_id)
    user_cars_task = Car.get_all_cars_for_user(user_id)
    user_rank_task = User.get_user_rank(user_id)
    total_users_task = User.get_total_users_count()

    user_data, user_cars, user_rank, total_users = await asyncio.gather(
        user_data_task, user_cars_task, user_rank_task, total_users_task
    )

    if not user_data:
        logger.error(f"Could not load profile for user {user_id}.")
        error_text = get_text('profile.profile_not_loaded')
        if edit:
            await message.edit_text(error_text)
        else:
            await message.answer(error_text)
        return

    user_balance = user_data[3]

    garage_lines = [get_text('profile.garage_header')]
    for i, car in enumerate(user_cars):
        garage_lines.append(get_text('profile.garage_car_line', index=i + 1, name=car[2], mileage=car[3]))

    add_car_text = get_text('profile.garage_add_car_paid', index=len(user_cars) + 1, cost=config.costs.add_car_slot)
    garage_lines.append(add_car_text)

    garage_section = "\n".join(garage_lines)

    rating_lines = [get_text('profile.rating_header')]
    rating_lines.append(get_text('profile.rating_rank_line', rank=user_rank, total_users=total_users))

    if user_rank > 1:
        next_user_balance = await User.get_user_balance_by_rank(user_rank)
        if next_user_balance is not None:
            diff = (next_user_balance - user_balance) + 1
            rating_lines.append(get_text('profile.rating_overtake_line', diff=max(0, diff)))
    else:
        rating_lines.append(get_text('profile.rating_no_one_above'))

    rating_section = "\n".join(rating_lines)

    referral_section = (
        f"{get_text('profile.referral_header')}\n"
        f"{get_text('profile.referral_invite_line', amount=config.rewards.referral_bonus)}"
    )

    full_text = "\n".join([
        get_text('profile.header'),
        get_text('profile.balance', balance=user_balance),
        garage_section,
        rating_section,
        referral_section
    ])

    keyboard = get_profile_keyboard()

    if edit:
        try:
            await message.edit_text(full_text, reply_markup=keyboard)
        except TelegramBadRequest:
            await message.answer(full_text, reply_markup=keyboard)
    else:
        await message.answer(full_text, reply_markup=keyboard)


@router.callback_query(F.data == "my_garage")
async def show_garage(callback: CallbackQuery):
    """Shows the list of user's cars for selection."""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} requested their car list.")

    all_cars = await Car.get_all_cars_for_user(user_id)

    if not all_cars:
        text = f"{get_text('profile.garage.header')}\n\n{get_text('profile.garage.no_cars')}"
        keyboard = get_garage_keyboard(cars=[])
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        return

    active_car_id = await User.get_active_car_id(user_id)
    car_text_lines = []

    for i, car_row in enumerate(all_cars):
        reminders_count = len(await Reminder.get_reminders_for_car(car_row['car_id']))

        insurance_start_date_str = car_row['insurance_start_date']
        insurance_duration_days = car_row['insurance_duration_days']


        if insurance_start_date_str and insurance_duration_days:
            start_date = datetime.strptime(insurance_start_date_str, "%Y-%m-%d").date()
            end_date = start_date + timedelta(insurance_duration_days)
            remaining_days = (end_date - datetime.now().date()).days

            if remaining_days > 0:
                days_value = get_text('insurance.policy_days_left', days=remaining_days)
                insurance_status = f"{days_value} дней"
            else:
                insurance_status = get_text('insurance.policy_expired')
        else:
            insurance_status = get_text('insurance.policy_not_set')

        active_indicator = get_text('profile.garage.active_car_indicator') if car_row['car_id'] == active_car_id else ""

        car_text_lines.append(
            get_text('profile.garage.car_line',
                     index=i + 1,
                     name=f"{active_indicator}{car_row['name']}",
                     mileage=car_row['mileage'],
                     reminders_count=reminders_count,
                     insurance_status=insurance_status)
        )

    car_list_string = "\n".join(car_text_lines)
    next_item_index = len(all_cars) + 1

    add_car_prompt = get_text('profile.garage.add_another_car_prompt', index=next_item_index, cost=config.costs.add_car_slot)

    full_text = (
        f"{get_text('profile.garage.header')}\n\n"
        f"{car_list_string}\n"
        f"{add_car_prompt}"
    )

    keyboard = get_garage_keyboard(all_cars)

    await callback.message.edit_text(text=full_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_car:"))
async def select_car(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    car_id = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} selected car {car_id} as active.")
    await User.set_active_car(user_id, car_id)
    await show_main_menu(callback.message, user_id, edit=True)
    await callback.answer(get_text('profile.active_changed'))

@router.callback_query(F.data == "delete_car_start")
async def delete_car_start(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} initiated car deletion process.")

    all_cars = await Car.get_all_cars_for_user(user_id)

    if not all_cars:
        await callback.answer("У вас нет автомобилей для удаления.", show_alert=True)
        return

    await callback.message.edit_text(
        "Какой автомобиль вы хотите удалить? \n\n⚠️ <b>Внимание:</b> Это действие необратимо и удалит все связанные с автомобилем данные (напоминания, заметки).",
        reply_markup=get_delete_car_keyboard(all_cars)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_car_confirm:"))
async def delete_car_process(callback: CallbackQuery):
    user_id = callback.from_user.id
    car_id = int(callback.data.split(":")[1])
    logger.info(f"User {user_id} confirmed deletion of car {car_id}.")

    await Car.delete_car(car_id)
    await callback.answer("Автомобиль успешно удален.", show_alert=True)

    # After deleting, refresh the car list view
    await show_garage(callback)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    logger.info(f"User {user_id} clicked 'back to main menu'.")
    active_car = await Car.get_active_car(user_id)

    if active_car:
        await show_main_menu(callback.message, user_id, edit=True)
    else:
        await callback.message.edit_text(
            get_text('start_command.welcome'),
            reply_markup=get_start_keyboard()
        )
    await callback.answer(get_text('general.action_canceled'))

async def _display_detailed_rating_page(callback: CallbackQuery, page: int):
    logger.info(f"User {callback.from_user.id} is viewing detailed rating page {page}.")

    total_pages = math.ceil(TOP_USERS_LIMIT / RATING_PAGE_SIZE)
    page = max(1, min(page, total_pages))

    top_users = await User.get_top_users_paginated(page, RATING_PAGE_SIZE)

    header = get_text('rating_menu.detailed_rating.header')

    if not top_users:
        await callback.message.edit_text(f"{header}\n\nПользователей пока нет.",reply_markup=get_detailed_rating_keyboard(page, total_pages))
        return

    rating_lines = []
    current_user_id = callback.from_user.id

    for i, user_data in enumerate(top_users):
        user_id, first_name, username, balance = user_data
        rank = (page - 1) * RATING_PAGE_SIZE + i + 1
        name = first_name or username or "Аноним"

        if user_id == current_user_id:
            line_template = 'rating_menu.detailed_rating.user_line_highlight'
        else:
            line_template = 'rating_menu.detailed_rating.user_line'

        rating_lines.append(get_text(line_template, rank=rank, name=name, balance=balance))

        page_footer = get_text('rating_menu.detailed_rating.page_footer', page=page, total_pages=total_pages)
        full_text = f"{header}\n\n" + "\n".join(rating_lines) + page_footer

        await callback.message.edit_text(
            text=full_text,
            reply_markup=get_detailed_rating_keyboard(page, total_pages)
        )

@router.callback_query(F.data == "rating_details")
async def show_detailed_rating_menu(callback: CallbackQuery):
    """Shows the first page of the detailed rating."""
    await _display_detailed_rating_page(callback, page=1)
    await callback.answer()


@router.callback_query(F.data.startswith("rating_page:"))
async def paginate_detailed_rating(callback: CallbackQuery):
    """Handles pagination for the detailed rating view."""
    page = int(callback.data.split(":")[1])
    await _display_detailed_rating_page(callback, page)
    await callback.answer()

@router.callback_query(F.data == "invite_friend")
async def invite_friend(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} requested referral link.")
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    amount = config.rewards.referral_bonus

    text = get_text('rating_menu.invite_friend_text', amount=amount, link=ref_link)

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("my_profile")
    )
    await callback.answer()

@router.callback_query(F.data == "notes")
async def notes_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} opened notes menu.")
    car = await Car.get_active_car(user_id)
    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return
    # Start on page 1
    await notes_handlers.show_notes(callback.message, user_id, page=1)
    await callback.answer()

@router.callback_query(F.data == "change_reminder_period")
async def start_reminder_period_update(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started updating reminder period.")
    await state.set_state(ProfileFSM.set_reminder_period)
    user_data = await User.get_user(user_id)
    current_period = user_data[5] if user_data else 1
    prompt_text = get_text('profile.prompt_reminder_period', current_period=current_period)
    msg = await callback.message.edit_text(prompt_text, reply_markup=get_back_keyboard("my_profile"))
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(ProfileFSM.set_reminder_period)
async def process_reminder_period_update(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} (State: set_reminder_period) sent new period: '{message.text}'.")
    if not message.text.isdigit() or int(message.text) < 1:
        logger.warning(f"User {user_id} entered invalid reminder period: '{message.text}'.")
        error_msg = await message.reply("Пожалуйста, введите целое положительное число.")
        await asyncio.sleep(5)
        await message.delete()
        await error_msg.delete()
        return

    days = int(message.text)
    await User.set_mileage_reminder_period(user_id, days)
    logger.success(f"User {user_id} updated reminder period to {days} days.")
    confirmation_msg = await message.answer(get_text('profile.reminder_period_updated', days=days))
    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await state.clear()
    await message.delete()

    if prompt_message_id:
        user_data = await User.get_user(user_id)
        balance = user_data[3] if user_data else 0
        profile_text = f"{get_text('profile.header')}\n\n{get_text('profile.balance', balance=balance)}"
        try:
            await bot.edit_message_text(text=profile_text, chat_id=message.chat.id, message_id=prompt_message_id, reply_markup=get_profile_keyboard())
        except TelegramBadRequest as e:
            logger.error(f"Failed to edit message into profile menu for {user_id}: {e}")
            await message.answer(profile_text, reply_markup=get_profile_keyboard())
    else:
        await show_profile(message, user_id, edit=False)

    await asyncio.sleep(5)
    try:
        await confirmation_msg.delete()
    except TelegramBadRequest as e:
        logger.warning(f"Could not delete temporary confirmation message for user {user_id}: {e}")


async def _display_transaction_history_page(callback: CallbackQuery, page: int):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} is viewing transaction history page {page}.")

    total_transactions = await Transaction.get_transactions_count(user_id)

    if total_transactions == 0:
        await callback.message.edit_text(
            f"{get_text('rating_menu.transaction_history.header')}\n\n{get_text('rating_menu.transaction_history.no_history')}",
            reply_markup=get_transaction_history_keyboard(1, 1)
        )
        return

    total_pages = math.ceil(total_transactions / TRANSACTION_PAGE_SIZE)
    page = max(1, min(page, total_pages))

    transactions = await Transaction.get_transactions_paginated(user_id, page, TRANSACTION_PAGE_SIZE)

    header = get_text('rating_menu.transaction_history.header')

    transaction_lines = []
    for amount, description, created_at in transactions:
        date_str = created_at.split(" ")[0]

        if amount > 0:
            formatted_amount = f"+{amount}"
        else:
            formatted_amount = str(amount)
        transaction_lines.append(
            get_text(
                'rating_menu.transaction_history.transaction_line',
                date=date_str,
                description=description,
                amount=formatted_amount
            )
        )

    page_footer = get_text('rating_menu.transaction_history.page_footer', page=page, total_pages=total_pages)
    full_text = f"{header}\n\n" + "\n".join(transaction_lines) + page_footer

    await callback.message.edit_text(
        text=full_text,
        reply_markup=get_transaction_history_keyboard(page, total_pages)
    )


@router.callback_query(F.data == "transaction_history")
async def show_transaction_history(callback: CallbackQuery):
    """Shows the first page of the user's transaction history."""
    await _display_transaction_history_page(callback, page=1)
    await callback.answer()


@router.callback_query(F.data.startswith("trans_page:"))
async def paginate_transaction_history(callback: CallbackQuery):
    """Handles pagination for the transaction history view."""
    page = int(callback.data.split(":")[1])
    await _display_transaction_history_page(callback, page)
    await callback.answer()