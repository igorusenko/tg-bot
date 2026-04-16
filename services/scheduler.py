from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.repository import BookingRepository


class ReminderService:
    def __init__(self, scheduler: AsyncIOScheduler, bot: Bot, repo: BookingRepository) -> None:
        self.scheduler = scheduler
        self.bot = bot
        self.repo = repo

    @staticmethod
    def _job_id(booking_id: int) -> str:
        return f"booking_reminder_{booking_id}"

    async def schedule_for_booking(self, booking: dict) -> str | None:
        booking_dt = datetime.strptime(
            f"{booking['day_date']} {booking['slot_time']}",
            "%Y-%m-%d %H:%M",
        )
        remind_at = booking_dt - timedelta(hours=24)
        if remind_at <= datetime.now():
            return None

        job_id = self._job_id(booking["id"])
        self.scheduler.add_job(
            self.send_reminder,
            trigger="date",
            run_date=remind_at,
            id=job_id,
            replace_existing=True,
            kwargs={"user_id": booking["user_id"], "slot_time": booking["slot_time"]},
        )
        await self.repo.set_reminder_job_id(booking["id"], job_id)
        return job_id

    async def remove_for_booking(self, booking: dict) -> None:
        job_id = booking.get("reminder_job_id")
        if job_id:
            job = self.scheduler.get_job(job_id)
            if job:
                job.remove()

    async def restore_tasks(self) -> None:
        bookings = await self.repo.get_all_bookings()
        for booking in bookings:
            await self.schedule_for_booking(booking)

    async def send_reminder(self, user_id: int, slot_time: str) -> None:
        text = (
            f"Напоминаем, что вы записаны на наращивание ресниц завтра в <b>{slot_time}</b>.\n"
            "Ждём вас ❤️"
        )
        await self.bot.send_message(chat_id=user_id, text=text)
