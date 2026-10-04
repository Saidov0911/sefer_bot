"""Sefer saytiga kirish: foydalanuvchi o'z kontaktini ulashadi, bot backend'dan olingan
6 xonali bir martalik kodni beradi. Kod saytda kiritiladi.

Telefon faqat kontakt ulashilganda (va u foydalanuvchining o'ziniki bo'lsa) qabul qilinadi —
qo'lda yozilgan raqam hech narsani isbotlamaydi. Bir marta ulashilgan raqam eslab qolinadi."""
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import keyboards, texts
from bot.config import settings
from bot.db import Database
from bot.handlers.form import normalize_phone
from bot.services.sefer_api import SeferApiError, request_login_code
from bot.states import Login

log = logging.getLogger(__name__)

# Saytdagi havola: t.me/<bot>?start=login
START_PAYLOAD = "login"

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(CommandStart(deep_link=True, magic=F.args == START_PAYLOAD))
@router.message(Command("login"))
async def cmd_login(message: Message, db: Database, state: FSMContext):
    user = message.from_user
    await db.register_user(user.id, user.username, user.full_name, None)
    if not settings.login_enabled:
        await message.answer(texts.LOGIN_DISABLED)
        return

    phone = await db.get_phone(user.id)
    if phone:
        await _send_code(message, phone)
        return
    # Anketa o'rtasida holatni almashtirsak, kiritilgan javoblar yo'qoladi
    if await state.get_state() not in (None, Login.phone.state):
        await message.answer(texts.LOGIN_FINISH_FORM)
        return
    await state.set_state(Login.phone)
    await message.answer(texts.LOGIN_ASK_PHONE, reply_markup=keyboards.phone())


@router.message(Login.phone, F.contact)
async def got_contact(message: Message, db: Database, state: FSMContext):
    phone = normalize_phone(message.contact.phone_number)
    if message.contact.user_id != message.from_user.id or phone is None:
        await message.answer(texts.FOREIGN_CONTACT, reply_markup=keyboards.phone())
        return
    await db.set_phone(message.from_user.id, phone)
    await state.clear()
    await _send_code(message, phone)


@router.message(Login.phone, ~F.text.startswith("/"))
async def need_contact(message: Message):
    await message.answer(texts.LOGIN_NEED_CONTACT, reply_markup=keyboards.phone())


async def _send_code(message: Message, phone: str) -> None:
    user = message.from_user
    try:
        code, seconds = await request_login_code(user.id, phone, user.first_name, user.last_name, user.username)
    except SeferApiError as e:
        if not e.too_many:
            log.error("Kirish kodi olinmadi (user %s): %s", user.id, e)
        text = texts.LOGIN_TOO_MANY if e.too_many else texts.LOGIN_UNAVAILABLE
        await message.answer(text, reply_markup=keyboards.remove)
        return

    text = texts.LOGIN_CODE.format(code=code, seconds=seconds)
    if settings.site_url:
        text += texts.LOGIN_CODE_SITE.format(url=settings.site_url)
    await message.answer(text, reply_markup=keyboards.remove, disable_web_page_preview=True)
