from aiogram.fsm.state import State, StatesGroup

class RegistrationFSM(StatesGroup):
    """FSM for user and car registration."""
    car_name = State()
    car_mileage = State()
    last_oil_change = State()
    oil_change_interval = State()