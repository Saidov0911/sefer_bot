"""Web panel hisoblari: parol hashlash, sessiya va rollar.

Rollar:
  admin  — hamma amal, shu jumladan ommaviy xabar va hisoblarni boshqarish
  viewer — arizalarni ko'rish, holat qo'yish, CV yuklash
"""
import hashlib
import re
import secrets
from dataclasses import dataclass

from fastapi import Request

from bot.config import settings
from bot.db import ROLES, Database

# scrypt parametrlari (~16 MB xotira, bitta parol uchun)
SCRYPT_N, SCRYPT_R, SCRYPT_P, DK_LEN = 2**14, 8, 1, 32
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
MIN_PASSWORD = 8


class LoginRequired(Exception):
    pass


class Forbidden(Exception):
    pass


@dataclass
class CurrentUser:
    username: str
    role: str
    user_id: int | None  # None — .env dagi asosiy hisob

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def from_env(self) -> bool:
        return self.user_id is None


# --- Parollar ---

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=DK_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, key_hex = stored.split("$")
        if algo != "scrypt":
            return False
        key = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(key_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(key.hex(), key_hex)


# --- Tekshiruvlar ---

def check_username(username: str) -> str | None:
    """Xato matnini qaytaradi (yoki None — hammasi joyida)."""
    if not USERNAME_RE.fullmatch(username):
        return "Login 3–32 ta belgidan iborat bo'lishi va faqat lotin harflari, raqam, . _ - dan tashkil topishi kerak."
    if secrets.compare_digest(username.encode(), settings.admin_username.encode()):
        return "Bu login .env dagi asosiy hisobga tegishli — boshqasini tanlang."
    return None


def check_password(password: str) -> str | None:
    if len(password) < MIN_PASSWORD:
        return f"Parol kamida {MIN_PASSWORD} ta belgidan iborat bo'lsin."
    return None


def check_role(role: str) -> str | None:
    return None if role in ROLES else "Rol noto'g'ri."


# --- Sessiya ---

def start_session(request: Request, user: CurrentUser) -> None:
    request.session.clear()
    request.session.update(
        admin=True, username=user.username, role=user.role, uid=user.user_id,
        csrf=secrets.token_urlsafe(32),
    )


def current_user(request: Request) -> CurrentUser:
    session = request.session
    # Rolsiz sessiyalar — bu funksiya qo'shilishidan oldingi kirishlar: qayta kirsin
    if not session.get("admin") or session.get("role") not in ROLES:
        raise LoginRequired
    return CurrentUser(username=session.get("username", ""), role=session["role"], user_id=session.get("uid"))


async def authenticate(db: Database, username: str, password: str) -> CurrentUser | None:
    """.env dagi asosiy hisob yoki bazadagi hisob."""
    env_user = secrets.compare_digest(username.encode(), settings.admin_username.encode())
    env_password = secrets.compare_digest(password.encode(), (settings.admin_password or "").encode())
    if env_user and env_password:
        return CurrentUser(username=settings.admin_username, role="admin", user_id=None)

    account = await db.admin_user(username)
    if account and verify_password(password, account.password_hash):
        await db.touch_admin_login(account.id)
        return CurrentUser(username=account.username, role=account.role, user_id=account.id)
    return None
