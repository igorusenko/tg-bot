from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


async def is_subscribed(bot: Bot, channel_id: str, user_id: int) -> tuple[bool, str | None]:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramForbiddenError:
        return (
            False,
            "Бот не имеет доступа к каналу. Добавьте бота в канал и выдайте права администратора.",
        )
    except TelegramBadRequest:
        return (
            False,
            "Не удалось проверить подписку. Проверьте CHANNEL_ID (обычно это -100...).",
        )
    except Exception:
        return (False, "Временная ошибка проверки подписки. Попробуйте еще раз.")

    is_ok = member.status in {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.RESTRICTED,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    }
    return (is_ok, None)
