from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db import Database
from bot.flow import show_next_step

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(StateFilter(None))
async def any_message(message: Message, bot: Bot, db: Database, state: FSMContext):
    """/start bosmasdan yozganlar yoki bot qayta ishga tushgandan keyin holati yo'qolganlar."""
    user = message.from_user
    await db.register_user(user.id, user.username, user.full_name, None)
    await show_next_step(bot, db, state, user.id)


@router.callback_query()
async def any_callback(callback: CallbackQuery):
    """Eskirgan tugmalar — soat belgisi osilib qolmasligi uchun javob beramiz."""
    await callback.answer()
