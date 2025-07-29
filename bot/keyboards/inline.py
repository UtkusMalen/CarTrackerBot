from typing import Tuple, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
        [InlineKeyboardButton(text="Мои автомобили", callback_data="my_cars")],
        [InlineKeyboardButton(text="Период напоминания", callback_data="change_reminder_period")],
        [InlineKeyboardButton(text="+ Добавить автомобиль", callback_data="start_registration")],
        [InlineKeyboardButton(text="История начисления гаек", callback_data="nut_history")],
        [InlineKeyboardButton(text="Рейтинг пользователей", callback_data="user_rating")],
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

def get_notes_keyboard() -> InlineKeyboardMarkup:
    """Returns the keyboard for the notes menu."""
    buttons = [
        [InlineKeyboardButton(text="Добавить запись", callback_data="add_note")],
        [InlineKeyboardButton(text="Удалить запись", callback_data="delete_note_start")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_notes_keyboard(notes: List[Tuple]) -> InlineKeyboardMarkup:
    """Returns a keyboard to select which note to delete."""
    buttons = []
    for note_id, text, date in notes:
        # Truncate long text
        display_text = (text[:25] + '...') if len(text) > 25 else text
        buttons.append([InlineKeyboardButton(
            text=f"❌ {date}: {display_text}",
            callback_data=f"delete_note_confirm:{note_id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="show_notes")])
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