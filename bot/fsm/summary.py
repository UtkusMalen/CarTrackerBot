from aiogram.fsm.state import State, StatesGroup

class SummaryFSM(StatesGroup):
    """FSM for filling car summary."""
    get_value = State()
    get_option_value = State()