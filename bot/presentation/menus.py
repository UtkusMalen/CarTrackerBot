from datetime import datetime, timedelta

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.database.models import Car, Reminder
from bot.utils.text_manager import get_text


async def _get_main_menu_content(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Helper to generate the content for the main menu."""
    car_row = await Car.get_active_car(user_id)
    if not car_row:
        return None

    car_id = car_row['car_id']
    car_name = car_row['name']
    mileage = car_row['mileage']
    reminders = await Reminder.get_reminders_for_car(car_id)

    reminders_text_parts = []
    reminder_buttons = []

    for rem_id, name, interval, last_reset in reminders:
        rem_remaining = (last_reset + interval) - mileage

        if rem_remaining <= 0:
            reminders_text_parts.append(
                get_text('main_menu.reminder_line_due').format(name=name).replace('\\n', '\n')
            )
        else:
            progress_percentage = ((interval - rem_remaining) / interval) if interval > 0 else 1
            progress_percentage = max(0, min(1, progress_percentage))

            progress = int(progress_percentage * 10)

            if progress_percentage >= 0.8:
                bar_emoji = '🟥'
            elif progress_percentage >= 0.5:
                bar_emoji = '🟨'
            else:
                bar_emoji = '🟩'

            rem_progress_bar = bar_emoji * progress + "─" * (10 - progress)

            reminders_text_parts.append(
                get_text('main_menu.reminder_line').format(
                    name=name,
                    remaining_km=rem_remaining,
                    progress_bar=rem_progress_bar,
                    progress_percent=int(progress_percentage * 100)
                ).replace('\\n', '\n')
            )

        reminder_buttons.append(
            [InlineKeyboardButton(text=name, callback_data=f"manage_reminder:{rem_id}")]
        )

    active_reminders_section = "\n\n".join(reminders_text_parts) if reminders_text_parts else get_text('main_menu.no_active_reminders')

    insurance_section_text = ""
    insurance_start_date_str = car_row['insurance_start_date']
    insurance_duration_days = car_row['insurance_duration_days']

    if insurance_start_date_str and insurance_duration_days:
        start_date = datetime.strptime(insurance_start_date_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=insurance_duration_days)
        remaining_days = (end_date - datetime.now().date()).days

        if remaining_days > 0:
            progress_percentage = (insurance_duration_days - remaining_days) / insurance_duration_days
            progress = int(progress_percentage * 10)

            if progress_percentage >= 0.8:
                bar_emoji = '🟥'
            elif progress_percentage >= 0.5:
                bar_emoji = '🟨'
            else:
                bar_emoji = '🟩'

            progress_bar = bar_emoji * progress + "─" * (10 - progress)

            insurance_section_text = get_text(
                'main_menu.insurance_line',
                remaining_days=remaining_days,
                progress_bar=progress_bar,
                progress_percent=int(progress_percentage * 100)
            ).replace('\\n', '\n')
        else:
            insurance_section_text = get_text('main_menu.insurance_line_expired').replace('\\n', '\n')
    else:
        insurance_section_text = get_text('main_menu.insurance_not_set_prompt').replace('\\n', '\n')

    menu_text = f"{get_text('main_menu.header', car_name=car_name)}\n" \
                f"{get_text('main_menu.mileage', mileage=mileage)}\n\n" \
                f"{get_text('main_menu.reminders_header')}\n" \
                f"{active_reminders_section}\n\n" \
                f"{insurance_section_text}"

    top_buttons = [
        [InlineKeyboardButton(text=get_text('main_menu.add_insurance_button'), callback_data="add_insurance")],
        # [InlineKeyboardButton(text="Мой авто🚘", callback_data="car_summary")],
        [
            InlineKeyboardButton(text="Мой профиль", callback_data="my_profile"),
            InlineKeyboardButton(text="Обновить пробег", callback_data="update_mileage"),
        ]
    ]
    bottom_buttons = [
        [InlineKeyboardButton(text="+ Создать напоминание", callback_data="create_reminder")],
        [InlineKeyboardButton(text="Заметки", callback_data="notes")],
    ]

    final_buttons = top_buttons + reminder_buttons + bottom_buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=final_buttons)

    return menu_text, keyboard


async def show_main_menu(message: Message, user_id: int, edit: bool = True):
    """Displays or edits the message to show the main menu."""
    content = await _get_main_menu_content(user_id)
    if not content:
        await message.answer(get_text('main_menu.add_car_first'))
        return

    text, keyboard = content
    if edit:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                logger.warning("Message is not modified, skipping edit.")
            else:
                logger.warning(f"Failed to edit message: {e}. Sending new one.")
                await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)