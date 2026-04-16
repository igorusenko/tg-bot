from __future__ import annotations

from datetime import date, timedelta

import aiosqlite

from database.db import Database
from utils.dates import date_to_str


class BookingRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add_working_day(self, day_date: str) -> None:
        await self.db.execute(
            """
            INSERT INTO working_days(day_date, is_closed)
            VALUES(?, 0)
            ON CONFLICT(day_date) DO UPDATE SET is_closed = 0;
            """,
            (day_date,),
        )

    async def close_day(self, day_date: str) -> None:
        await self.db.execute(
            "UPDATE working_days SET is_closed = 1 WHERE day_date = ?;",
            (day_date,),
        )
        await self.db.execute(
            "UPDATE time_slots SET is_available = 0 WHERE day_date = ?;",
            (day_date,),
        )

    async def add_slot(self, day_date: str, slot_time: str) -> bool:
        try:
            await self.db.execute(
                """
                INSERT INTO time_slots(day_date, slot_time, is_available)
                VALUES(?, ?, 1);
                """,
                (day_date, slot_time),
            )
            return True
        except Exception:
            return False

    async def delete_slot(self, slot_id: int) -> None:
        await self.db.execute("DELETE FROM time_slots WHERE id = ?;", (slot_id,))

    async def get_available_days(self, start: date, end: date) -> set[str]:
        rows = await self.db.fetchall(
            """
            SELECT DISTINCT ts.day_date
            FROM time_slots ts
            JOIN working_days wd ON wd.day_date = ts.day_date
            WHERE ts.is_available = 1
              AND wd.is_closed = 0
              AND ts.day_date BETWEEN ? AND ?
            ORDER BY ts.day_date;
            """,
            (date_to_str(start), date_to_str(end)),
        )
        return {row["day_date"] for row in rows}

    async def get_available_slots(self, day_date: str) -> list[tuple[int, str]]:
        rows = await self.db.fetchall(
            """
            SELECT id, slot_time
            FROM time_slots
            WHERE day_date = ? AND is_available = 1
            ORDER BY slot_time;
            """,
            (day_date,),
        )
        return [(row["id"], row["slot_time"]) for row in rows]

    async def get_slot(self, slot_id: int) -> dict | None:
        row = await self.db.fetchone(
            "SELECT id, day_date, slot_time, is_available FROM time_slots WHERE id = ?;",
            (slot_id,),
        )
        return dict(row) if row else None

    async def user_has_booking(self, user_id: int) -> bool:
        row = await self.db.fetchone("SELECT id FROM bookings WHERE user_id = ?;", (user_id,))
        return row is not None

    async def get_user_booking(self, user_id: int) -> dict | None:
        row = await self.db.fetchone(
            """
            SELECT id, user_id, username, full_name, phone, day_date, slot_time, reminder_job_id
            FROM bookings
            WHERE user_id = ?;
            """,
            (user_id,),
        )
        return dict(row) if row else None

    async def create_booking(
        self,
        user_id: int,
        username: str | None,
        full_name: str,
        phone: str,
        slot_id: int,
        reminder_job_id: str | None = None,
    ) -> dict | None:
        slot = await self.get_slot(slot_id)
        if not slot or not slot["is_available"]:
            return None

        day_row = await self.db.fetchone(
            "SELECT is_closed FROM working_days WHERE day_date = ?;",
            (slot["day_date"],),
        )
        if not day_row or day_row["is_closed"]:
            return None

        if await self.user_has_booking(user_id):
            return None

        try:
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON;")
                db.row_factory = aiosqlite.Row
                await db.execute("BEGIN IMMEDIATE;")
                cur = await db.execute(
                    "UPDATE time_slots SET is_available = 0 WHERE id = ? AND is_available = 1;",
                    (slot_id,),
                )
                if cur.rowcount == 0:
                    await db.rollback()
                    return None
                await cur.close()

                await db.execute(
                    """
                    INSERT INTO bookings(user_id, username, full_name, phone, day_date, slot_time, reminder_job_id)
                    VALUES(?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        user_id,
                        username,
                        full_name,
                        phone,
                        slot["day_date"],
                        slot["slot_time"],
                        reminder_job_id,
                    ),
                )
                await db.commit()
        except Exception:
            return None

        return await self.get_user_booking(user_id)

    async def set_reminder_job_id(self, booking_id: int, reminder_job_id: str | None) -> None:
        await self.db.execute(
            "UPDATE bookings SET reminder_job_id = ? WHERE id = ?;",
            (reminder_job_id, booking_id),
        )

    async def cancel_booking(self, user_id: int) -> dict | None:
        booking = await self.get_user_booking(user_id)
        if not booking:
            return None

        row = await self.db.fetchone(
            "SELECT id FROM time_slots WHERE day_date = ? AND slot_time = ?;",
            (booking["day_date"], booking["slot_time"]),
        )

        await self.db.execute("DELETE FROM bookings WHERE user_id = ?;", (user_id,))
        if row:
            await self.db.execute(
                "UPDATE time_slots SET is_available = 1 WHERE id = ?;",
                (row["id"],),
            )
        return booking

    async def cancel_booking_by_id(self, booking_id: int) -> dict | None:
        row = await self.db.fetchone(
            """
            SELECT id, user_id, username, full_name, phone, day_date, slot_time, reminder_job_id
            FROM bookings
            WHERE id = ?;
            """,
            (booking_id,),
        )
        if not row:
            return None
        booking = dict(row)

        slot = await self.db.fetchone(
            "SELECT id FROM time_slots WHERE day_date = ? AND slot_time = ?;",
            (booking["day_date"], booking["slot_time"]),
        )
        await self.db.execute("DELETE FROM bookings WHERE id = ?;", (booking_id,))
        if slot:
            await self.db.execute("UPDATE time_slots SET is_available = 1 WHERE id = ?;", (slot["id"],))
        return booking

    async def get_schedule_for_day(self, day_date: str) -> list[dict]:
        rows = await self.db.fetchall(
            """
            SELECT ts.slot_time, ts.is_available, b.full_name, b.phone, b.user_id
            FROM time_slots ts
            LEFT JOIN bookings b ON b.day_date = ts.day_date AND b.slot_time = ts.slot_time
            WHERE ts.day_date = ?
            ORDER BY ts.slot_time;
            """,
            (day_date,),
        )
        return [dict(row) for row in rows]

    async def get_bookings_for_day(self, day_date: str) -> list[tuple[int, int, str, str, str]]:
        rows = await self.db.fetchall(
            """
            SELECT id, user_id, full_name, phone, slot_time
            FROM bookings
            WHERE day_date = ?
            ORDER BY slot_time;
            """,
            (day_date,),
        )
        return [
            (row["id"], row["user_id"], row["full_name"], row["phone"], row["slot_time"])
            for row in rows
        ]

    async def get_all_bookings(self) -> list[dict]:
        rows = await self.db.fetchall(
            """
            SELECT id, user_id, day_date, slot_time, reminder_job_id
            FROM bookings;
            """
        )
        return [dict(row) for row in rows]

    async def ensure_month_days(self) -> None:
        today = date.today()
        for i in range(31):
            await self.add_working_day(date_to_str(today + timedelta(days=i)))
