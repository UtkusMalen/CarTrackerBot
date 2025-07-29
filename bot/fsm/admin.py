from aiogram.fsm.state import StatesGroup, State


class AdminFSM(StatesGroup):
    """FSM for admin commands."""
    get_message = State()
    confirm_mailing = State()