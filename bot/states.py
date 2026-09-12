from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    full_name = State()
    phone = State()
    cv = State()
    essay = State()
    answer = State()
    confirm = State()
