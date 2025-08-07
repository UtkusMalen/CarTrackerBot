import asyncio
import math
import os
import re

from loguru import logger
from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from bot.config import config
from bot.fsm.admin import AdminFSM
from bot.database.models import User, Car, Transaction, Reminder
from bot.keyboards.inline import get_admin_panel_keyboard, get_mailing_confirmation_keyboard, get_back_keyboard, \
    get_referral_stats_keyboard
from bot.utils.db_exporter import create_db_dump_zip
from bot.utils.notifications import send_mileage_reminder, send_time_based_notification
from bot.utils.text_manager import get_text

router = Router()
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))

REF_STATS_PAGE_SIZE = 10

@router.message(Command("admin"))
async def show_admin_panel(message: Message, state: FSMContext):
    """Displays the admin panel."""
    logger.info(f"Admin {message.from_user.id} accessed admin panel.")
    await state.clear()
    await message.answer(
        get_text("admin.panel_header"),
        reply_markup=get_admin_panel_keyboard()
    )

@router.callback_query(F.data == "show_admin_panel")
async def show_admin_panel_callback(callback: CallbackQuery, state: FSMContext):
    """Callback to show the admin panel main menu from a button."""
    await state.clear()
    await callback.message.edit_text(
        get_text("admin.panel_header"), # You can use your own text here
        reply_markup=get_admin_panel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "create_mailing")
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    """Starts the process of creating a new broadcast message."""
    logger.info(f"Admin {callback.from_user.id} initiated a new mailing.")
    await state.set_state(AdminFSM.get_message)
    msg = await callback.message.edit_text(get_text("admin.mailing_prompt"), reply_markup=get_back_keyboard("show_admin_panel"))
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(AdminFSM.get_message)
async def get_mailing_message(message: Message, state: FSMContext, bot: Bot):
    """Receives the content for the broadcast"""
    logger.debug(f"Admin {message.from_user.id} provided content for the mailing.")
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    if prompt_message_id:
        try:
            await bot.delete_message(message.from_user.id, prompt_message_id)
        except TelegramBadRequest:
            logger.warning(f"Failed to delete prompt message {prompt_message_id} for admin {message.from_user.id}.")

    await message.delete()

    await state.update_data(
        text=message.html_text,
        photo_id=message.photo[-1].file_id if message.photo else None
    )
    await state.set_state(AdminFSM.confirm_mailing)

    logger.debug(f"Showing mailing preview to admin {message.from_user.id}.")
    await bot.send_message(message.from_user.id, get_text("admin.mailing_preview"))
    if message.photo:
        await bot.send_photo(
            chat_id=message.from_user.id,
            photo=message.photo[-1].file_id,
            caption=message.html_text
        )
    else:
        await bot.send_message(message.from_user.id, message.html_text)

    await bot.send_message(
        chat_id=message.from_user.id,
        text=get_text("admin.mailing_confirm_prompt"),
        reply_markup=get_mailing_confirmation_keyboard()
    )

@router.callback_query(F.data == "cancel_mailing", AdminFSM.confirm_mailing)
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    """Cancels the broadcast process."""
    logger.info(f"Admin {callback.from_user.id} cancelled the mailing.")
    await state.clear()
    await callback.message.edit_text(get_text("admin.mailing_cancelled"))
    await show_admin_panel(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "send_mailing", AdminFSM.confirm_mailing)
async def send_mailing(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirms and starts the broadcast process."""
    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} confirmed and started the mailing.")
    await callback.message.edit_text(get_text("admin.mailing_started"))
    await callback.answer()

    data = await state.get_data()
    text = data.get("text")
    photo_id = data.get("photo_id")
    await state.clear()

    all_users = await User.get_all_user_ids()
    logger.info(f"Starting broadcast to {len(all_users)} users.")
    success_count = 0
    fail_count = 0

    for user_id in all_users:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo=photo_id, caption=text)
            else:
                await bot.send_message(user_id, text=text)
            logger.debug(f"Successfully sent broadcast message to user {user_id}.")
            success_count += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            fail_count += 1
            logger.warning(f"Failed to send broadcast message to user {user_id}: {e}")
        except Exception as e:
            fail_count += 1
            logger.error(f"An unexpected error occurred while sending broadcast to user {user_id}: {e}")
        await asyncio.sleep(0.1)

    result_text = get_text('admin.mailing_finished', success_count=success_count, fail_count=fail_count)
    logger.success(f"Mailing finished. Success: {success_count}, Failed: {fail_count}.")
    await bot.send_message(
        chat_id=admin_id,
        text=result_text
    )

@router.message(Command("addnuts"))
async def add_nuts_command(message: Message, command: CommandObject, bot: Bot):
    admin_id = message.from_user.id

    if not command.args:
        await message.answer(get_text("admin.addnuts.usage"))
        return

    try:
        parts = command.args.split()
        if len(parts) != 2:
            raise ValueError("Incorrect number of arguments.")

        user_id_str, amount_str = parts
        user_id = int(user_id_str)
        amount = int(amount_str)

        if amount <= 0:
            await message.answer(get_text('admin.addnuts.invalid_amount'))
            return

    except (ValueError, TypeError):
        await message.answer(get_text("admin.addnuts.usage"))
        return

    target_user = await User.get_user(user_id)
    if not target_user:
        await message.answer(get_text("admin.addnuts.user_not_found", user_id=user_id))
        return

    description = "Начисление от администратора"
    await Transaction.add_transaction(user_id, amount, description)
    logger.success(f"Admin {admin_id} added {amount} nuts to user {user_id}")

    await message.answer(get_text("admin.addnuts.success", user_id=user_id, amount=amount))

    try:
        await bot.send_message(user_id, get_text('admin.addnuts.user_notification', amount=amount))
        logger.info(f"Successfully notified user {user_id} about receiving nuts.")
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(f"Could not notify user {user_id}. The bot might be blocked.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while notifying user {user_id}: {e}")


@router.message(Command("test_mileage_reminder"), lambda msg: msg.from_user.id in config.admin_ids)
async def test_mileage_update_reminder(message: Message, bot: Bot):
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} initiated a test mileage reminder.")
    active_car = await Car.get_active_car(user_id)

    if not active_car:
        logger.warning(f"Admin {user_id} tried to test reminder, but has no active car.")
        await message.reply("Нет активного автомобиля.")
        return

    car_id = active_car[0]
    car_name = active_car[2]
    await message.reply(f"Отправляю тестовое напоминание о пробеге для автомобиля '{car_name}'.")

    success = await send_mileage_reminder(bot, user_id, car_name, car_id)
    if not success:
        logger.error(f"Failed to send test mileage reminder to admin {user_id}.")
        await message.reply("Произошла ошибка при отправке тестового напоминания.")

@router.message(Command("test_time_reminder"), F.from_user.id.in_(config.admin_ids))
async def test_time_based_notification_command(message: Message, bot: Bot):
    """
    Sends a test notification for the first available time-based reminder
    of the admin's active car.
    """
    admin_id = message.from_user.id
    logger.info(f"Admin {admin_id} initiated a test time-based notification.")

    active_car = await Car.get_active_car(admin_id)
    if not active_car:
        logger.warning(f"Admin {admin_id} has no active car to test time-based reminder.")
        await message.reply("У вас нет активного автомобиля для теста.")
        return

    reminders = await Reminder.get_reminders_for_car(active_car['car_id'])
    time_reminder = None
    for rem in reminders:
        if rem['type'] == 'time' and rem['last_reset_date'] and rem['interval_days']:
            time_reminder = rem
            break

    if not time_reminder:
        logger.warning(f"Admin {admin_id} has no configured time-based reminders for the active car.")
        await message.reply(
            "Не найдено ни одного настроенного отслеживания по времени для активного автомобиля. "
            "Создайте его и попробуйте снова."
        )
        return

    reminder_id = time_reminder['reminder_id']
    reminder_name = time_reminder['name']
    car_name = active_car['name']
    days_left_for_test = 7

    await message.reply(f"Отправляю тестовое уведомление для отслеживания '{reminder_name}'.")

    success = await send_time_based_notification(
        bot=bot,
        user_id=admin_id,
        car_name=car_name,
        reminder_name=reminder_name,
        days_left=days_left_for_test,
        reminder_id=reminder_id
    )

    if not success:
        logger.error(f"Failed to send test time-based notification to admin {admin_id}.")
        await message.reply("Произошла ошибка при отправке тестового уведомления.")

@router.callback_query(F.data == "export_database", F.from_user.id.in_(config.admin_ids))
async def export_database(callback: CallbackQuery, bot: Bot, state: FSMContext):
    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} initiated database export.")

    await callback.answer("Начинаю экспорт...")
    await callback.bot.send_message(admin_id, "⏳ Начинаю экспорт базы данных... Это может занять некоторое время.")

    zip_file_path = None
    try:
        zip_file_path = await create_db_dump_zip()

        if zip_file_path and os.path.exists(zip_file_path):
            logger.success(f"Database export successful. Sending {zip_file_path} to admin {admin_id}.")
            document = FSInputFile(zip_file_path)
            await bot.send_document(admin_id, document, caption="✅ Экспорт завершен. Ваш архив с базой данных.")
        else:
            logger.error("Database export failed, zip file not created.")
            await bot.send_message(admin_id, "❌ Произошла ошибка во время экспорта базы данных.")

    except Exception as e:
        logger.error(f"An error occurred during database export for admin {admin_id}: {e}", exc_info=True)
        await bot.send_message(admin_id, "❌ Произошла критическая ошибка во время экспорта.")
    finally:
        if zip_file_path and os.path.exists(zip_file_path):
            try:
                os.remove(zip_file_path)
                logger.info(f"Cleaned up zip file: {zip_file_path}")
            except OSError as e:
                logger.error(f"Error removing zip file {zip_file_path}: {e}")

        await show_admin_panel(callback.message, state)


@router.callback_query(F.data == "create_referral_link", F.from_user.id.in_(config.admin_ids))
async def start_referral_link_creation(callback: CallbackQuery, state: FSMContext):
    logger.info(f"Admin {callback.from_user.id} initiated custom referral link creation.")
    await state.set_state(AdminFSM.get_referral_code)

    prompt_text = (
        "Введите уникальный код для реферальной ссылки (например, <code>promo2025</code> или <code>new_campaign</code>).\n\n"
        "Используйте только латинские буквы, цифры и символ подчеркивания `_`."
    )

    msg = await callback.message.edit_text(
        text=prompt_text,
        reply_markup=get_back_keyboard("show_admin_panel")
    )
    await state.update_data(prompt_message_id=msg.message_id)
    await callback.answer()

@router.message(AdminFSM.get_referral_code)
async def process_referral_code(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    code = message.text.strip()

    if not re.match(r'^[a-zA-Z0-9_]+$', code):
        logger.warning(f"Admin {admin_id} entered invalid referral code: '{code}'")
        error_msg = await message.answer(
            "❌ Неверный формат кода. Используйте только латинские буквы (a-z, A-Z), цифры (0-9) и символ подчеркивания (_)."
        )
        await message.delete()
        await asyncio.sleep(5)
        await error_msg.delete()
        return

    await message.delete()
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")
    await state.clear()

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={code}"

    logger.success(f"Admin {admin_id} created custom referral link with code: {code}")

    response_text = (
        f"✅ Ваша кастомная реферальная ссылка успешно создана:\n\n"
        f"{ref_link}\n\n"
        f"Нажмите на ссылку, чтобы скопировать ее. Когда новый пользователь перейдет по этой ссылке, он будет зарегистрирован "
        f"без начисления вознаграждения кому-либо (используется для отслеживания кампаний)."
    )

    try:
        await bot.edit_message_text(
            chat_id=admin_id,
            message_id=prompt_message_id,
            text=response_text,
            reply_markup=get_back_keyboard("show_admin_panel")
        )
    except TelegramBadRequest:
        await bot.send_message(
            chat_id=admin_id,
            text=response_text,
            reply_markup=get_back_keyboard("show_admin_panel")
        )

@router.callback_query(F.data == "referral_stats")
async def show_referral_stats(callback: CallbackQuery):
    """Shows the first page of the referral code statistics."""
    await _display_referral_stats_page(callback, page=1)
    await callback.answer()


@router.callback_query(F.data.startswith("ref_stats_page:"))
async def paginate_referral_stats(callback: CallbackQuery):
    """Handles pagination for the referral statistics view."""
    try:
        page = int(callback.data.split(":")[1])
        await _display_referral_stats_page(callback, page)
    except (ValueError, IndexError):
        logger.warning(f"Invalid pagination callback received: {callback.data}")
    finally:
        await callback.answer()


async def _display_referral_stats_page(callback: CallbackQuery, page: int):
    """
    A helper function to display a specific page of the referral stats.
    """
    logger.info(f"Admin {callback.from_user.id} is viewing referral stats page {page}.")

    all_stats = await User.get_all_referral_code_stats()

    if not all_stats:
        text = "<b>Статистика по реферальным кодам</b>\n\nПользователи еще не регистрировались по кастомным ссылкам."
        keyboard = get_back_keyboard("show_admin_panel")
        await callback.message.edit_text(text, reply_markup=keyboard)
        return

    # Pagination logic
    total_pages = math.ceil(len(all_stats) / REF_STATS_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * REF_STATS_PAGE_SIZE
    end_index = start_index + REF_STATS_PAGE_SIZE

    page_stats = all_stats[start_index:end_index]

    # Format the text
    header = "<b>Статистика по реферальным кодам:</b>"

    stats_lines = []
    for code, count in page_stats:
        stats_lines.append(f"▫️ <code>{code}</code>: <b>{count}</b> чел.")

    page_footer = f"\n\nСтраница {page}/{total_pages}"
    full_text = f"{header}\n\n" + "\n".join(stats_lines) + page_footer

    keyboard = get_referral_stats_keyboard(page, total_pages)
    await callback.message.edit_text(text=full_text, reply_markup=keyboard)