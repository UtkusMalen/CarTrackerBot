from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from bot.database.models import Car, Reminder
from bot.utils.text_manager import get_text


async def _get_main_menu_content(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Helper to generate the content for the main menu."""
    car = await Car.get_active_car(user_id)
    if not car:
        return None

    car_id, _, car_name, mileage, *_ = car
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
            rem_progress_bar = "🟩" * progress + "─" * (10 - progress)

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

    menu_text = f"{get_text('main_menu.header', car_name=car_name)}\n" \
                f"{get_text('main_menu.mileage', mileage=mileage)}\n\n" \
                f"{get_text('main_menu.reminders_header')}\n" \
                f"{active_reminders_section}\n\n" \
                f"{get_text('main_menu.add_reminder_prompt')}"

    top_buttons = [
        [InlineKeyboardButton(text="Мой авто🚘", callback_data="car_summary")],
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