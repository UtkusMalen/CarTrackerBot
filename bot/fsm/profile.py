from aiogram.fsm.state import State, StatesGroup

class ProfileFSM(StatesGroup):
    set_reminder_period = State()