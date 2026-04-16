import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_id: int
    channel_id: str
    channel_link: str
    db_path: str


def load_config() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "")
    admin_id = os.getenv("ADMIN_ID", "0")
    channel_id = os.getenv("CHANNEL_ID", "0")
    channel_link = os.getenv("CHANNEL_LINK", "")
    db_path = os.getenv("DB_PATH", "bot.db")

    if not bot_token:
        raise ValueError("BOT_TOKEN не указан в .env")
    if not channel_link:
        raise ValueError("CHANNEL_LINK не указан в .env")

    return Settings(
        bot_token=bot_token,
        admin_id=int(admin_id),
        channel_id=channel_id.strip(),
        channel_link=channel_link,
        db_path=db_path,
    )
