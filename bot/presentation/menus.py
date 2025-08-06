
from datetime import datetime, timedelta

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
from aiosqlite import Row

from bot.database.models import Car, Reminder
from bot.utils.message_manager import delete_previous_message, track_message
from bot.utils.text_manager import get_text


def _is_reminder_configured(reminder: Row) -> bool:
    """Checks if a reminder has the necessary data to be considered active."""
    rem_type = reminder['type']
    if rem_type in ('mileage', 'mileage_interval'):
        return reminder['interval_km'] is not None and reminder['last_reset_mileage'] is not None
    if rem_type == 'exact_mileage':
        return reminder['target_mileage'] is not None
    if rem_type == 'time':
        # This handles both the old insurance style and the new target_date style
        is_old_style_configured = reminder['interval_days'] is not None and reminder['last_reset_date'] is not None
        is_new_style_configured = reminder['target_date'] is not None
        return is_old_style_configured or is_new_style_configured
    return False


async def _get_main_menu_content(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """
    Completely refactored helper to generate the content for the main menu.
    Handles all reminder types and dynamically shows the setup prompt.
    """
    car_row = await Car.get_active_car(user_id)
    if not car_row:
        return None

    car_id = car_row['car_id']
    car_name = car_row['name']
    mileage = car_row['mileage']
    reminders = await Reminder.get_reminders_for_car(car_id)

    # --- Build Reminders/Trackings Text ---
    reminders_text_parts = []
    unconfigured_reminder_names = []

    for rem in reminders:
        rem_type = rem['type']
        is_configured = _is_reminder_configured(rem)

        if not is_configured:
            unconfigured_reminder_names.append(f'"{rem["name"]}"')

        # --- Mileage Interval ---
        if rem_type in ('mileage', 'mileage_interval'):
            if is_configured and mileage is not None:
                rem_remaining = (rem['last_reset_mileage'] + rem['interval_km']) - mileage
                progress_percentage = ((rem['interval_km'] - rem_remaining) / rem['interval_km'])
                progress = int(progress_percentage * 10)

                if rem_remaining <= 0:
                    rem_progress_bar = '🟥' * 10
                    reminders_text_parts.append(
                        get_text('main_menu.reminder_line_due_full_bar').format(
                            name=rem['name'], progress_bar=rem_progress_bar
                        ).replace('\\n', '\n')
                    )
                else:
                    bar_emoji = '🟥' if progress_percentage >= 0.8 else '🟨' if progress_percentage >= 0.5 else '🟩'
                    rem_progress_bar = bar_emoji * progress + "─" * (10 - progress)
                    reminders_text_parts.append(
                        get_text('main_menu.reminder_line').format(
                            name=rem['name'], remaining_km=rem_remaining,
                            progress_bar=rem_progress_bar, progress_percent=int(progress_percentage * 100)
                        ).replace('\\n', '\n')
                    )
            else:
                reminders_text_parts.append(
                    get_text('main_menu.reminder_line_empty_km', name=rem['name']).replace('\\n', '\n'))

        # --- Exact Mileage Target ---
        elif rem_type == 'exact_mileage':
            if is_configured and mileage is not None:
                rem_remaining = rem['target_mileage'] - mileage
                progress_percentage = (mileage / rem['target_mileage'])
                progress = int(progress_percentage * 10)

                if rem_remaining <= 0:
                    # Logic for when target is reached
                    rem_progress_bar = '🟥' * 10
                    reminders_text_parts.append(
                        get_text('main_menu.reminder_line_due_full_bar').format(
                            name=rem['name'], progress_bar=rem_progress_bar
                        ).replace('\\n', '\n')
                    )
                else:
                    # Logic for progress
                    bar_emoji = '🟥' if progress_percentage >= 0.8 else '🟨' if progress_percentage >= 0.5 else '🟩'
                    rem_progress_bar = bar_emoji * progress + "─" * (10 - progress)
                    reminders_text_parts.append(
                        get_text('main_menu.reminder_line').format(
                            name=rem['name'], remaining_km=rem_remaining,
                            progress_bar=rem_progress_bar, progress_percent=int(progress_percentage * 100)
                        ).replace('\\n', '\n')
                    )
            else:
                reminders_text_parts.append(
                    get_text('main_menu.reminder_line_empty_km', name=rem['name']).replace('\\n', '\n'))

        # --- Time-based (Old and New) ---
        elif rem_type == 'time':
            if is_configured:
                # Handle new target_date format
                if rem['target_date']:
                    end_date = datetime.strptime(rem['target_date'], '%Y-%m-%d').date()
                    # Cannot calculate progress without a start date, so show remaining days and an empty bar.
                    remaining_days = (end_date - datetime.now().date()).days
                    progress_bar = "─" * 10
                    reminders_text_parts.append(get_text(
                        'main_menu.insurance_line', name=rem['name'], remaining_days=max(0, remaining_days),
                        progress_bar=progress_bar, progress_percent=0
                    ).replace('\\n', '\n'))
                # Handle old interval_days format
                elif rem['interval_days'] and rem['last_reset_date']:
                    start_date = datetime.strptime(rem['last_reset_date'], '%Y-%m-%d').date()
                    end_date = start_date + timedelta(days=rem['interval_days'])
                    remaining_days = (end_date - datetime.now().date()).days
                    progress_percentage = (rem['interval_days'] - remaining_days) / rem['interval_days']
                    progress = int(progress_percentage * 10)
                    if remaining_days <= 0:
                        reminders_text_parts.append(
                            get_text('main_menu.insurance_line_expired_full_bar', name=rem['name'],
                                     progress_bar='🟥' * 10).replace('\\n', '\n'))
                    else:
                        bar_emoji = '🟥' if progress_percentage >= 0.8 else '🟨' if progress_percentage >= 0.5 else '🟩'
                        progress_bar = bar_emoji * progress + "─" * (10 - progress)
                        reminders_text_parts.append(get_text(
                            'main_menu.insurance_line', name=rem['name'], remaining_days=remaining_days,
                            progress_bar=progress_bar, progress_percent=int(progress_percentage * 100)
                        ).replace('\\n', '\n'))
            else:
                reminders_text_parts.append(
                    get_text('main_menu.insurance_line_empty', name=rem['name']).replace('\\n', '\n'))

    active_reminders_section = "\n".join(reminders_text_parts) if reminders_text_parts else get_text(
        'main_menu.no_active_reminders')

    # --- Build Final Menu Text ---
    mileage_text = get_text('main_menu.mileage', mileage=mileage) if mileage is not None else get_text(
        'main_menu.mileage_not_set')

    menu_text = f"{get_text('main_menu.header', car_name=car_name)}\n" \
                f"{mileage_text}\n\n" \
                f"{get_text('main_menu.reminders_header')}\n" \
                f"{active_reminders_section}"

    # Determine if the setup prompt should be shown
    is_setup_complete = (mileage is not None) and (not unconfigured_reminder_names)
    if not is_setup_complete:
        if unconfigured_reminder_names:
            names_str = ' и '.join(unconfigured_reminder_names)
            menu_text += "\n\n" + get_text('main_menu.setup_prompt_dynamic', unconfigured_names=names_str)
        else:  # This covers the case where only mileage is missing
            menu_text += "\n\n" + get_text('main_menu.setup_prompt_generic')

    # --- Build Keyboard ---
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Мой профиль", callback_data="my_profile"),
            InlineKeyboardButton(text="Обновить пробег", callback_data="update_mileage"),
        ],
        [
            InlineKeyboardButton(
                text=get_text('main_menu.trackings_button', count=len(reminders)),
                callback_data="manage_trackings"
            )
        ],
        [InlineKeyboardButton(text="Заметки", callback_data="notes")],
    ])

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
                await delete_previous_message(message)
                new_msg = await message.answer(text, reply_markup=keyboard)
                track_message(new_msg)
    else:
        await delete_previous_message(message)
        new_msg = await message.answer(text, reply_markup=keyboard)
        track_message(new_msg)