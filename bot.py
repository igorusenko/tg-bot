import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Settings, load_config
from database.db import Database
from database.repository import BookingRepository
from handlers import admin_router, user_router
from services.scheduler import ReminderService


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings: Settings = load_config()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    db = Database(settings.db_path)
    await db.init()
    repo = BookingRepository(db)
    await repo.ensure_month_days()

    scheduler = AsyncIOScheduler()
    reminder_service = ReminderService(scheduler=scheduler, bot=bot, repo=repo)
    scheduler.start()
    await reminder_service.restore_tasks()

    dp["settings"] = settings
    dp["repo"] = repo
    dp["reminder_service"] = reminder_service

    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
