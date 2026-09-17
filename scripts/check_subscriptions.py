"""Bot bazasidagi har bir foydalanuvchining kanalga a'zoligini tekshiradi (bazaga hech narsa yozmaydi).

Ishlatish (server, loyiha papkasida):
    docker compose exec -T bot python - < scripts/check_subscriptions.py

Har bir foydalanuvchi uchun bitta Telegram so'rovi ketadi, shuning uchun 2000 ta foydalanuvchi ~2 daqiqa oladi.
"""
import asyncio
import sys
from collections import Counter

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from bot.config import settings
from bot.db import Database

DELAY = 0.06  # Telegram limiti ~30 so'rov/soniya
MEMBER_STATUSES = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}

SUBSCRIBED = "obuna"
NOT_SUBSCRIBED = "obuna emas"
KICKED = "kanaldan chetlatilgan"
DELETED = "akkaunt topilmadi"
ERROR = "xato"

ORDER = [SUBSCRIBED, NOT_SUBSCRIBED, KICKED, DELETED, ERROR]


async def member_status(bot: Bot, user_id: int) -> str:
    try:
        member = await bot.get_chat_member(settings.channel_id, user_id)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        return await member_status(bot, user_id)
    except TelegramAPIError as e:
        text = str(e).lower()
        return DELETED if "not found" in text or "invalid" in text else ERROR

    if member.status == ChatMemberStatus.RESTRICTED:
        return SUBSCRIBED if member.is_member else NOT_SUBSCRIBED
    if member.status == ChatMemberStatus.KICKED:
        return KICKED
    return SUBSCRIBED if member.status in MEMBER_STATUSES else NOT_SUBSCRIBED


async def check(bot: Bot, db: Database, progress_every: int = 200) -> tuple[Counter, Counter, list]:
    cur = await db.conn.execute(
        "SELECT u.id, u.username, u.tg_name, a.user_id IS NOT NULL AS applied "
        "FROM users u LEFT JOIN applications a ON a.user_id = u.id ORDER BY u.created_at"
    )
    rows = await cur.fetchall()

    total, applicants, lost_applicants = Counter(), Counter(), []
    for i, row in enumerate(rows, 1):
        status = await member_status(bot, row["id"])
        total[status] += 1
        if row["applied"]:
            applicants[status] += 1
            if status != SUBSCRIBED:
                lost_applicants.append((row["id"], row["username"], row["tg_name"], status))
        if progress_every and i % progress_every == 0:
            print(f"  ...{i}/{len(rows)}", file=sys.stderr)
        await asyncio.sleep(DELAY)
    return total, applicants, lost_applicants


def report(total: Counter, applicants: Counter, lost: list) -> None:
    users = sum(total.values())
    print(f"\n== Bot bazasidagi foydalanuvchilar: {users}")
    for status in ORDER:
        if total[status]:
            print(f"  {status:<22} {total[status]:>6}  ({total[status] * 100 // max(users, 1)}%)")

    applied = sum(applicants.values())
    print(f"\n== Ariza topshirganlar: {applied}")
    for status in ORDER:
        if applicants[status]:
            print(f"  {status:<22} {applicants[status]:>6}")

    if lost:
        print(f"\n== Ariza topshirib, endi kanalda yo'qlar: {len(lost)}")
        for user_id, username, name, status in lost[:30]:
            print(f"  {user_id}  @{username or '-'}  {name or ''}  — {status}")
        if len(lost) > 30:
            print(f"  ...va yana {len(lost) - 30} ta")

    print(
        f"\nEslatma: kanaldagi a'zolar soni bilan solishtiring. Kanalda bor, lekin bu ro'yxatda yo'q odamlar — "
        f"botdan foydalanmay, to'g'ridan-to'g'ri kanalga obuna bo'lganlar."
    )


async def main() -> None:
    db = Database(settings.db_path)
    await db.connect()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        report(*await check(bot, db))
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
