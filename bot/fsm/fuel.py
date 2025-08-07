from aiogram.fsm.state import StatesGroup, State

class FuelFSM(StatesGroup):
    get_tank_volume = State()
    entry_menu = State()
    get_mileage = State()
    get_liters = State()
    get_sum = State()
    get_date = State()