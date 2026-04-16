from __future__ import annotations

from datetime import date, datetime


def date_to_str(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def str_to_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def human_date(value: str) -> str:
    day = str_to_date(value)
    return day.strftime("%d.%m.%Y")
