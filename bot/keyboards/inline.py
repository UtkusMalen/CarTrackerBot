from datetime import datetime
from typing import Tuple, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiosqlite import Row

from bot.utils.text_manager import get_text


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns the initial keyboard for the bot."""
    button = [[InlineKeyboardButton(text="🚀 Поехали!", callback_data="start_registration")]]
    return InlineKeyboardMarkup(inline_keyboard=button)


def get_registration_step_keyboard(back_callback: str, skip_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with Back and 'Specify Later' buttons."""
    buttons = [
        [InlineKeyboardButton(text="Указать позже", callback_data=skip_callback)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_oil_interval_keyboard(back_callback: str, skip_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with predefined oil change intervals, a skip, and a back button."""
    buttons = [
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(5, 8)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(8, 11)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(11, 14)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(14, 17)],
        [InlineKeyboardButton(text="Указать позже", callback_data=skip_callback)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with a single 'Back' button pointing to a specific callback."""
    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_profile_keyboard() -> InlineKeyboardMarkup:
    """Returns the static profile menu keyboard."""
    buttons = [
        [InlineKeyboardButton(text=get_text('profile.my_garage_button'), callback_data="my_garage")],
        [InlineKeyboardButton(text=get_text('profile.transaction_history_button'),
                              callback_data="transaction_history")],
        [InlineKeyboardButton(text=get_text('profile.rating_button'), callback_data="rating_details")],
        [InlineKeyboardButton(text=get_text('profile.invite_friend_button'), callback_data="invite_friend")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reminder_management_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for managing configured mileage-based reminders."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking'),
                              callback_data=f"edit_mileage_tracking:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.start_again'),
                              callback_data=f"reset_mileage_tracking_start:{reminder_id}")],
        [InlineKeyboardButton(text="❌ Удалить отслеживание", callback_data=f"delete_reminder:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_trackings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mileage_tracking_initial_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for an unconfigured mileage-based reminder."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking'),
                              callback_data=f"edit_mileage_tracking:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.start_again'),
                              callback_data=f"reset_mileage_tracking_start:{reminder_id}")],
        [InlineKeyboardButton(text="❌ Удалить отслеживание", callback_data=f"delete_reminder:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_trackings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mileage_tracking_edit_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for editing an unconfigured mileage-based reminder."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_name'),
                              callback_data=f"edit_reminder_name:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_interval_km'),
                              callback_data=f"edit_reminder_interval_km:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_start_mileage'),
                              callback_data=f"edit_reminder_last_reset_mileage:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_reminder:{reminder_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_exact_mileage_edit_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for editing an exact mileage-based reminder."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_name'),
                              callback_data=f"edit_reminder_name:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_target_mileage'),
                              callback_data=f"edit_reminder_target_mileage:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_reminder:{reminder_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reset_mileage_tracking_keyboard(reminder_id: int, current_mileage: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for the mileage prompt when resetting a mileage tracking."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.use_current_mileage', mileage=current_mileage),
                              callback_data=f"set_current_mileage:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"manage_reminder:{reminder_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Returns a generic Yes/No keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=yes_callback),
            InlineKeyboardButton(text="❌ Нет", callback_data=no_callback),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notes_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for the notes menu with pagination."""
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить запись", callback_data="add_note")],
        [
            InlineKeyboardButton(text="Удалить запись", callback_data=f"delete_note_start:{page}"),
            InlineKeyboardButton(text="📌 Закрепить/Открепить", callback_data=f"pin_note_start:{page}")
        ],
    ]

    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"notes_page:{page - 1}")
        )
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="Следующая ➡️", callback_data=f"notes_page:{page + 1}")
        )

    if pagination_buttons:
        buttons.append(pagination_buttons)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_notes_keyboard(notes: List[Tuple], page: int) -> InlineKeyboardMarkup:
    """Returns a keyboard to select which note to delete."""
    buttons = []
    for note_id, text, date, _ in notes:
        display_text = (text[:25] + '...') if len(text) > 25 else text
        buttons.append([InlineKeyboardButton(
            text=f"❌ {date}: {display_text}",
            callback_data=f"delete_note_confirm:{note_id}:{page}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"show_notes_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_pin_notes_keyboard(notes: List[Tuple], page: int) -> InlineKeyboardMarkup:
    """Returns a keyboard to select which note to pin/unpin."""
    buttons = []
    for note_id, text, date, is_pinned in notes:
        display_text = (text[:25] + "...") if len(text) > 25 else text
        pin_emoji = "📌" if is_pinned else "📎"
        buttons.append([InlineKeyboardButton(
            text=f"{pin_emoji} {date}: {display_text}",
            callback_data=f"pin_note_confirm:{note_id}:{page}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"show_notes_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_garage_keyboard(cars: List[Row]) -> InlineKeyboardMarkup:
    """Returns the keyboard for the new garage menu."""
    buttons = []

    if cars:
        for car_row in cars:
            buttons.append([
                InlineKeyboardButton(
                    text=get_text('profile.garage.select_car_button', name=car_row['name']),
                    callback_data=f"select_car:{car_row['car_id']}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="➕ Добавить автомобиль", callback_data="start_registration")
        ])
        buttons.append([
            InlineKeyboardButton(text="❌ Удалить автомобиль", callback_data="delete_car_start")
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text=get_text('profile.garage.add_first_car_button'),
                callback_data="start_registration")
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_car_keyboard(cars: List[Row]) -> InlineKeyboardMarkup:
    """Returns a keyboard to select which car to delete."""
    buttons = []
    for car_row in cars:
        display_text = (car_row['name'][:25] + "...") if len(car_row['name']) > 25 else car_row['name']
        buttons.append([InlineKeyboardButton(
            text=f"❌ {display_text}",
            callback_data=f"delete_car_confirm:{car_row['car_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="my_garage")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_tracking_menu_keyboard(reminders: List[Row]) -> InlineKeyboardMarkup:
    """Returns the keyboard for the tracking menu."""
    buttons = []

    for reminder_row in reminders:
        buttons.append([InlineKeyboardButton(text=reminder_row['name'],
                                             callback_data=f"manage_reminder:{reminder_row['reminder_id']}")])

    buttons.append(
        [InlineKeyboardButton(text=get_text('reminders.create_tracking_button'), callback_data="create_reminder")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_time_tracking_keyboard(reminder_id: int, is_initial: bool = False, is_repeating: bool = False) -> InlineKeyboardMarkup:
    """Returns the keyboard for managing a single time-based tracking."""
    buttons = []
    if is_initial:
        buttons.append([InlineKeyboardButton(text=get_text('keyboards.edit_tracking'),
                                             callback_data=f"edit_time_tracking:{reminder_id}")])
        buttons.append(
            [InlineKeyboardButton(text=get_text('keyboards.start_again'),
                                  callback_data=f"reset_time_tracking_start:{reminder_id}")])
    else:
        repeat_text = "✅ Повторять" if is_repeating else "❌ Повторять"
        buttons.append([InlineKeyboardButton(text=get_text('keyboards.edit_tracking'),
                                             callback_data=f"edit_time_tracking:{reminder_id}")])
        buttons.append(
            [InlineKeyboardButton(text=repeat_text, callback_data=f"toggle_repeat_tracking:{reminder_id}")])
        buttons.append(
            [InlineKeyboardButton(text=get_text('keyboards.start_again'),
                                  callback_data=f"reset_time_tracking_start:{reminder_id}")])

    buttons.append([InlineKeyboardButton(text="❌ Удалить отслеживание", callback_data=f"delete_reminder:{reminder_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_trackings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_time_tracking_edit_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for editing a time-based tracking."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_name'),
                              callback_data=f"edit_reminder_name:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_interval_days'),
                              callback_data=f"edit_reminder_interval_days:{reminder_id}")],
        [InlineKeyboardButton(text=get_text('keyboards.edit_tracking_start_mileage'),
                              callback_data=f"edit_reminder_start_date:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_reminder:{reminder_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_time_based_notification_keyboard(reminder_id: int, current_day: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for a time-based reminder notification."""
    buttons = [
        [InlineKeyboardButton(
            text="Не напоминать",
            callback_data=f"time_notify_stop:{reminder_id}"
        )],
        [InlineKeyboardButton(
            text="Спасибо!",
            callback_data=f"time_notify_ack:{reminder_id}:{current_day}"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reset_time_tracking_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for the date prompt when resetting a time tracking."""
    current_date = datetime.now().strftime('%d.%m.%Y')
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.use_current_date', date=current_date),
                              callback_data=f"set_current_date:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"manage_reminder:{reminder_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reminder_type_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for choosing the reminder type."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.reminder_type_interval'),
                              callback_data="set_reminder_type:mileage_interval")],
        [InlineKeyboardButton(text=get_text('keyboards.reminder_type_exact'),
                              callback_data="set_reminder_type:exact_mileage")],
        [InlineKeyboardButton(text=get_text('keyboards.reminder_type_time'), callback_data="set_reminder_type:time")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_trackings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_use_current_mileage_keyboard(back_callback: str, current_mileage: int) -> InlineKeyboardMarkup:
    """Returns a keyboard with a 'Use current' mileage button."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.use_current_mileage', mileage=current_mileage),
                              callback_data=f"use_current_mileage:{current_mileage}")],
        [get_back_keyboard(back_callback).inline_keyboard[0][0]]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_use_current_date_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with a 'Use current' date button."""
    current_date = datetime.now().strftime('%d.%m.%Y')
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.use_current_date', date=current_date),
                              callback_data=f"use_current_date:{current_date}")],
        [get_back_keyboard(back_callback).inline_keyboard[0][0]]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_use_current_date_for_start_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """
    Returns a keyboard with a 'Use current' date button for the start date of a reminder.
    This uses a unique callback to distinguish it from other "use current date" actions.
    """
    current_date = datetime.now().strftime('%d.%m.%Y')
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.use_current_date', date=current_date),
                              callback_data="use_current_date_for_start")],
        [get_back_keyboard(back_callback).inline_keyboard[0][0]]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notification_config_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for configuring notifications after creation."""
    buttons = [
        [InlineKeyboardButton(text=get_text('keyboards.notification_thanks'),
                              callback_data=f"finish_creation:{reminder_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Returns the main admin panel keyboard"""
    buttons = [
        [InlineKeyboardButton(text="📢 Создать рассылку", callback_data="create_mailing")],
        [InlineKeyboardButton(text="Выгрузить базу данных 💾", callback_data="export_database")],
        [InlineKeyboardButton(text="Создать реф. ссылку 🔗", callback_data="create_referral_link")],
        [InlineKeyboardButton(text="Статистика по ссылкам 📊", callback_data="referral_stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_referral_stats_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []

    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        buttons.append([
            InlineKeyboardButton(text="⬅️", callback_data=f"ref_stats_page:{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="..."),
            InlineKeyboardButton(text="➡️", callback_data=f"ref_stats_page:{next_page}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="show_admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_mailing_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for confirming the mailing"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="send_mailing"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_mailing"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Returns a keyboard with a single 'To Main Menu' button."""
    buttons = [[InlineKeyboardButton(text="В главное меню", callback_data="main_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_options_keyboard(field_key: str, options: List[str]) -> InlineKeyboardMarkup:
    """Creates a keyboard with pre-defined options for a summary field."""
    buttons = []
    for i in range(0, len(options), 2):
        row = [
            InlineKeyboardButton (
                text=options[i],
                callback_data=f"set_summary_option:{field_key}:{options[i]}"
            )
        ]
        if i + 1 < len(options):
            row.append(
                InlineKeyboardButton(
                    text=options[i + 1],
                    callback_data=f"set_summary_option:{field_key}:{options[i + 1]}"
                )
            )
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="car_summary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_summary_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the car summary menu with a two-column layout."""
    buttons = []
    field_labels = get_text('summary.field_labels')

    # Convert dictionary items to a list to allow iteration by index
    field_items = list(field_labels.items())

    # Iterate through the items, taking two at a time to create rows
    for i in range(0, len(field_items), 2):
        # Start a new row with the first button
        row = [
            InlineKeyboardButton(
                text=field_items[i][1],  # The label (e.g., "Марка")
                callback_data=f"edit_summary:{field_items[i][0]}"  # The key (e.g., "make")
            )
        ]

        # If there's a second item for this row, add it to the same row
        if i + 1 < len(field_items):
            row.append(
                InlineKeyboardButton(
                    text=field_items[i + 1][1],  # The label for the second button
                    callback_data=f"edit_summary:{field_items[i + 1][0]}"  # The key for the second button
                )
            )

        # Add the completed row (with one or two buttons) to the keyboard
        buttons.append(row)

    # Add the 'Back' button on its own row at the end
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_expense_category_keyboard(categories: List[Row]) -> InlineKeyboardMarkup:
    """Creates a keyboard with expense categories."""
    buttons = []
    # Create a 3-column layout
    for i in range(0, len(categories), 3):
        row = []
        for j in range(3):
            if i + j < len(categories):
                cat = categories[i+j]
                row.append(
                    InlineKeyboardButton(text=cat['name'], callback_data=f"set_exp_cat:{cat['category_id']}:{cat['name']}")
                )
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text=get_text('expense.create_category_button'), callback_data="create_exp_cat")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_expense_skip_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with a Skip and Back button."""
    buttons = [
        [InlineKeyboardButton(text=get_text('expense.skip_button'), callback_data="skip_expense_step")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_expense_mileage_keyboard(current_mileage: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for the mileage step in expense tracking."""
    buttons = [
        [InlineKeyboardButton(text=get_text('expense.use_current_mileage_button', mileage=current_mileage), callback_data=f"use_current_exp_mileage:{current_mileage}")],
        [InlineKeyboardButton(text=get_text('expense.skip_button'), callback_data="skip_expense_step")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="add_expense")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_expense_date_keyboard() -> InlineKeyboardMarkup:
    """Returns a keyboard for the date step in expense tracking."""
    current_date_str = datetime.now().strftime('%d.%m.%Y')
    current_date_sql = datetime.now().strftime('%Y-%m-%d')
    buttons = [
        [InlineKeyboardButton(text=get_text('expense.use_current_date_button', date=current_date_str), callback_data=f"use_current_exp_date:{current_date_sql}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="add_expense")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_detailed_rating_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Returns the pagination keyboard for the detailed rating view."""
    buttons = []
    pagination_buttons = []

    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"rating_page:{page - 1}")
        )
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="Следующая ➡️", callback_data=f"rating_page:{page + 1}")
        )

    if pagination_buttons:
        buttons.append(pagination_buttons)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_transaction_history_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Returns the pagination keyboard for the transaction history view."""
    buttons = []
    pagination_buttons = []

    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"trans_page:{page - 1}")
        )
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="Следующая ➡️", callback_data=f"trans_page:{page + 1}")
        )

    if pagination_buttons:
        buttons.append(pagination_buttons)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_fuel_tracking_menu_keyboard(data: dict) -> InlineKeyboardMarkup:
    """Generates the dynamic keyboard for the fuel tracking menu."""
    full_tank_icon = "✅" if data.get("is_full") else "❌"
    mileage_val = data.get("mileage", get_text('fuel_tracking.value_not_set'))
    liters_val = data.get("liters", get_text('fuel_tracking.value_not_set'))
    sum_val = data.get("total_sum", get_text('fuel_tracking.value_not_set'))
    date_val = data.get("date_str", get_text('fuel_tracking.value_not_set'))

    buttons = [
        [InlineKeyboardButton(text=get_text('fuel_tracking.full_tank_button', icon=full_tank_icon), callback_data="fuel:toggle_full")],
        [
            InlineKeyboardButton(text=get_text('fuel_tracking.mileage_button', value=mileage_val), callback_data="fuel:edit:mileage"),
            InlineKeyboardButton(text=get_text('fuel_tracking.liters_button', value=liters_val), callback_data="fuel:edit:liters")
        ],
        [
            InlineKeyboardButton(text=get_text('fuel_tracking.sum_button', value=sum_val), callback_data="fuel:edit:sum"),
            InlineKeyboardButton(text=get_text('fuel_tracking.date_button', value=date_val), callback_data="fuel:edit:date")
        ],
        [InlineKeyboardButton(text=get_text('fuel_tracking.create_button'), callback_data="fuel:create")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_fuel_log_keyboard(page: int, total_pages: int, tank_volume: Optional[float]) -> InlineKeyboardMarkup:
    """Returns the keyboard for the fuel log view."""
    buttons = []
    pagination_row = []

    if page > 1:
        pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"fuel_log_page:{page-1}"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"fuel_log_page:{page+1}"))
    if pagination_row:
        buttons.append(pagination_row)

    buttons.append([
        InlineKeyboardButton(text=get_text('fuel_log.delete_entry_button'), callback_data=f"delete_fuel_entry_start:{page}")
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_expenses")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_delete_fuel_entry_keyboard(entries: List[Row], page: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for selecting which fuel entry to delete."""
    buttons = []
    for entry in entries:
        date_str = datetime.strptime(entry['created_at'], '%Y-%m-%d').strftime('%d.%m.%y')
        buttons.append([
            InlineKeyboardButton(
                text=get_text('fuel_log.delete_confirm_button', date=date_str, liters=entry['liters']),
                callback_data=f"delete_fuel_entry_confirm:{entry['entry_id']}:{page}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"fuel_log_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_expenses_summary_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the main expenses summary view."""
    buttons = [
        [InlineKeyboardButton(text=get_text('my_expenses.detailed_log_button'), callback_data="detailed_expense_log")],
        [InlineKeyboardButton(text=get_text('my_expenses.fuel_log_button'), callback_data="fuel_log")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_detailed_expenses_log_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for the detailed, paginated expense log."""
    buttons = [
        [InlineKeyboardButton(text=get_text('my_expenses.add_expense_button'), callback_data="add_expense")],
        [
            InlineKeyboardButton(text=get_text('my_expenses.delete_expense_button'), callback_data=f"delete_expense_start:{page}")
        ]
    ]
    # Pagination
    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"expense_page:{page-1}"))
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(text="➡️", callback_data=f"expense_page:{page+1}"))
    if pagination_row:
        buttons.append(pagination_row)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_expenses")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_expense_keyboard(expenses: List[Row], page: int) -> InlineKeyboardMarkup:
    """Returns a keyboard for selecting which expense to delete."""
    buttons = []
    for exp in expenses:
        date_str = datetime.strptime(exp['created_at'], '%Y-%m-%d').strftime('%d.%m.%y')
        buttons.append([
            InlineKeyboardButton(
                text=get_text('my_expenses.delete_confirm_button', date=date_str, category=exp['category_name'], amount=exp['amount']),
                callback_data=f"delete_expense_confirm:{exp['expense_id']}:{page}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"detailed_expense_log_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)