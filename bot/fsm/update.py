from aiogram.fsm.state import State, StatesGroup

class UpdateFSM(StatesGroup):
    """FSM for updating profile."""
    update_mileage = State()
    update_reminder_interval = State()
    confirm_oil_reset = State()