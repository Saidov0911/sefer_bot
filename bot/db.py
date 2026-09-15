from dataclasses import dataclass
from pathlib import Path

import aiosqlite

# Ariza holatlari (yorliqlar: texts.STATUS_LABELS)
STATUSES = ("new", "reviewing", "accepted", "rejected")
# Ommaviy xabar auditoriyalari (yorliqlar: texts.AUDIENCE_LABELS)
AUDIENCES = ("all", "applied", "not_applied", *STATUSES)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY,
    username          TEXT,
    tg_name           TEXT,
    referrer_id       INTEGER REFERENCES users(id),
    referral_credited INTEGER NOT NULL DEFAULT 0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id, referral_credited);

CREATE TABLE IF NOT EXISTS applications (
    user_id           INTEGER PRIMARY KEY REFERENCES users(id),
    full_name         TEXT NOT NULL,
    phone             TEXT NOT NULL,
    cv_file_id        TEXT NOT NULL,
    cv_file_name      TEXT,
    essay             TEXT NOT NULL,
    answer            TEXT NOT NULL,
    admin_msg_id      INTEGER,
    sheet_synced      INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'new',
    status_updated_at TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Eski bazalarga qo'shiladigan ustunlar: (jadval, ustun, ta'rif)
MIGRATIONS = [
    ("users", "is_active", "INTEGER NOT NULL DEFAULT 1"),
    ("applications", "status", "TEXT NOT NULL DEFAULT 'new'"),
    ("applications", "status_updated_at", "TEXT"),
]

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status, created_at);
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
    status: str = "new"
    status_updated_at: str | None = None
    created_at: str | None = None
    username: str | None = None
    referrals: int = 0


@dataclass
class User:
    id: int
    username: str | None
    tg_name: str | None
    referrer_id: int | None
    is_active: bool
    created_at: str
    referrals: int
    app_status: str | None  # ariza topshirmagan bo'lsa None


def _like(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _clean_query(query: str | None) -> str:
    return (query or "").strip().lstrip("@")


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
        await self._migrate()
        await self.conn.executescript(INDEXES)
        await self.conn.commit()

    async def _migrate(self) -> None:
        for table, column, ddl in MIGRATIONS:
            cur = await self.conn.execute(f"PRAGMA table_info({table})")
            if column not in {r["name"] for r in await cur.fetchall()}:
                await self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

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
            # Botga qayta yozgan bo'lsa — bloklashni olib tashlagan
            await self.conn.execute(
                "UPDATE users SET username = ?, tg_name = ?, is_active = 1 WHERE id = ?",
                (username, tg_name, user_id),
            )
        await self.conn.commit()
        return is_new

    async def user_exists(self, user_id: int) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        return await cur.fetchone() is not None

    async def set_user_active(self, user_id: int, active: bool) -> None:
        await self.conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(active), user_id))
        await self.conn.commit()

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

    @staticmethod
    def _user_where(query: str | None) -> tuple[str, list]:
        if not (query := _clean_query(query)):
            return "", []
        like = _like(query)
        return (
            "WHERE CAST(u.id AS TEXT) = ? OR u.username LIKE ? ESCAPE '\\' OR u.tg_name LIKE ? ESCAPE '\\'",
            [query, like, like],
        )

    async def count_users(self, query: str | None = None) -> int:
        where, params = self._user_where(query)
        cur = await self.conn.execute(f"SELECT COUNT(*) FROM users u {where}", params)
        return (await cur.fetchone())[0]

    async def list_users(self, query: str | None = None, limit: int = 50, offset: int = 0) -> list[User]:
        where, params = self._user_where(query)
        cur = await self.conn.execute(
            "SELECT u.*, a.status AS app_status, "
            "(SELECT COUNT(*) FROM users r WHERE r.referrer_id = u.id AND r.referral_credited = 1) AS referrals "
            f"FROM users u LEFT JOIN applications a ON a.user_id = u.id {where} "
            "ORDER BY u.created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return [
            User(
                id=r["id"], username=r["username"], tg_name=r["tg_name"], referrer_id=r["referrer_id"],
                is_active=bool(r["is_active"]), created_at=r["created_at"], referrals=r["referrals"],
                app_status=r["app_status"],
            )
            for r in await cur.fetchall()
        ]

    async def audience_ids(self, audience: str) -> list[int]:
        """Ommaviy xabar oluvchilar (botni bloklaganlar hisobga olinmaydi)."""
        if audience == "all":
            sql, params = "SELECT id FROM users WHERE is_active = 1", ()
        elif audience == "applied":
            sql, params = "SELECT u.id FROM users u JOIN applications a ON a.user_id = u.id WHERE u.is_active = 1", ()
        elif audience == "not_applied":
            sql, params = (
                "SELECT id FROM users u WHERE is_active = 1 "
                "AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.user_id = u.id)",
                (),
            )
        elif audience in STATUSES:
            sql, params = (
                "SELECT u.id FROM users u JOIN applications a ON a.user_id = u.id "
                "WHERE u.is_active = 1 AND a.status = ?",
                (audience,),
            )
        else:
            raise ValueError(f"Noma'lum auditoriya: {audience}")
        cur = await self.conn.execute(sql, params)
        return [r[0] for r in await cur.fetchall()]

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

    async def set_status(self, user_id: int, status: str) -> bool:
        """Qaytaradi: holat o'zgardimi (ariza yo'q yoki holat bir xil bo'lsa False)."""
        if status not in STATUSES:
            raise ValueError(f"Noma'lum holat: {status}")
        cur = await self.conn.execute(
            "UPDATE applications SET status = ?, status_updated_at = datetime('now') "
            "WHERE user_id = ? AND status != ?",
            (status, user_id, status),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def get_application(self, user_id: int) -> Application | None:
        rows = await self._fetch_applications("WHERE a.user_id = ?", (user_id,))
        return rows[0] if rows else None

    async def pending_applications(self) -> list[Application]:
        """Admin guruhiga yoki Google Sheets'ga hali yetib bormagan arizalar."""
        return await self._fetch_applications(
            "WHERE a.admin_msg_id IS NULL OR a.sheet_synced = 0 ORDER BY a.created_at", ()
        )

    @staticmethod
    def _app_where(status: str | None, query: str | None) -> tuple[str, list]:
        conds, params = [], []
        if status:
            conds.append("a.status = ?")
            params.append(status)
        if query := _clean_query(query):
            like = _like(query)
            conds.append(
                "(CAST(a.user_id AS TEXT) = ? OR a.full_name LIKE ? ESCAPE '\\' "
                "OR a.phone LIKE ? ESCAPE '\\' OR u.username LIKE ? ESCAPE '\\')"
            )
            params += [query, like, like, like]
        return ("WHERE " + " AND ".join(conds)) if conds else "", params

    async def count_applications(self, status: str | None = None, query: str | None = None) -> int:
        where, params = self._app_where(status, query)
        cur = await self.conn.execute(
            f"SELECT COUNT(*) FROM applications a JOIN users u ON u.id = a.user_id {where}", params
        )
        return (await cur.fetchone())[0]

    async def list_applications(
        self, status: str | None = None, query: str | None = None, limit: int = -1, offset: int = 0
    ) -> list[Application]:
        """Eng yangilari birinchi. limit=-1 — hammasi."""
        where, params = self._app_where(status, query)
        return await self._fetch_applications(
            f"{where} ORDER BY a.created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset)
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
                status=r["status"], status_updated_at=r["status_updated_at"], created_at=r["created_at"],
                username=r["username"], referrals=r["referrals"],
            )
            for r in await cur.fetchall()
        ]

    async def stats(self) -> dict[str, int]:
        cur = await self.conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM users) AS users, "
            "(SELECT COUNT(*) FROM users WHERE is_active = 0) AS inactive, "
            "(SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')) AS users_24h, "
            "(SELECT COUNT(*) FROM users WHERE referral_credited = 1) AS referred, "
            "(SELECT COUNT(*) FROM applications) AS applications, "
            "(SELECT COUNT(*) FROM applications WHERE created_at >= datetime('now', '-1 day')) AS applications_24h, "
            "(SELECT COUNT(*) FROM applications WHERE admin_msg_id IS NULL) AS not_in_group, "
            "(SELECT COUNT(*) FROM applications WHERE sheet_synced = 0) AS not_in_sheet"
        )
        return dict(await cur.fetchone())

    async def status_counts(self) -> dict[str, int]:
        cur = await self.conn.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
        counts = dict.fromkeys(STATUSES, 0)
        counts.update({r[0]: r[1] for r in await cur.fetchall()})
        return counts
