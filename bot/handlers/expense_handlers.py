import asyncio
import math
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from bot.database.models import Car, Expense, ExpenseCategory
from bot.fsm.expense import ExpenseFSM
from bot.keyboards.inline import get_expense_category_keyboard, get_expense_mileage_keyboard, \
    get_expense_skip_keyboard, get_expense_date_keyboard, get_back_keyboard, get_detailed_expenses_log_keyboard, \
    get_expenses_summary_keyboard, get_delete_expense_keyboard
from bot.presentation.menus import show_main_menu
from bot.utils.text_manager import get_text

router = Router()

EXPENSES_PER_PAGE = 8

async def _finish_expense_tracking(chat_id: int, user_id: int, state: FSMContext, bot: Bot):
    """
    A helper to save the expense, clean up messages, and show the main menu.
    """
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    car = await Car.get_active_car(user_id)
    await state.clear()

    if not car:
        return

    expense_mileage = data.get("mileage")
    if expense_mileage and car['mileage'] is not None:
        if expense_mileage > car['mileage']:
            await Car.update_mileage(car['car_id'], expense_mileage)
            logger.info(f"Car mileage for car_id {car['car_id']} updated to {expense_mileage} via expense entry.")

    await Expense.add_expense(
        car_id=car['car_id'],
        category_id=data.get("category_id"),
        amount=data.get("amount"),
        mileage=data.get("mileage"),
        description=data.get("description"),
        date=data.get("date")
    )

    if prompt_message_id:
        try:
            # Clean up the prompt message
            await bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
        except TelegramBadRequest:
            pass  # Message might have been deleted already

    desc = data.get("description")
    if desc:
        success_text = get_text('expense.success', description=desc, amount=data.get("amount"))
    else:
        success_text = get_text('expense.success_no_desc', amount=data.get("amount"))

    conf_msg = await bot.send_message(chat_id, success_text)
    # Show the main menu
    await show_main_menu(conf_msg, user_id, edit=False)
    # Delete the temporary confirmation after a few seconds
    await asyncio.sleep(4)
    await conf_msg.delete()


@router.callback_query(F.data == "add_expense")
async def start_expense_tracking(callback: CallbackQuery, state: FSMContext):
    """Starts the expense tracking flow by asking for the category."""
    user_id = callback.from_user.id
    await state.clear()
    categories = await ExpenseCategory.get_categories_for_user(user_id)
    msg = await callback.message.edit_text(
        get_text('expense.prompt_category'),
        reply_markup=get_expense_category_keyboard(categories)
    )
    await state.set_state(ExpenseFSM.get_category)
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(ExpenseFSM.get_category, F.text)
async def process_fast_expense_entry(message: Message, state: FSMContext, bot: Bot):
    """Handles the combined format for adding an expense"""
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        await message.delete()
        msg = await message.answer(get_text('expense.invalid_fast_format'))
        await asyncio.sleep(5)
        await msg.delete()
        return

    category_name = parts[0]
    category = await ExpenseCategory.find_category_by_name(user_id, category_name)
    if not category:
        await message.delete()
        msg = await message.answer(f"Категория '{category_name}' не найдена. Проверьте название.")
        await asyncio.sleep(5)
        await msg.delete()
        return

    try:
        amount = float(parts[1])
        if amount <= 0:
            await message.delete()
            msg = await message.answer(get_text('expense.error_amount_must_be_positive'))
            await asyncio.sleep(5)
            await msg.delete()
            return
        mileage = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

        description_start_index = 3 if mileage is not None else 2
        description = " ".join(parts[description_start_index:]) if len(parts) > description_start_index else f"Расход: {category_name}"

        await state.update_data(
            category_id=category['category_id'],
            amount=amount,
            mileage=mileage,
            description=description,
            date=datetime.now().strftime('%Y-%m-%d')
        )
        await _finish_expense_tracking(message.chat.id, user_id, state, bot)
        await message.delete()

    except (ValueError, IndexError):
        await message.delete()
        msg =await message.answer(get_text('expense.invalid_fast_format'))
        await asyncio.sleep(5)
        await msg.delete()
        return

@router.callback_query(F.data.startswith("set_exp_cat:"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Process category selection via button and asks for amount."""
    _, category_id, category_name = callback.data.split(":", 2)
    await state.update_data(category_id=int(category_id), category_name=category_name)
    await state.set_state(ExpenseFSM.get_amount)

    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    await bot.edit_message_text(
        get_text('expense.prompt_amount'),
        chat_id=callback.message.chat.id,
        message_id=prompt_message_id,
        reply_markup=get_back_keyboard("add_expense")
    )
    await callback.answer()

@router.message(ExpenseFSM.get_amount)
async def process_expense_amount(message: Message, state: FSMContext, bot: Bot):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.delete()
            msg = await message.answer(get_text('expense.error_amount_must_be_positive'))
            await asyncio.sleep(5)
            await msg.delete()
            return
    except ValueError:
        await message.delete()
        msg = await message.answer(get_text('errors.must_be_digit'))
        await asyncio.sleep(5)
        await msg.delete()
        return

    await state.update_data(amount=float(message.text))
    await state.set_state(ExpenseFSM.get_mileage)

    car = await Car.get_active_car(message.from_user.id)
    current_mileage = car['mileage'] if car and car['mileage'] else 0

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    await bot.edit_message_text(
        get_text('expense.prompt_mileage'),
        chat_id=message.chat.id,
        message_id=prompt_message_id,
        reply_markup=get_expense_mileage_keyboard(current_mileage)
    )

@router.callback_query(F.data.startswith("use_current_exp_mileage:"), ExpenseFSM.get_mileage)
async def process_expense_mileage_current(callback: CallbackQuery, state: FSMContext, bot: Bot):
    mileage = int(callback.data.split(":")[1])
    await state.update_data(mileage=mileage)
    await state.set_state(ExpenseFSM.get_description)

    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await bot.edit_message_text(
        get_text('expense.prompt_description'),
        chat_id=callback.message.chat.id,
        message_id=prompt_message_id,
        reply_markup=get_expense_skip_keyboard("add_expense")
    )


@router.message(ExpenseFSM.get_mileage)
async def process_expense_mileage_text(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.delete()
        msg = await message.answer(get_text('errors.must_be_digit'))
        await asyncio.sleep(5)
        await msg.delete()
        return
    await state.update_data(mileage=int(message.text))
    await state.set_state(ExpenseFSM.get_description)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    await bot.edit_message_text(
        get_text('expense.prompt_description'),
        chat_id=message.chat.id,
        message_id=prompt_message_id,
        reply_markup=get_expense_skip_keyboard("add_expense")
    )


# Handlers for description
@router.message(ExpenseFSM.get_description)
async def process_expense_description(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(description=message.text)
    await state.set_state(ExpenseFSM.get_date)
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await message.delete()
    await bot.edit_message_text(
        get_text('expense.prompt_date'),
        chat_id=message.chat.id,
        message_id=prompt_message_id,
        reply_markup=get_expense_date_keyboard()
    )


# Handlers for date
@router.callback_query(F.data.startswith("use_current_exp_date:"), ExpenseFSM.get_date)
async def process_expense_date_current(callback: CallbackQuery, state: FSMContext, bot: Bot):
    date = callback.data.split(":")[1]
    await state.update_data(date=date)
    await _finish_expense_tracking(callback.message.chat.id, callback.from_user.id, state, bot)


@router.message(ExpenseFSM.get_date)
async def process_expense_date_text(message: Message, state: FSMContext, bot: Bot):
    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        date_str = date_obj.strftime("%Y-%m-%d")
        await state.update_data(date=date_str)
        await message.delete()
        await _finish_expense_tracking(message.chat.id, message.from_user.id, state, bot)
    except ValueError:
        msg = await message.answer(get_text('errors.invalid_date_format'))
        await asyncio.sleep(4)
        await msg.delete()
        await message.delete()


# Handler for skipping steps
@router.callback_query(F.data == "skip_expense_step")
async def skip_expense_step(callback: CallbackQuery, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    next_state = None
    prompt_text = ""
    keyboard = None

    if current_state == ExpenseFSM.get_mileage.state:
        await state.update_data(mileage=None)
        next_state = ExpenseFSM.get_description
        prompt_text = get_text('expense.prompt_description')
        keyboard = get_expense_skip_keyboard("add_expense")
    elif current_state == ExpenseFSM.get_description.state:
        data = await state.get_data()
        await state.update_data(description=data.get("category_name", "Расход"))
        next_state = ExpenseFSM.get_date
        prompt_text = get_text('expense.prompt_date')
        keyboard = get_expense_date_keyboard()

    if next_state:
        await state.set_state(next_state)
        data = await state.get_data()
        prompt_message_id = data.get("prompt_message_id")
        await bot.edit_message_text(prompt_text, chat_id=callback.message.chat.id, message_id=prompt_message_id,
                                    reply_markup=keyboard)


# Handlers for creating a new category
@router.callback_query(F.data == "create_exp_cat")
async def create_category_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ExpenseFSM.create_category_name)
    await callback.message.edit_text(
        get_text('expense.prompt_create_category'),
        reply_markup=get_back_keyboard("add_expense")
    )


@router.message(ExpenseFSM.create_category_name)
async def create_category_process(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    category_name = message.text

    existing = await ExpenseCategory.find_category_by_name(user_id, category_name)
    if existing:
        await message.delete()
        msg =await message.answer(get_text('expense.category_exists'))
        await asyncio.sleep(5)
        await msg.delete()
        return

    await ExpenseCategory.add_category(user_id, category_name)

    # Get prompt_message_id BEFORE clearing the state
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    # After creating, go back to the category selection
    await state.clear()
    categories = await ExpenseCategory.get_categories_for_user(user_id)
    await message.delete()
    if prompt_message_id:
        await bot.edit_message_text(
            get_text('expense.prompt_category'),
            chat_id=message.chat.id,
            message_id=prompt_message_id,
            reply_markup=get_expense_category_keyboard(categories)
        )


async def show_detailed_log(message: Message, user_id: int, page: int = 1, edit: bool = True):
    car = await Car.get_active_car(user_id)
    if not car:
        return

    total_expenses = await Expense.get_total_expenses_count_for_car(car['car_id'])
    total_pages = math.ceil(total_expenses / EXPENSES_PER_PAGE) if total_expenses > 0 else 1
    page = max(1, min(page, total_pages))

    expenses = await Expense.get_expenses_for_car_paginated(car['car_id'], page, EXPENSES_PER_PAGE)

    text_lines = [get_text('my_expenses.detailed_log_header', car_name=car['name'])]
    if not expenses:
        text_lines.append(get_text('my_expenses.no_expenses_log'))
    else:
        for exp in expenses:
            date_str = datetime.strptime(exp['created_at'], '%Y-%m-%d').strftime('%d.%m.%y')
            desc_line = f"{exp['description']}\n" if exp['description'] else ""

            if exp['mileage']:
                line = get_text('my_expenses.detailed_log_entry_with_mileage', date=date_str,
                                category_name=exp['category_name'], mileage=exp['mileage'], description_line=desc_line,
                                amount=exp['amount'])
            else:
                line = get_text('my_expenses.detailed_log_entry', date=date_str, category_name=exp['category_name'],
                                description_line=desc_line, amount=exp['amount'])
            text_lines.append(line)

    text = "\n\n".join(text_lines)
    keyboard = get_detailed_expenses_log_keyboard(page, total_pages)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


# --- Summary Menu ---
@router.callback_query(F.data == "my_expenses")
async def show_expenses_summary(callback: CallbackQuery):
    user_id = callback.from_user.id
    car = await Car.get_active_car(user_id)
    if not car:
        await callback.answer(get_text('main_menu.add_car_first'), show_alert=True)
        return

    summary = await Expense.get_expense_summary_for_car(car['car_id'])

    text_lines = [get_text('my_expenses.summary_header', car_name=car['name'])]

    # Category summary
    text_lines.append(get_text('my_expenses.category_summary_header'))
    if summary['by_category']:
        for cat, total in summary['by_category'].items():
            text_lines.append(get_text('my_expenses.category_line', category_name=cat, total=total))
    else:
        text_lines.append(get_text('my_expenses.no_category_expenses'))
    text_lines.append(get_text('my_expenses.fuel_line', total=summary['fuel_total']))

    # Time period summary
    text_lines.append(get_text('my_expenses.time_period_header'))
    text_lines.append(get_text('my_expenses.this_month', total=summary['this_month']))
    text_lines.append(get_text('my_expenses.last_month', total=summary['last_month']))
    text_lines.append(get_text('my_expenses.this_year', total=summary['this_year']))
    text_lines.append(get_text('my_expenses.last_year', total=summary['last_year']))

    text = "\n".join(text_lines)
    keyboard = get_expenses_summary_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# --- Detailed Log Callbacks ---
@router.callback_query(F.data.in_({"detailed_expense_log", "detailed_expense_log_page:1"}))
async def detailed_log_start(callback: CallbackQuery):
    await show_detailed_log(callback.message, callback.from_user.id, page=1, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("expense_page:"))
async def detailed_log_paginate(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_detailed_log(callback.message, callback.from_user.id, page=page, edit=True)
    await callback.answer()


# --- Deletion Flow ---
@router.callback_query(F.data.startswith("delete_expense_start:"))
async def delete_expense_start(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    car = await Car.get_active_car(callback.from_user.id)
    expenses = await Expense.get_expenses_for_car_paginated(car['car_id'], page, EXPENSES_PER_PAGE)

    await callback.message.edit_text(
        get_text('my_expenses.delete_prompt'),
        reply_markup=get_delete_expense_keyboard(expenses, page)
    )


@router.callback_query(F.data.startswith("delete_expense_confirm:"))
async def delete_expense_confirm(callback: CallbackQuery):
    _, expense_id, page = callback.data.split(":")
    await Expense.delete_expense(int(expense_id))
    await callback.answer(get_text('my_expenses.expense_deleted_success'), show_alert=True)
    await show_detailed_log(callback.message, callback.from_user.id, page=int(page), edit=True)