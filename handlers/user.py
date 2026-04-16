from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Settings
from database.repository import BookingRepository
from keyboards.inline import (
    confirm_booking_keyboard,
    main_menu,
    month_calendar,
    my_booking_keyboard,
    portfolio_keyboard,
    slots_keyboard,
    subscription_keyboard,
)
from services.scheduler import ReminderService
from states.booking import BookingStates
from utils.dates import human_date
from utils.subscription import is_subscribed

user_router = Router()


def _calendar_range() -> tuple[date, date]:
    start = date.today()
    end = start + timedelta(days=30)
    return start, end


async def _show_main_menu(message: Message, settings: Settings) -> None:
    is_admin = bool(message.from_user) and message.from_user.id in settings.admin_ids
    await message.answer(
        "<b>Добро пожаловать в бот записи мастера по маникюру</b>\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu(is_admin=is_admin),
    )


async def _show_calendar(
    callback: CallbackQuery,
    repo: BookingRepository,
    state: FSMContext,
    callback_prefix: str = "book",
    force_month: date | None = None,
) -> None:
    start, end = _calendar_range()
    month = force_month or date(start.year, start.month, 1)
    available_days = await repo.get_available_days(start, end)
    keyboard = month_calendar(
        current_month=month,
        enabled_dates=available_days,
        callback_prefix=callback_prefix,
        min_date=start,
        max_date=end,
    )
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        "<b>Выберите дату для записи:</b>",
        reply_markup=keyboard,
    )


@user_router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings) -> None:
    await _show_main_menu(message, settings)


@user_router.callback_query(F.data == "menu:back")
async def menu_back(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    is_admin = callback.from_user.id in settings.admin_ids
    await callback.message.edit_text(
        "<b>Главное меню</b>\nВыберите действие:",
        reply_markup=main_menu(is_admin=is_admin),
    )
    await callback.answer()


@user_router.callback_query(F.data == "ignore")
async def ignore_click(callback: CallbackQuery) -> None:
    await callback.answer()


@user_router.callback_query(F.data == "menu:prices")
async def prices(callback: CallbackQuery, settings: Settings) -> None:
    is_admin = callback.from_user.id in settings.admin_ids
    await callback.message.edit_text(
        "<b>Прайсы</b>\n\n"
        "Френч — <b>1000₽</b>\n"
        "Квадрат — <b>500₽</b>",
        reply_markup=main_menu(is_admin=is_admin),
    )
    await callback.answer()


@user_router.callback_query(F.data == "menu:portfolio")
async def portfolio(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "<b>Портфолио</b>\nНажмите на кнопку ниже:",
        reply_markup=portfolio_keyboard(),
    )
    await callback.answer()


@user_router.callback_query(F.data == "menu:book")
async def start_booking(
    callback: CallbackQuery,
    state: FSMContext,
    repo: BookingRepository,
    settings: Settings,
) -> None:
    if await repo.user_has_booking(callback.from_user.id):
        await callback.message.edit_text(
            "У вас уже есть активная запись. Сначала отмените её в разделе <b>Моя запись</b>.",
            reply_markup=my_booking_keyboard(),
        )
        await callback.answer()
        return

    subscribed, reason = await is_subscribed(callback.bot, settings.channel_id, callback.from_user.id)
    if not subscribed:
        text = "Для записи необходимо подписаться на канал"
        if reason:
            text += f"\n\n<i>{reason}</i>"
        await callback.message.edit_text(
            text,
            reply_markup=subscription_keyboard(settings.channel_link),
        )
        await callback.answer()
        return

    await _show_calendar(callback, repo, state)
    await callback.answer()


@user_router.callback_query(F.data == "sub:check")
async def check_subscription(
    callback: CallbackQuery,
    state: FSMContext,
    repo: BookingRepository,
    settings: Settings,
) -> None:
    subscribed, reason = await is_subscribed(callback.bot, settings.channel_id, callback.from_user.id)
    if not subscribed:
        await callback.answer(reason or "Подписка пока не найдена", show_alert=True)
        return

    await callback.answer("Подписка подтверждена")
    await _show_calendar(callback, repo, state)


@user_router.callback_query(F.data.startswith("book:month:"))
async def switch_month(callback: CallbackQuery, repo: BookingRepository, state: FSMContext) -> None:
    _, _, month_value = callback.data.split(":")
    year, month = map(int, month_value.split("-"))
    await _show_calendar(callback, repo, state, force_month=date(year, month, 1))
    await callback.answer()


@user_router.callback_query(F.data.startswith("book:date:"))
async def pick_date(callback: CallbackQuery, repo: BookingRepository, state: FSMContext) -> None:
    _, _, day_date = callback.data.split(":")
    slots = await repo.get_available_slots(day_date)
    if not slots:
        await callback.answer("На эту дату нет свободных слотов", show_alert=True)
        return
    await state.update_data(day_date=day_date)
    await state.set_state(BookingStates.choosing_time)
    await callback.message.edit_text(
        f"<b>Дата:</b> {human_date(day_date)}\nВыберите время:",
        reply_markup=slots_keyboard(slots),
    )
    await callback.answer()


@user_router.callback_query(F.data == "book:back_to_dates")
async def back_to_dates(callback: CallbackQuery, repo: BookingRepository, state: FSMContext) -> None:
    await _show_calendar(callback, repo, state)
    await callback.answer()


@user_router.callback_query(F.data.startswith("book:slot:"))
async def pick_slot(callback: CallbackQuery, repo: BookingRepository, state: FSMContext) -> None:
    _, _, slot_id_raw = callback.data.split(":")
    slot_id = int(slot_id_raw)
    slot = await repo.get_slot(slot_id)
    if not slot or not slot["is_available"]:
        await callback.answer("Слот уже занят", show_alert=True)
        return
    await state.update_data(slot_id=slot_id, day_date=slot["day_date"], slot_time=slot["slot_time"])
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text(
        f"<b>Вы выбрали:</b> {human_date(slot['day_date'])} в {slot['slot_time']}\n\n"
        "Введите ваше <b>имя</b>:",
    )
    await callback.answer()


@user_router.message(BookingStates.entering_name)
async def get_name(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("Введите корректное имя.")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer("Введите номер телефона (например, +79991234567):")


@user_router.message(BookingStates.entering_phone)
async def get_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if len(phone) < 10:
        await message.answer("Введите корректный номер телефона.")
        return
    await state.update_data(phone=phone)
    data = await state.get_data()
    await state.set_state(BookingStates.confirming)
    await message.answer(
        "<b>Проверьте данные:</b>\n"
        f"Дата: <b>{human_date(data['day_date'])}</b>\n"
        f"Время: <b>{data['slot_time']}</b>\n"
        f"Имя: <b>{data['full_name']}</b>\n"
        f"Телефон: <b>{phone}</b>",
        reply_markup=confirm_booking_keyboard(),
    )


@user_router.callback_query(F.data == "book:confirm", BookingStates.confirming)
async def confirm_booking(
    callback: CallbackQuery,
    state: FSMContext,
    repo: BookingRepository,
    settings: Settings,
    reminder_service: ReminderService,
) -> None:
    user_id = callback.from_user.id
    if await repo.user_has_booking(user_id):
        await callback.answer("У вас уже есть запись", show_alert=True)
        return

    data = await state.get_data()
    booking = await repo.create_booking(
        user_id=user_id,
        username=callback.from_user.username,
        full_name=data["full_name"],
        phone=data["phone"],
        slot_id=int(data["slot_id"]),
    )
    if not booking:
        await callback.answer("Не удалось забронировать слот. Выберите другое время.", show_alert=True)
        return

    await reminder_service.schedule_for_booking(booking)

    user_text = (
        "<b>Запись подтверждена ✅</b>\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Имя: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>"
    )
    owner_text = (
        "<b>Новая запись</b>\n"
        f"Клиент: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"User ID: <code>{booking['user_id']}</code>"
    )
    channel_text = (
        "<b>Обновление расписания</b>\n"
        "✅ Новая запись\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Клиент: <b>{booking['full_name']}</b>"
    )
    await callback.message.edit_text(user_text, reply_markup=my_booking_keyboard())
    for admin_id in settings.admin_ids:
        await callback.bot.send_message(admin_id, owner_text)
    await callback.bot.send_message(settings.channel_id, channel_text)
    await state.clear()
    await callback.answer()


@user_router.callback_query(F.data == "menu:my_booking")
async def my_booking(callback: CallbackQuery, repo: BookingRepository, settings: Settings) -> None:
    booking = await repo.get_user_booking(callback.from_user.id)
    if not booking:
        is_admin = callback.from_user.id in settings.admin_ids
        await callback.message.edit_text(
            "У вас пока нет активной записи.",
            reply_markup=main_menu(is_admin=is_admin),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "<b>Ваша запись:</b>\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>\n"
        f"Имя: <b>{booking['full_name']}</b>\n"
        f"Телефон: <b>{booking['phone']}</b>",
        reply_markup=my_booking_keyboard(),
    )
    await callback.answer()


@user_router.callback_query(F.data == "book:cancel")
async def cancel_booking(
    callback: CallbackQuery,
    repo: BookingRepository,
    settings: Settings,
    reminder_service: ReminderService,
) -> None:
    booking = await repo.cancel_booking(callback.from_user.id)
    if not booking:
        await callback.answer("Активной записи нет", show_alert=True)
        return

    await reminder_service.remove_for_booking(booking)
    is_admin = callback.from_user.id in settings.admin_ids
    await callback.message.edit_text("Запись успешно отменена.", reply_markup=main_menu(is_admin=is_admin))
    await callback.bot.send_message(
        settings.channel_id,
        "<b>Обновление расписания</b>\n"
        "❌ Запись отменена\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>",
    )
    await callback.answer()
