import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

from bot.config import settings
from bot.db import Database
from bot.handlers import admin, fallback, form, start
from bot.services.broadcast import Broadcaster
from bot.services.delivery import deliver_pending
from bot.services.sheets import Sheets

log = logging.getLogger("bot")

USER_COMMANDS = [BotCommand(command="start", description="Botni boshlash")]
ADMIN_COMMANDS = [
    *USER_COMMANDS,
    BotCommand(command="admin", description="Admin panel"),
    BotCommand(command="stats", description="Statistika"),
    BotCommand(command="sync", description="Yetkazilmagan arizalarni qayta yuborish"),
]


def make_storage() -> BaseStorage:
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage
        return RedisStorage.from_url(settings.redis_url)
    log.warning("REDIS_URL berilmagan — anketa javoblari bot qayta ishga tushsa yo'qoladi")
    return MemoryStorage()


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(USER_COMMANDS)
    for admin_id in settings.admin_id_set:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except TelegramAPIError:
            log.warning("Admin %s uchun buyruqlar o'rnatilmadi (botga /start bosmagan bo'lishi mumkin)", admin_id)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db = Database(settings.db_path)
    await db.connect()
    sheets = (
        Sheets(settings.google_credentials_file, settings.google_sheet_id, settings.google_worksheet)
        if settings.sheets_enabled
        else None
    )
    broadcaster = Broadcaster(db)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=make_storage(), db=db, sheets=sheets, broadcaster=broadcaster)
    dp.include_routers(admin.router, start.router, form.router, fallback.router)

    await set_commands(bot)
    # Oldingi ishga tushishda yetkazilmay qolgan arizalar
    asyncio.create_task(deliver_pending(bot, db, sheets))

    web = None
    if settings.web_enabled:
        from bot.web.app import WebServer
        web = WebServer(bot, db, sheets, broadcaster)
        web.start()
    else:
        log.info("ADMIN_PASSWORD berilmagan — web admin panel o'chiq")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        broadcaster.cancel()
        if web:
            await web.stop()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
