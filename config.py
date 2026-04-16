import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    # List of administrator Telegram IDs.
    # Stored in environment variable `ADMIN_ID` as comma/space-separated values.
    admin_ids: list[int]
    channel_id: str
    channel_link: str
    db_path: str


def load_config() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "")
    raw_admin_ids = os.getenv("ADMIN_ID", "").strip()
    channel_id = os.getenv("CHANNEL_ID", "0")
    channel_link = os.getenv("CHANNEL_LINK", "")
    db_path = os.getenv("DB_PATH", "bot.db")

    if not bot_token:
        raise ValueError("BOT_TOKEN не указан в .env")
    if not raw_admin_ids:
        raise ValueError("ADMIN_ID не указан в .env")
    if not channel_link:
        raise ValueError("CHANNEL_LINK не указан в .env")

    # Support multiple IDs: "123,456" or "123 456" or "123;456"
    parts = [p for p in re.split(r"[,\s;]+", raw_admin_ids) if p]
    admin_ids = sorted({int(p) for p in parts})
    if not admin_ids:
        raise ValueError("ADMIN_ID не содержит корректных чисел")

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        channel_id=channel_id.strip(),
        channel_link=channel_link,
        db_path=db_path,
    )
