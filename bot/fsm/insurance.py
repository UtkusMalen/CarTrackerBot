from aiogram.fsm.state import State, StatesGroup

class InsuranceFSM(StatesGroup):
    get_duration = State()
    get_start_date = State()