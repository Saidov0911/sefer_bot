"""Bot ichidagi admin panel: callback ma'lumotlari, klaviaturalar va matnlar."""
import html
from math import ceil

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.config import settings
from bot.db import AUDIENCES, STATUSES, Application, Database
from bot.services.broadcast import Broadcaster, BroadcastJob
from bot.services.delivery import admin_message_link
from bot.utils import local_time

PAGE_SIZE = 8
PREVIEW_LIMIT = 1200  # xabar Telegram limitidan (4096) oshmasligi uchun
STATUS_ICONS = {"new": "🆕", "reviewing": "👀", "accepted": "✅", "rejected": "❌"}
STATUS_ACTIONS = {"new": "🆕 Yangi", "reviewing": "👀 Ko‘rib chiqish", "accepted": "✅ Qabul", "rejected": "❌ Rad etish"}


class Menu(CallbackData, prefix="adm"):
    action: str  # home | stats | search | sync | broadcast | noop


class AppList(CallbackData, prefix="adml"):
    status: str = ""  # "" — hammasi
    page: int = 0
    q: bool = False  # oxirgi qidiruv so'zi bilan


class AppView(CallbackData, prefix="admv"):
    user_id: int
    status: str = ""
    page: int = 0
    q: bool = False


class AppAction(CallbackData, prefix="adma"):
    user_id: int
    action: str  # cv | ask | set
    value: str = ""  # yangi holat
    notify: bool = False
    status: str = ""
    page: int = 0
    q: bool = False


class Export(CallbackData, prefix="admx"):
    status: str = ""
    q: bool = False


class Broadcast(CallbackData, prefix="admb"):
    action: str  # audience | send | cancel | stop | refresh
    audience: str = ""


def _btn(text: str, data: CallbackData | None = None, url: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data.pack() if data else None, url=url)


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def _preview(text: str) -> str:
    return html.escape(text if len(text) <= PREVIEW_LIMIT else text[:PREVIEW_LIMIT] + "…")


def back_home() -> InlineKeyboardMarkup:
    return _kb([_btn("⬅️ Menyu", Menu(action="home"))])


# --- Bosh menyu va statistika ---

async def home(db: Database) -> tuple[str, InlineKeyboardMarkup]:
    s = await db.stats()
    counts = await db.status_counts()
    text = (
        "🛠 <b>Admin panel</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b> (24 soatda +{s['users_24h']})\n"
        f"📝 Arizalar: <b>{s['applications']}</b> (24 soatda +{s['applications_24h']})\n"
        + "   ".join(f"{STATUS_ICONS[st]} {counts[st]}" for st in STATUSES)
    )
    return text, _kb(
        [_btn("📝 Arizalar", AppList()), _btn("🔍 Qidirish", Menu(action="search"))],
        [_btn("📊 Statistika", Menu(action="stats")), _btn("📥 CSV eksport", Export())],
        [_btn("📢 Ommaviy xabar", Menu(action="broadcast")), _btn("🔄 Sync", Menu(action="sync"))],
    )


async def stats_text(db: Database) -> str:
    s = await db.stats()
    counts = await db.status_counts()
    return "\n".join([
        "📊 <b>Statistika</b>\n",
        f"👥 Foydalanuvchilar: <b>{s['users']}</b> (24 soatda +{s['users_24h']})",
        f"🚫 Botni bloklaganlar: <b>{s['inactive']}</b>",
        f"🔗 Taklif orqali kelgan (kanalga a’zo): <b>{s['referred']}</b>\n",
        f"📝 Arizalar: <b>{s['applications']}</b> (24 soatda +{s['applications_24h']})",
        *(f"    {texts.STATUS_LABELS[st]}: <b>{counts[st]}</b>" for st in STATUSES),
        "",
        f"⚠️ Guruhga yetib bormagan: <b>{s['not_in_group']}</b>",
        # Sheets o'chiq bo'lsa sheet_synced hech qachon 1 bo'lmaydi — son chalg'itmasin
        f"⚠️ Sheets'ga yozilmagan: <b>{s['not_in_sheet']}</b>"
        if settings.sheets_enabled
        else "📄 Google Sheets: <b>o‘chiq</b> (GOOGLE_SHEET_ID berilmagan)",
    ])


# --- Arizalar ---

async def app_list(db: Database, status: str, page: int, query: str | None) -> tuple[str, InlineKeyboardMarkup]:
    q = query is not None
    total = await db.count_applications(status or None, query)
    pages = max(1, ceil(total / PAGE_SIZE))
    page = min(max(page, 0), pages - 1)
    apps = await db.list_applications(status or None, query, PAGE_SIZE, page * PAGE_SIZE)

    lines = ["📝 <b>Arizalar</b>\n", f"Holat: <b>{texts.STATUS_LABELS[status] if status else 'Hammasi'}</b>"]
    if q:
        lines.append(f"🔍 Qidiruv: <code>{html.escape(query)}</code>")
    lines.append(f"Jami: <b>{total}</b>" if total else "\nHech narsa topilmadi.")

    rows = [
        [_btn(
            f"{STATUS_ICONS.get(a.status, '')} {a.full_name} · {local_time(a.created_at, '%d.%m %H:%M')}",
            AppView(user_id=a.user_id, status=status, page=page, q=q),
        )]
        for a in apps
    ]
    if pages > 1:
        noop = Menu(action="noop")
        rows.append([
            _btn("◀️", AppList(status=status, page=page - 1, q=q) if page > 0 else noop),
            _btn(f"{page + 1}/{pages}", noop),
            _btn("▶️", AppList(status=status, page=page + 1, q=q) if page < pages - 1 else noop),
        ])
    rows.append([
        _btn(("• " if s == status else "") + (STATUS_ICONS[s] if s else "Hammasi"), AppList(status=s, q=q))
        for s in ("", *STATUSES)
    ])
    tools = [_btn("📥 CSV", Export(status=status, q=q)), _btn("🔍 Qidirish", Menu(action="search"))]
    if q:
        tools.append(_btn("✖️ Tozalash", AppList(status=status)))
    rows.append(tools)
    rows.append([_btn("⬅️ Menyu", Menu(action="home"))])
    return "\n".join(lines), _kb(*rows)


def app_view(
    app: Application, status: str = "", page: int = 0, q: bool = False, confirm: str | None = None
) -> tuple[str, InlineKeyboardMarkup]:
    """confirm — tasdiqlanishi kutilayotgan yangi holat."""
    user_link = f'<a href="tg://user?id={app.user_id}">{app.user_id}</a>'
    if app.username:
        user_link += f" (@{html.escape(app.username)})"
    lines = [
        f"📝 <b>Ariza</b> · {texts.STATUS_LABELS.get(app.status, app.status)}\n",
        f"👤 <b>Ism familiya:</b> {html.escape(app.full_name)}",
        f"📱 <b>Telefon:</b> {html.escape(app.phone)}",
        f"🆔 <b>Telegram:</b> {user_link}",
        f"👥 <b>Takliflar:</b> {app.referrals}",
        f"📅 <b>Sana:</b> {local_time(app.created_at)}",
        f"📄 <b>CV:</b> {html.escape(app.cv_file_name or 'fayl')}",
        f"\n📝 <b>Esse:</b>\n{_preview(app.essay)}",
        f"\n📚 <b>Kitoblar haqida:</b>\n{_preview(app.answer)}",
    ]
    ctx = {"status": status, "page": page, "q": q}

    if confirm:
        notify_text = texts.STATUS_NOTIFY.get(confirm)
        lines.append(f"\n❓ Holatni <b>{texts.STATUS_LABELS[confirm]}</b> ga o‘zgartirasizmi?")
        if notify_text:
            lines.append(f"Foydalanuvchiga yuboriladigan xabar:\n<blockquote>{notify_text}</blockquote>")

        def set_status(notify: bool) -> AppAction:
            return AppAction(user_id=app.user_id, action="set", value=confirm, notify=notify, **ctx)

        rows = (
            [[_btn("📨 Ha, xabar bilan", set_status(True)), _btn("🔕 Ha, xabarsiz", set_status(False))]]
            if notify_text
            else [[_btn("✅ Ha", set_status(False))]]
        )
        rows.append([_btn("⬅️ Bekor qilish", AppView(user_id=app.user_id, **ctx))])
        return "\n".join(lines), _kb(*rows)

    status_buttons = [
        _btn(STATUS_ACTIONS[s], AppAction(user_id=app.user_id, action="ask", value=s, **ctx))
        for s in STATUSES
        if s != app.status
    ]
    rows = [
        [_btn("📄 CV faylni olish", AppAction(user_id=app.user_id, action="cv", **ctx))],
        status_buttons[:2],
        status_buttons[2:],
    ]
    if app.admin_msg_id and (link := admin_message_link(app.admin_msg_id)):
        rows.append([_btn("💬 Guruhdagi xabar", url=link)])
    rows.append([_btn("⬅️ Ro‘yxatga", AppList(**ctx))])
    return "\n".join(lines), _kb(*rows)


# --- Ommaviy xabar ---

def job_text(job: BroadcastJob) -> str:
    if job.running:
        state = "⏳ davom etmoqda"
    elif job.cancelled:
        state = "⛔ to‘xtatildi"
    else:
        state = "✅ tugadi"
    return (
        f"📢 <b>Tarqatma {state}</b>\n"
        f"Auditoriya: {texts.AUDIENCE_LABELS.get(job.audience, job.audience)}\n"
        f"Jarayon: <b>{job.done}/{job.total}</b> ({job.percent}%)\n"
        f"✅ Yetkazildi: {job.sent} · 🚫 Bloklagan: {job.blocked} · ⚠️ Xato: {job.failed}"
    )


async def broadcast_menu(db: Database, broadcaster: Broadcaster) -> tuple[str, InlineKeyboardMarkup]:
    job = broadcaster.job
    if job and job.running:
        return job_text(job), _kb(
            [_btn("🔄 Yangilash", Broadcast(action="refresh")), _btn("⛔ To‘xtatish", Broadcast(action="stop"))],
            [_btn("⬅️ Menyu", Menu(action="home"))],
        )
    lines = ["📢 <b>Ommaviy xabar</b>\n", "Kimga yuboramiz? (botni bloklaganlar hisobga olinmaydi)"]
    if job:
        lines.append("\n<b>Oxirgi tarqatma:</b>\n" + job_text(job))
    rows = [
        [_btn(f"{texts.AUDIENCE_LABELS[a]} ({len(await db.audience_ids(a))})", Broadcast(action="audience", audience=a))]
        for a in AUDIENCES
    ]
    rows.append([_btn("⬅️ Menyu", Menu(action="home"))])
    return "\n".join(lines), _kb(*rows)


def broadcast_confirm() -> InlineKeyboardMarkup:
    return _kb([_btn("🚀 Yuborish", Broadcast(action="send")), _btn("❌ Bekor qilish", Broadcast(action="cancel"))])
