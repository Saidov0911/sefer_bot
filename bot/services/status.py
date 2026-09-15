"""Ariza holatini o'zgartirish (bot va web paneldan umumiy)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from bot import texts
from bot.db import Database

log = logging.getLogger(__name__)


async def change_status(bot: Bot, db: Database, user_id: int, status: str, notify: bool) -> tuple[bool, bool]:
    """Qaytaradi: (holat o'zgardimi, foydalanuvchiga xabar yetib bordimi)."""
    if not await db.set_status(user_id, status):
        return False, False
    text = texts.STATUS_NOTIFY.get(status)
    if not (notify and text):
        return True, False
    try:
        await bot.send_message(user_id, text)
    except TelegramForbiddenError:
        await db.set_user_active(user_id, False)
        return True, False
    except TelegramAPIError:
        log.exception("Holat xabari yuborilmadi (user %s)", user_id)
        return True, False
    return True, True
