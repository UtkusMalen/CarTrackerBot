from aiogram.fsm.state import State, StatesGroup

class ReminderFSM(StatesGroup):
    # --- Creation Flow ---
    get_name = State()
    choose_type = State()

    # Path 1: Mileage Interval
    get_mileage_interval = State()
    get_mileage_interval_start = State()

    # Path 2: Exact Mileage Target
    get_exact_mileage_target = State()

    # Path 3: Time Target
    get_time_target_date = State()
    get_time_start_date = State()

    # Final step
    configure_notifications = State()

    # --- Editing Flow (unchanged for now) ---
    edit_name = State()
    edit_interval_days = State()
    edit_start_date = State()
    edit_interval_km = State()
    edit_last_reset_mileage = State()
    edit_target_mileage = State()