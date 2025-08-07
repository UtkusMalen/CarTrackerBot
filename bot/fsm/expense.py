from aiogram.fsm.state import State, StatesGroup

class ExpenseFSM(StatesGroup):
    get_category = State()
    get_amount = State()
    get_mileage = State()
    get_description = State()
    get_date = State()
    create_category_name = State()