import asyncio
import logging
from pathlib import Path

import gspread

from bot.db import Application
from bot.utils import local_time

log = logging.getLogger(__name__)

HEADER = ["Sana", "Telegram ID", "Username", "Ism familiya", "Telefon", "Takliflar", "CV", "Esse", "Kitoblar haqida"]


class Sheets:
    def __init__(self, credentials_file: Path, sheet_id: str, worksheet: str):
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id
        self.worksheet_name = worksheet
        self._ws: gspread.Worksheet | None = None
        self._lock = asyncio.Lock()

    def _worksheet(self) -> gspread.Worksheet:
        if self._ws is None:
            client = gspread.service_account(filename=str(self.credentials_file))
            spreadsheet = client.open_by_key(self.sheet_id)
            try:
                ws = spreadsheet.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(self.worksheet_name, rows=1000, cols=len(HEADER))
            if not ws.row_values(1):
                ws.append_row(HEADER, value_input_option="RAW")
                ws.freeze(rows=1)
            self._ws = ws
        return self._ws

    def _append(self, app: Application, cv_link: str | None) -> None:
        row = [
            local_time(app.created_at),
            str(app.user_id),
            f"@{app.username}" if app.username else "",
            app.full_name,
            app.phone,
            app.referrals,
            cv_link or app.cv_file_name or "",
            app.essay,
            app.answer,
        ]
        # RAW — foydalanuvchi matni formula sifatida bajarilmasligi uchun
        self._worksheet().append_row(row, value_input_option="RAW")

    async def append(self, app: Application, cv_link: str | None) -> None:
        async with self._lock:
            await asyncio.to_thread(self._append, app, cv_link)
