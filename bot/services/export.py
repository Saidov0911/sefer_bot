"""Arizalarni CSV'ga eksport qilish (Excel to'g'ri ochishi uchun UTF-8 BOM bilan)."""
import csv
import io

from bot import texts
from bot.db import Application
from bot.utils import local_time

HEADER = [
    "Sana", "Telegram ID", "Username", "Ism familiya", "Telefon", "Takliflar", "Holat", "CV fayl", "Esse",
    "Kitoblar haqida",
]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> object:
    # Excel foydalanuvchi matnini formula sifatida bajarmasligi uchun
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def applications_csv(apps: list[Application]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    for app in apps:
        writer.writerow([_cell(v) for v in (
            local_time(app.created_at),
            app.user_id,
            f"@{app.username}" if app.username else "",
            app.full_name,
            app.phone,
            app.referrals,
            texts.STATUS_LABELS.get(app.status, app.status),
            app.cv_file_name or "",
            app.essay,
            app.answer,
        )])
    return buf.getvalue().encode("utf-8-sig")
