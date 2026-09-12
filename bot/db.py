from dataclasses import dataclass
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY,
    username          TEXT,
    tg_name           TEXT,
    referrer_id       INTEGER REFERENCES users(id),
    referral_credited INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id, referral_credited);

CREATE TABLE IF NOT EXISTS applications (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id),
    full_name    TEXT NOT NULL,
    phone        TEXT NOT NULL,
    cv_file_id   TEXT NOT NULL,
    cv_file_name TEXT,
    essay        TEXT NOT NULL,
    answer       TEXT NOT NULL,
    admin_msg_id INTEGER,
    sheet_synced INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class Application:
    user_id: int
    full_name: str
    phone: str
    cv_file_id: str
    cv_file_name: str | None
    essay: str
    answer: str
    admin_msg_id: int | None = None
    sheet_synced: bool = False
    created_at: str | None = None
    username: str | None = None
    referrals: int = 0


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    # --- users ---

    async def register_user(
        self, user_id: int, username: str | None, tg_name: str, referrer_id: int | None
    ) -> bool:
        """Yangi foydalanuvchini qo'shadi. Referrer faqat birinchi kirishda yoziladi.
        Qaytaradi: foydalanuvchi yangimi."""
        if referrer_id is not None and (referrer_id == user_id or not await self.user_exists(referrer_id)):
            referrer_id = None
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO users (id, username, tg_name, referrer_id) VALUES (?, ?, ?, ?)",
            (user_id, username, tg_name, referrer_id),
        )
        is_new = cur.rowcount == 1
        if not is_new:
            await self.conn.execute(
                "UPDATE users SET username = ?, tg_name = ? WHERE id = ?", (username, tg_name, user_id)
            )
        await self.conn.commit()
        return is_new

    async def user_exists(self, user_id: int) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        return await cur.fetchone() is not None

    async def credit_referral(self, user_id: int) -> int | None:
        """Foydalanuvchi kanalga a'zo bo'lganda chaqiriladi. Taklif qilgan odamga
        bir marta ball beradi va uning id'sini qaytaradi (aks holda None)."""
        cur = await self.conn.execute(
            "UPDATE users SET referral_credited = 1 "
            "WHERE id = ? AND referral_credited = 0 AND referrer_id IS NOT NULL "
            "RETURNING referrer_id",
            (user_id,),
        )
        row = await cur.fetchone()
        await self.conn.commit()
        return row["referrer_id"] if row else None

    async def referral_count(self, user_id: int) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ? AND referral_credited = 1", (user_id,)
        )
        return (await cur.fetchone())[0]

    # --- applications ---

    async def has_application(self, user_id: int) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM applications WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None

    async def save_application(self, app: Application) -> bool:
        """Qaytaradi: saqlandimi (ikkinchi marta topshirishga yo'l qo'yilmaydi)."""
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO applications "
            "(user_id, full_name, phone, cv_file_id, cv_file_name, essay, answer) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (app.user_id, app.full_name, app.phone, app.cv_file_id, app.cv_file_name, app.essay, app.answer),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def set_admin_msg_id(self, user_id: int, msg_id: int) -> None:
        await self.conn.execute("UPDATE applications SET admin_msg_id = ? WHERE user_id = ?", (msg_id, user_id))
        await self.conn.commit()

    async def mark_synced(self, user_id: int) -> None:
        await self.conn.execute("UPDATE applications SET sheet_synced = 1 WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    async def get_application(self, user_id: int) -> Application | None:
        rows = await self._fetch_applications("WHERE a.user_id = ?", (user_id,))
        return rows[0] if rows else None

    async def pending_applications(self) -> list[Application]:
        """Admin guruhiga yoki Google Sheets'ga hali yetib bormagan arizalar."""
        return await self._fetch_applications(
            "WHERE a.admin_msg_id IS NULL OR a.sheet_synced = 0 ORDER BY a.created_at", ()
        )

    async def _fetch_applications(self, where: str, params: tuple) -> list[Application]:
        cur = await self.conn.execute(
            "SELECT a.*, u.username, "
            "(SELECT COUNT(*) FROM users r WHERE r.referrer_id = a.user_id AND r.referral_credited = 1) AS referrals "
            f"FROM applications a JOIN users u ON u.id = a.user_id {where}",
            params,
        )
        return [
            Application(
                user_id=r["user_id"], full_name=r["full_name"], phone=r["phone"],
                cv_file_id=r["cv_file_id"], cv_file_name=r["cv_file_name"], essay=r["essay"],
                answer=r["answer"], admin_msg_id=r["admin_msg_id"], sheet_synced=bool(r["sheet_synced"]),
                created_at=r["created_at"],
                username=r["username"], referrals=r["referrals"],
            )
            for r in await cur.fetchall()
        ]

    async def stats(self) -> dict[str, int]:
        cur = await self.conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM users) AS users, "
            "(SELECT COUNT(*) FROM users WHERE referral_credited = 1) AS referred, "
            "(SELECT COUNT(*) FROM applications) AS applications, "
            "(SELECT COUNT(*) FROM applications WHERE admin_msg_id IS NULL) AS not_in_group, "
            "(SELECT COUNT(*) FROM applications WHERE sheet_synced = 0) AS not_in_sheet"
        )
        return dict(await cur.fetchone())
