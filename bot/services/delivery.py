"""Tayyor arizani admin guruhiga va Google Sheets'ga yetkazish."""
import html
import logging

from aiogram import Bot

from bot import texts
from bot.config import settings
from bot.db import Application, Database
from bot.services.sheets import Sheets

log = logging.getLogger(__name__)

TG_TEXT_LIMIT = 4096


def admin_message_link(msg_id: int) -> str | None:
    chat = str(settings.admin_chat_id)
    if not chat.startswith("-100"):  # havolalar faqat superguruh/kanal uchun ishlaydi
        return None
    return f"https://t.me/c/{chat[4:]}/{msg_id}"


def _chunks(text: str, size: int = TG_TEXT_LIMIT) -> list[str]:
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = text.rfind(" ", 0, size)
        if cut <= 0:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    parts.append(text)
    return parts


async def _send_to_admin_group(bot: Bot, app: Application) -> int:
    name = html.escape(app.full_name)
    user_link = f'<a href="tg://user?id={app.user_id}">{app.user_id}</a>'
    if app.username:
        user_link += f" (@{html.escape(app.username)})"
    caption = texts.ADMIN_APPLICATION.format(
        full_name=name, phone=html.escape(app.phone), user_link=user_link, referrals=app.referrals,
    )
    doc = await bot.send_document(settings.admin_chat_id, app.cv_file_id, caption=caption)

    # Uzun matnlar oddiy matn sifatida (HTML emas) — bo'laklarga ajratilganda teglar buzilmasin
    body = f"📝 ESSE:\n{app.essay}\n\n📚 KITOBLAR HAQIDA:\n{app.answer}"
    for part in _chunks(body):
        await bot.send_message(settings.admin_chat_id, part, parse_mode=None, reply_to_message_id=doc.message_id)
    return doc.message_id


async def deliver(bot: Bot, db: Database, sheets: Sheets | None, app: Application) -> None:
    if app.admin_msg_id is None:
        try:
            app.admin_msg_id = await _send_to_admin_group(bot, app)
            await db.set_admin_msg_id(app.user_id, app.admin_msg_id)
        except Exception:
            log.exception("Ariza admin guruhiga yuborilmadi (user %s)", app.user_id)

    if sheets and not app.sheet_synced:
        link = admin_message_link(app.admin_msg_id) if app.admin_msg_id else None
        try:
            await sheets.append(app, link)
            await db.mark_synced(app.user_id)
            app.sheet_synced = True
        except Exception:
            log.exception("Ariza Google Sheets'ga yozilmadi (user %s)", app.user_id)


async def deliver_pending(bot: Bot, db: Database, sheets: Sheets | None) -> int:
    """Oldin yetkazilmay qolgan arizalarni qayta yuboradi. Qaytaradi: nechta ko'rib chiqildi."""
    pending = [
        a for a in await db.pending_applications() if a.admin_msg_id is None or (sheets and not a.sheet_synced)
    ]
    for app in pending:
        await deliver(bot, db, sheets, app)
    return len(pending)
