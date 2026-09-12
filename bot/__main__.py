import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.db import Database
from bot.handlers import admin, fallback, form, start
from bot.services.delivery import deliver_pending
from bot.services.sheets import Sheets

log = logging.getLogger("bot")


def make_storage() -> BaseStorage:
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage
        return RedisStorage.from_url(settings.redis_url)
    log.warning("REDIS_URL berilmagan — anketa javoblari bot qayta ishga tushsa yo'qoladi")
    return MemoryStorage()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db = Database(settings.db_path)
    await db.connect()
    sheets = (
        Sheets(settings.google_credentials_file, settings.google_sheet_id, settings.google_worksheet)
        if settings.sheets_enabled
        else None
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=make_storage(), db=db, sheets=sheets)
    dp.include_routers(admin.router, start.router, form.router, fallback.router)

    await bot.set_my_commands([BotCommand(command="start", description="Botni boshlash")])
    # Oldingi ishga tushishda yetkazilmay qolgan arizalar
    asyncio.create_task(deliver_pending(bot, db, sheets))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
