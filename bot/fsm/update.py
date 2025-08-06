from aiogram.fsm.state import State, StatesGroup

class UpdateFSM(StatesGroup):
    """FSM for updating profile."""
    update_mileage = State()