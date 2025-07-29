from aiogram.fsm.state import State, StatesGroup

class ReminderFSM(StatesGroup):
    set_name = State()
    set_interval = State()
    set_last_reset_mileage = State()