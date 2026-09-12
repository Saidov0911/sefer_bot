from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards, texts
from bot.config import settings
from bot.db import Database
from bot.flow import referral_text, show_next_step
from bot.services.subscription import is_subscribed
from bot.states import Form

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


def _parse_referrer(args: str | None) -> int | None:
    return int(args) if args and args.isdigit() else None


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot, db: Database, state: FSMContext):
    user = message.from_user
    is_new = await db.register_user(user.id, user.username, user.full_name, _parse_referrer(command.args))
    if is_new:
        await message.answer(texts.WELCOME.format(name=user.first_name, refs=settings.required_referrals))
    await show_next_step(bot, db, state, user.id)


@router.callback_query(F.data == keyboards.CHECK_SUB)
async def on_check_sub(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_subscribed(bot, user_id):
        await callback.answer(texts.NOT_SUBSCRIBED, show_alert=True)
        return
    await callback.answer(texts.SUBSCRIBED_OK)
    await callback.message.delete()
    # Anketa to'ldirilayotgan paytda obuna qayta so'ralgan bo'lsa — javoblarni o'chirmaymiz
    if await state.get_state() in Form.__all_states_names__:
        return
    await show_next_step(bot, db, state, user_id)


@router.callback_query(F.data == keyboards.CHECK_REFS, StateFilter(None))
async def on_check_refs(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    user_id = callback.from_user.id
    count = await db.referral_count(user_id)
    need = settings.required_referrals
    if count >= need:
        await callback.answer()
        await callback.message.delete()
        await show_next_step(bot, db, state, user_id)
        return

    await callback.answer(texts.REFERRAL_NOT_ENOUGH.format(count=count, need=need, left=need - count), show_alert=True)
    try:  # hisobni yangilab qo'yamiz
        await callback.message.edit_text(
            await referral_text(bot, user_id, count), reply_markup=callback.message.reply_markup
        )
    except TelegramBadRequest:
        pass  # matn o'zgarmagan
