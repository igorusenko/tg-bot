from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


class AdminStates(StatesGroup):
    choosing_day_for_slot = State()
    entering_slot_time = State()
    choosing_day_for_delete_slot = State()
    choosing_slot_for_delete = State()
    choosing_day_for_view = State()
    choosing_day_for_close = State()
    choosing_day_for_cancel_booking = State()
    choosing_booking_for_cancel = State()
