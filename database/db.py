from __future__ import annotations

import aiosqlite


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS working_days (
                    day_date TEXT PRIMARY KEY,
                    is_closed INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day_date TEXT NOT NULL,
                    slot_time TEXT NOT NULL,
                    is_available INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(day_date, slot_time),
                    FOREIGN KEY(day_date) REFERENCES working_days(day_date) ON DELETE CASCADE
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    day_date TEXT NOT NULL,
                    slot_time TEXT NOT NULL,
                    reminder_job_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_slots_day ON time_slots(day_date);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bookings_day_time ON bookings(day_date, slot_time);"
            )
            await db.commit()

    async def execute(self, query: str, params: tuple = ()) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(query, params)
            await db.commit()

    async def fetchone(self, query: str, params: tuple = ()) -> aiosqlite.Row | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            await cursor.close()
            return row

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
            return rows
