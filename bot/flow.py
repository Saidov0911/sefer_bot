"""Foydalanuvchi qaysi bosqichda ekanini aniqlab, keyingi qadamni ko'rsatadi:
obuna -> do'stlarni taklif qilish -> anketa -> tayyor."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext

from bot import keyboards, texts
from bot.config import settings
from bot.db import Database
from bot.services.subscription import is_subscribed
from bot.states import Form

log = logging.getLogger(__name__)


async def referral_link(bot: Bot, user_id: int) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start={user_id}"


async def referral_text(bot: Bot, user_id: int, count: int) -> str:
    return texts.REFERRAL.format(
        link=await referral_link(bot, user_id), count=count, need=settings.required_referrals
    )


async def credit_referrer(bot: Bot, db: Database, user_id: int) -> None:
    """Kanalga a'zo bo'lgan foydalanuvchini taklif qilgan odamga hisoblaydi va xabar beradi."""
    referrer_id = await db.credit_referral(user_id)
    if referrer_id is None:
        return
    count = await db.referral_count(referrer_id)
    need = settings.required_referrals
    if count > need or await db.has_application(referrer_id):
        return
    text = texts.REFERRAL_DONE.format(need=need) if count == need else texts.REFERRAL_NEW.format(count=count, need=need)
    try:
        await bot.send_message(referrer_id, text)
    except TelegramAPIError:
        log.info("Referrer %s ga xabar yuborilmadi (botni bloklagan bo'lishi mumkin)", referrer_id)


async def show_next_step(bot: Bot, db: Database, state: FSMContext, user_id: int) -> None:
    await state.clear()

    if await db.has_application(user_id):
        await bot.send_message(user_id, texts.ALREADY_SUBMITTED, reply_markup=keyboards.remove)
        return

    if not await is_subscribed(bot, user_id):
        await bot.send_message(user_id, texts.SUBSCRIBE, reply_markup=keyboards.subscribe())
        return
    await credit_referrer(bot, db, user_id)

    count = await db.referral_count(user_id)
    if count < settings.required_referrals:
        await bot.send_message(
            user_id,
            await referral_text(bot, user_id, count),
            reply_markup=keyboards.referral(await referral_link(bot, user_id)),
        )
        return

    await start_form(bot, state, user_id)


async def start_form(bot: Bot, state: FSMContext, user_id: int) -> None:
    await state.clear()
    await state.set_state(Form.full_name)
    await bot.send_message(user_id, texts.FORM_START)
    await bot.send_message(user_id, texts.ASK_NAME, reply_markup=keyboards.remove)
