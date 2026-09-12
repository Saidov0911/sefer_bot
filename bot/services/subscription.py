import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

from bot.config import settings

log = logging.getLogger(__name__)

_MEMBER_STATUSES = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(settings.channel_id, user_id)
    except TelegramAPIError:
        # Odatda bot kanalda admin emasligini bildiradi — hamma bloklanib qolmasligi uchun logga yozamiz
        log.exception("Kanal a'zoligini tekshirib bo'lmadi (bot %s kanalida adminmi?)", settings.channel_id)
        return False
    subscribed = member.is_member if member.status == ChatMemberStatus.RESTRICTED else member.status in _MEMBER_STATUSES
    # Eslatma: kanal egasi va adminlari ham a'zo hisoblanadi (status: creator/administrator)
    log.info("Obuna tekshiruvi: user=%s status=%s -> %s", user_id, member.status, subscribed)
    return subscribed
