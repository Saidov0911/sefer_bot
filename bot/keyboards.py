from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from bot import texts
from bot.config import settings

CHECK_SUB = "check_sub"
CHECK_REFS = "check_refs"
SUBMIT = "submit"
RESTART = "restart"

remove = ReplyKeyboardRemove()


def subscribe() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_CHANNEL, url=settings.channel_url)],
        [InlineKeyboardButton(text=texts.BTN_INSTAGRAM, url=settings.instagram_url)],
        [InlineKeyboardButton(text=texts.BTN_CHECK, callback_data=CHECK_SUB)],
    ])


def referral(link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(texts.REFERRAL_SHARE_TEXT)}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_SHARE, url=share_url)],
        [InlineKeyboardButton(text=texts.BTN_CHECK_REFS, callback_data=CHECK_REFS)],
    ])


def phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_SUBMIT, callback_data=SUBMIT)],
        [InlineKeyboardButton(text=texts.BTN_RESTART, callback_data=RESTART)],
    ])
