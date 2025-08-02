from typing import Tuple, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.text_manager import get_text


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns the initial keyboard for the bot."""
    button = [[InlineKeyboardButton(text="Поехали!", callback_data="start_registration")]]
    return InlineKeyboardMarkup(inline_keyboard=button)

def get_oil_interval_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    """Returns a keyboard with predefined oil change intervals and a back button."""
    buttons = [
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(5, 8)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(8, 11)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(11, 14)],
        [InlineKeyboardButton(text=f"{i * 1000}", callback_data=f"interval_{i * 1000}") for i in range(14, 17)],
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
        [InlineKeyboardButton(text="Период напоминания", callback_data="change_reminder_period")],
        [InlineKeyboardButton(text=get_text('profile.transaction_history_button'), callback_data="transaction_history")],
        [InlineKeyboardButton(text=get_text('profile.rating_button'), callback_data="rating_details")],
        [InlineKeyboardButton(text=get_text('profile.invite_friend_button'), callback_data="invite_friend")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_mileage_reminder_keyboard(car_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for the mileage reminder menu."""
    buttons = [
        [InlineKeyboardButton(text="Обновить пробег", callback_data="update_mileage")],
        [InlineKeyboardButton(text="Напомнить завтра", callback_data=f"snooze_mileage_reminder:{car_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reminder_management_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Returns the keyboard for managing reminders."""
    buttons = [
        [InlineKeyboardButton(text="Изменить интервал", callback_data=f"change_interval:{reminder_id}")],
        [InlineKeyboardButton(text="Обнулить отсчёт", callback_data=f"reset_reminder:{reminder_id}")],
        [InlineKeyboardButton(text="❌ Удалить напоминание", callback_data=f"delete_reminder:{reminder_id}")],
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")],
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
        [InlineKeyboardButton(text="Добавить запись", callback_data="add_note")],
        [InlineKeyboardButton(text="Удалить запись", callback_data=f"delete_note_start:{page}")],
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
    for note_id, text, date in notes:
        display_text = (text[:25] + '...') if len(text) > 25 else text
        buttons.append([InlineKeyboardButton(
            text=f"❌ {date}: {display_text}",
            callback_data=f"delete_note_confirm:{note_id}:{page}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"show_notes_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_garage_keyboard(cars: List[Tuple]) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton(text="+ Добавить автомобиль", callback_data="start_registration")
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

def get_delete_car_keyboard(cars: List[Tuple]) -> InlineKeyboardMarkup:
    """Returns a keyboard to select which car to delete."""
    buttons = []
    for car_id, name, mileage in cars:
        display_text = (name[:25] + "...") if len(name) > 25 else name
        buttons.append([InlineKeyboardButton(
            text=f"❌ {display_text}",
            callback_data=f"delete_car_confirm:{car_id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="my_garage")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_create_reminder_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for creating a new reminder."""
    buttons = [
        [InlineKeyboardButton(text="Воздушный фильтр", callback_data="create_reminder_preset:Воздушный фильтр")],
        [InlineKeyboardButton(text="Тормозные колодки", callback_data="create_reminder_preset:Тормозные колодки")],
        [InlineKeyboardButton(text="Фильтр салона", callback_data="create_reminder_preset:Фильтр салона")],
        [InlineKeyboardButton(text="Свечи зажигания", callback_data="create_reminder_preset:Свечи зажигания")],
        [InlineKeyboardButton(text="Создать своё напоминание", callback_data="create_reminder_custom")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Returns the main admin panel keyboard"""
    buttons = [
        [InlineKeyboardButton(text="Создать рассылку", callback_data="create_mailing")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ]
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

def get_summary_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the car summary menu"""
    buttons = []

    field_labels = get_text('summary.field_labels')

    for field_key, field_label in field_labels.items():
        buttons.append([InlineKeyboardButton(
            text=field_label,
            callback_data=f"edit_summary:{field_key}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
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

def get_insurance_duration_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for selecting insurance policy duration."""
    buttons = [
        [
            InlineKeyboardButton(text=get_text('insurance.duration_3_months'), callback_data="set_insurance_duration:90"),
            InlineKeyboardButton(text=get_text('insurance.duration_6_months'), callback_data="set_insurance_duration:182"),
        ],
        [InlineKeyboardButton(text=get_text('insurance.duration_1_year'), callback_data="set_insurance_duration:365")],
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)