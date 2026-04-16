from __future__ import annotations

import calendar
from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.dates import date_to_str


def main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Записаться", callback_data="menu:book")],
        [InlineKeyboardButton(text="Моя запись", callback_data="menu:my_booking")],
        [InlineKeyboardButton(text="Прайсы", callback_data="menu:prices")],
        [InlineKeyboardButton(text="Портфолио", callback_data="menu:portfolio")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="Админ-панель", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться", url=channel_link)],
            [InlineKeyboardButton(text="Проверить подписку", callback_data="sub:check")],
            [InlineKeyboardButton(text="Назад", callback_data="menu:back")],
        ]
    )


def portfolio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Смотреть портфолио",
                    url="https://ru.pinterest.com/crystalwithluv/_created/",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="menu:back")],
        ]
    )


def month_calendar(
    current_month: date,
    enabled_dates: set[str],
    callback_prefix: str,
    min_date: date,
    max_date: date,
) -> InlineKeyboardMarkup:
    year, month = current_month.year, current_month.month
    month_name = f"{calendar.month_name[month]} {year}"

    buttons = [[InlineKeyboardButton(text=month_name, callback_data="ignore")]]
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    buttons.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    month_matrix = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    for week in month_matrix:
        row = []
        for day in week:
            if day.month != month or day < min_date or day > max_date:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue

            key = date_to_str(day)
            if key in enabled_dates:
                row.append(
                    InlineKeyboardButton(
                        text=str(day.day),
                        callback_data=f"{callback_prefix}:date:{key}",
                    )
                )
            else:
                row.append(InlineKeyboardButton(text=f"{day.day}❌", callback_data="ignore"))
        buttons.append(row)

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month = date(year, month, calendar.monthrange(year, month)[1]) + timedelta(days=1)

    nav = []
    if prev_month >= date(min_date.year, min_date.month, 1):
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{callback_prefix}:month:{prev_month.year}-{prev_month.month}",
            )
        )
    nav.append(InlineKeyboardButton(text="Назад", callback_data="menu:back"))
    if date(next_month.year, next_month.month, 1) <= date(max_date.year, max_date.month, 1):
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{callback_prefix}:month:{next_month.year}-{next_month.month}",
            )
        )
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def slots_keyboard(slots: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🕒 {slot_time}", callback_data=f"book:slot:{slot_id}")]
        for slot_id, slot_time in slots
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="book:back_to_dates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_booking_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="book:confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="menu:back")],
        ]
    )


def my_booking_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отменить запись", callback_data="book:cancel")],
            [InlineKeyboardButton(text="Назад", callback_data="menu:back")],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить рабочий день", callback_data="admin:add_day")],
            [InlineKeyboardButton(text="Добавить слот", callback_data="admin:add_slot")],
            [InlineKeyboardButton(text="Удалить слот", callback_data="admin:delete_slot")],
            [InlineKeyboardButton(text="Закрыть день", callback_data="admin:close_day")],
            [InlineKeyboardButton(text="Расписание на дату", callback_data="admin:view_day")],
            [InlineKeyboardButton(text="Отменить запись клиента", callback_data="admin:cancel_booking")],
            [InlineKeyboardButton(text="Назад", callback_data="menu:back")],
        ]
    )


def admin_slots_keyboard(slots: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Удалить {slot_time}", callback_data=f"admin:delete_slot_id:{slot_id}")]
        for slot_id, slot_time in slots
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bookings_keyboard(bookings: list[tuple[int, int, str, str, str]]) -> InlineKeyboardMarkup:
    rows = []
    for booking_id, user_id, full_name, phone, slot_time in bookings:
        title = f"{slot_time} | {full_name} ({phone})"
        rows.append(
            [InlineKeyboardButton(text=title[:64], callback_data=f"admin:cancel_booking_id:{booking_id}:{user_id}")]
        )
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
