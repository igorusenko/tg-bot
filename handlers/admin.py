from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Settings
from database.repository import BookingRepository
from keyboards.inline import admin_bookings_keyboard, admin_menu, admin_slots_keyboard, month_calendar
from services.scheduler import ReminderService
from states.booking import AdminStates
from utils.dates import human_date

admin_router = Router()


def _admin_only(callback: CallbackQuery, settings: Settings) -> bool:
    return callback.from_user.id == settings.admin_id


def _calendar_range() -> tuple[date, date]:
    start = date.today()
    end = start + timedelta(days=30)
    return start, end


async def _show_admin_calendar(
    callback: CallbackQuery,
    repo: BookingRepository,
    state: FSMContext,
    state_name,
    callback_prefix: str,
    text: str,
    force_month: date | None = None,
) -> None:
    start, end = _calendar_range()
    month = force_month or date(start.year, start.month, 1)
    # В админ-календаре отображаем все дни месяца, чтобы можно было создавать и закрывать вручную.
    full_days = {
        (start + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((end - start).days + 1)
    }
    keyboard = month_calendar(
        current_month=month,
        enabled_dates=full_days,
        callback_prefix=callback_prefix,
        min_date=start,
        max_date=end,
    )
    await state.set_state(state_name)
    await callback.message.edit_text(text, reply_markup=keyboard)


@admin_router.callback_query(F.data == "menu:admin")
async def open_admin(callback: CallbackQuery, settings: Settings) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("<b>Админ-панель</b>", reply_markup=admin_menu())
    await callback.answer()


@admin_router.callback_query(F.data == "admin:add_day")
async def add_day_start(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_slot,
        "admin:add_day",
        "<b>Выберите дату для добавления рабочего дня</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:add_day:month:"))
async def add_day_month(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, _, month_raw = callback.data.split(":")
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_slot,
        "admin:add_day",
        "<b>Выберите дату для добавления рабочего дня</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:add_day:date:"))
async def add_day_done(callback: CallbackQuery, settings: Settings, repo: BookingRepository) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    await repo.add_working_day(day_date)
    await callback.message.edit_text(
        f"Рабочий день <b>{human_date(day_date)}</b> добавлен.",
        reply_markup=admin_menu(),
    )
    await callback.answer("Готово")


@admin_router.callback_query(F.data == "admin:add_slot")
async def add_slot_start(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_slot,
        "admin:slot_day",
        "<b>Выберите день для добавления слота</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:slot_day:month:"))
async def add_slot_month(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    month_raw = callback.data.split(":")[-1]
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_slot,
        "admin:slot_day",
        "<b>Выберите день для добавления слота</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:slot_day:date:"))
async def add_slot_pick_day(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    await repo.add_working_day(day_date)
    await state.update_data(day_date=day_date)
    await state.set_state(AdminStates.entering_slot_time)
    await callback.message.edit_text(
        f"Введите время для {human_date(day_date)} в формате <b>HH:MM</b>\nНапример: <code>10:30</code>"
    )
    await callback.answer()


@admin_router.message(AdminStates.entering_slot_time)
async def add_slot_done(message: Message, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if message.from_user.id != settings.admin_id:
        return
    time_value = message.text.strip()
    try:
        hours, minutes = map(int, time_value.split(":"))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError
    except Exception:
        await message.answer("Неверный формат. Используйте HH:MM")
        return

    data = await state.get_data()
    day_date = data["day_date"]
    ok = await repo.add_slot(day_date, f"{hours:02d}:{minutes:02d}")
    if not ok:
        await message.answer("Такой слот уже существует.", reply_markup=admin_menu())
        await state.clear()
        return
    await message.answer(
        f"Слот <b>{hours:02d}:{minutes:02d}</b> добавлен на <b>{human_date(day_date)}</b>.",
        reply_markup=admin_menu(),
    )
    await state.clear()


@admin_router.callback_query(F.data == "admin:delete_slot")
async def delete_slot_start(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_delete_slot,
        "admin:delete_slot_day",
        "<b>Выберите день для удаления слота</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:delete_slot_day:month:"))
async def delete_slot_month(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    month_raw = callback.data.split(":")[-1]
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_delete_slot,
        "admin:delete_slot_day",
        "<b>Выберите день для удаления слота</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:delete_slot_day:date:"))
async def delete_slot_pick_day(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    rows = await repo.get_available_slots(day_date)
    if not rows:
        await callback.answer("Нет свободных слотов для удаления", show_alert=True)
        return
    await state.set_state(AdminStates.choosing_slot_for_delete)
    await callback.message.edit_text(
        f"Свободные слоты на {human_date(day_date)}:",
        reply_markup=admin_slots_keyboard(rows),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:delete_slot_id:"))
async def delete_slot_done(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    slot_id = int(callback.data.split(":")[-1])
    await repo.delete_slot(slot_id)
    await state.clear()
    await callback.message.edit_text("Слот удален.", reply_markup=admin_menu())
    await callback.answer()


@admin_router.callback_query(F.data == "admin:close_day")
async def close_day_start(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_close,
        "admin:close_day",
        "<b>Выберите день, который нужно закрыть</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:close_day:month:"))
async def close_day_month(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    month_raw = callback.data.split(":")[-1]
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_close,
        "admin:close_day",
        "<b>Выберите день, который нужно закрыть</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:close_day:date:"))
async def close_day_done(callback: CallbackQuery, settings: Settings, repo: BookingRepository) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    await repo.close_day(day_date)
    await callback.message.edit_text(
        f"День <b>{human_date(day_date)}</b> полностью закрыт.",
        reply_markup=admin_menu(),
    )
    await callback.answer("Готово")


@admin_router.callback_query(F.data == "admin:view_day")
async def view_day_start(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_view,
        "admin:view_day",
        "<b>Выберите дату для просмотра расписания</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:view_day:month:"))
async def view_day_month(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    month_raw = callback.data.split(":")[-1]
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_view,
        "admin:view_day",
        "<b>Выберите дату для просмотра расписания</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:view_day:date:"))
async def view_day_done(callback: CallbackQuery, settings: Settings, repo: BookingRepository, state: FSMContext) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    schedule = await repo.get_schedule_for_day(day_date)
    if not schedule:
        text = f"<b>{human_date(day_date)}</b>\nСлотов нет."
    else:
        lines = [f"<b>Расписание на {human_date(day_date)}</b>"]
        for row in schedule:
            if row["is_available"]:
                lines.append(f"🟢 {row['slot_time']} — свободно")
            else:
                lines.append(
                    f"🔴 {row['slot_time']} — {row.get('full_name', 'занято')} ({row.get('phone', '-')})"
                )
        text = "\n".join(lines)
    await state.clear()
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()


@admin_router.callback_query(F.data == "admin:cancel_booking")
async def cancel_booking_start(
    callback: CallbackQuery,
    settings: Settings,
    repo: BookingRepository,
    state: FSMContext,
) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_cancel_booking,
        "admin:cancel_booking",
        "<b>Выберите дату для отмены записи клиента</b>",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:cancel_booking:month:"))
async def cancel_booking_month(
    callback: CallbackQuery,
    settings: Settings,
    repo: BookingRepository,
    state: FSMContext,
) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    month_raw = callback.data.split(":")[-1]
    year, month = map(int, month_raw.split("-"))
    await _show_admin_calendar(
        callback,
        repo,
        state,
        AdminStates.choosing_day_for_cancel_booking,
        "admin:cancel_booking",
        "<b>Выберите дату для отмены записи клиента</b>",
        force_month=date(year, month, 1),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:cancel_booking:date:"))
async def cancel_booking_pick(
    callback: CallbackQuery,
    settings: Settings,
    repo: BookingRepository,
    state: FSMContext,
) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    day_date = callback.data.split(":")[-1]
    bookings = await repo.get_bookings_for_day(day_date)
    if not bookings:
        await callback.answer("На эту дату нет записей", show_alert=True)
        return
    await state.set_state(AdminStates.choosing_booking_for_cancel)
    await callback.message.edit_text(
        f"Записи на {human_date(day_date)}:",
        reply_markup=admin_bookings_keyboard(bookings),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:cancel_booking_id:"))
async def cancel_booking_done(
    callback: CallbackQuery,
    settings: Settings,
    repo: BookingRepository,
    reminder_service: ReminderService,
    state: FSMContext,
) -> None:
    if not _admin_only(callback, settings):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, booking_id_raw, user_id_raw = callback.data.split(":")
    booking = await repo.cancel_booking_by_id(int(booking_id_raw))
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await reminder_service.remove_for_booking(booking)
    await callback.bot.send_message(
        int(user_id_raw),
        "Ваша запись была отменена администратором. Вы можете выбрать новую дату в боте.",
    )
    await callback.bot.send_message(
        settings.channel_id,
        "<b>Обновление расписания</b>\n"
        "❌ Запись отменена администратором\n"
        f"Дата: <b>{human_date(booking['day_date'])}</b>\n"
        f"Время: <b>{booking['slot_time']}</b>",
    )
    await state.clear()
    await callback.message.edit_text("Запись клиента отменена.", reply_markup=admin_menu())
    await callback.answer("Готово")
