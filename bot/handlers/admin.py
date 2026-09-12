from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.db import Database
from bot.services.delivery import deliver_pending
from bot.services.sheets import Sheets

router = Router()
router.message.filter(F.from_user.id.in_(settings.admin_id_set))


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database):
    s = await db.stats()
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🔗 Taklif orqali kelgan (kanalga a’zo): <b>{s['referred']}</b>\n"
        f"📝 Arizalar: <b>{s['applications']}</b>\n"
        f"⚠️ Guruhga yetib bormagan: <b>{s['not_in_group']}</b>\n"
        f"⚠️ Sheets'ga yozilmagan: <b>{s['not_in_sheet']}</b>"
    )


@router.message(Command("sync"))
async def cmd_sync(message: Message, bot: Bot, db: Database, sheets: Sheets | None):
    count = await deliver_pending(bot, db, sheets)
    await message.answer(f"🔄 Qayta yuborildi: {count} ta ariza. Natijani /stats orqali tekshiring.")
