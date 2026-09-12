import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards, texts
from bot.config import settings
from bot.db import Application, Database
from bot.flow import show_next_step, start_form
from bot.services.delivery import deliver
from bot.services.sheets import Sheets
from bot.services.subscription import is_subscribed
from bot.states import Form

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

NAME_ALLOWED_PUNCT = set(" '’‘ʻʼ`-.")
CV_EXTENSIONS = (".pdf", ".doc", ".docx")
CV_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
PREVIEW_LIMIT = 1500  # tasdiqlash xabari Telegram limitidan (4096) oshmasligi uchun


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"[\s\-()]", "", raw)
    if not re.fullmatch(r"\+?\d{9,15}", digits):
        return None
    digits = digits.lstrip("+")
    if len(digits) == 9:  # 901234567 -> +998901234567
        digits = "998" + digits
    return "+" + digits


def _preview(text: str) -> str:
    text = text if len(text) <= PREVIEW_LIMIT else text[:PREVIEW_LIMIT] + "…"
    return html.escape(text)


# --- 1. Ism familiya ---

@router.message(Form.full_name, F.text)
async def got_name(message: Message, state: FSMContext):
    name = " ".join(message.text.split())
    words = name.split()
    valid = (
        len(words) >= 2
        and len(name) <= 100
        and all(ch.isalpha() or ch in NAME_ALLOWED_PUNCT for ch in name)
    )
    if not valid:
        await message.answer(texts.BAD_NAME)
        return
    await state.update_data(full_name=name)
    await state.set_state(Form.phone)
    await message.answer(texts.ASK_PHONE, reply_markup=keyboards.phone())


# --- 2. Telefon ---

@router.message(Form.phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    if message.contact.user_id != message.from_user.id:
        await message.answer(texts.FOREIGN_CONTACT, reply_markup=keyboards.phone())
        return
    await _save_phone(message, state, normalize_phone(message.contact.phone_number))


@router.message(Form.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    await _save_phone(message, state, normalize_phone(message.text))


async def _save_phone(message: Message, state: FSMContext, phone: str | None):
    if phone is None:
        await message.answer(texts.BAD_PHONE, reply_markup=keyboards.phone())
        return
    await state.update_data(phone=phone)
    await state.set_state(Form.cv)
    await message.answer(texts.ASK_CV, reply_markup=keyboards.remove)


# --- 3. CV ---

@router.message(Form.cv, F.document)
async def got_cv(message: Message, state: FSMContext):
    doc = message.document
    name = (doc.file_name or "").lower()
    if not (name.endswith(CV_EXTENSIONS) or doc.mime_type in CV_MIME_TYPES):
        await message.answer(texts.BAD_CV)
        return
    await state.update_data(cv_file_id=doc.file_id, cv_file_name=doc.file_name)
    await state.set_state(Form.essay)
    await message.answer(texts.ASK_ESSAY.format(max=settings.essay_max_words))


# --- 4. Esse ---

@router.message(Form.essay, F.text)
async def got_essay(message: Message, state: FSMContext):
    count = len(message.text.split())
    if count > settings.essay_max_words:
        await message.answer(texts.ESSAY_TOO_LONG.format(count=count, max=settings.essay_max_words))
        return
    await state.update_data(essay=message.text.strip())
    await state.set_state(Form.answer)
    await message.answer(texts.ASK_ANSWER)


# --- 5. Kitoblar haqida savol ---

@router.message(Form.answer, F.text)
async def got_answer(message: Message, state: FSMContext):
    await state.update_data(answer=message.text.strip())
    await state.set_state(Form.confirm)
    data = await state.get_data()
    await message.answer(
        texts.CONFIRM.format(
            full_name=html.escape(data["full_name"]),
            phone=data["phone"],
            cv=html.escape(data["cv_file_name"] or "fayl"),
            essay=_preview(data["essay"]),
            answer=_preview(data["answer"]),
        ),
        reply_markup=keyboards.confirm(),
    )


# --- Noto'g'ri turdagi xabarlar ---

@router.message(Form.full_name)
@router.message(Form.essay)
@router.message(Form.answer)
async def need_text(message: Message):
    await message.answer(texts.TEXT_ONLY)


@router.message(Form.phone)
async def need_phone(message: Message):
    await message.answer(texts.BAD_PHONE, reply_markup=keyboards.phone())


@router.message(Form.cv)
async def need_cv(message: Message):
    await message.answer(texts.BAD_CV)


@router.message(Form.confirm)
async def need_confirm(message: Message):
    await message.answer("Iltimos, yuqoridagi tugmalardan birini bosing.")


# --- Tasdiqlash ---

@router.callback_query(Form.confirm, F.data == keyboards.RESTART)
async def on_restart(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(texts.RESTART_FORM)
    await start_form(bot, state, callback.from_user.id)


@router.callback_query(Form.confirm, F.data == keyboards.SUBMIT)
async def on_submit(callback: CallbackQuery, bot: Bot, db: Database, sheets: Sheets | None, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_subscribed(bot, user_id):
        await callback.answer()
        await callback.message.answer(texts.NOT_SUBSCRIBED, reply_markup=keyboards.subscribe())
        return

    data = await state.get_data()
    app = Application(
        user_id=user_id,
        full_name=data["full_name"],
        phone=data["phone"],
        cv_file_id=data["cv_file_id"],
        cv_file_name=data.get("cv_file_name"),
        essay=data["essay"],
        answer=data["answer"],
    )
    saved = await db.save_application(app)
    await state.clear()
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    if not saved:
        await callback.message.answer(texts.ALREADY_SUBMITTED)
        return
    await callback.message.answer(texts.SUBMITTED)
    await deliver(bot, db, sheets, await db.get_application(user_id))


# Eski tugmalar (bot qayta ishga tushgan yoki anketa allaqachon yuborilgan)
@router.callback_query(F.data.in_({keyboards.SUBMIT, keyboards.RESTART}), StateFilter(None))
async def stale_confirm(callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_next_step(bot, db, state, callback.from_user.id)
