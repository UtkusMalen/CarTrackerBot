from aiogram.fsm.state import State, StatesGroup

class NotesFSM(StatesGroup):
    add_note = State()
    confirm_delete_note = State()