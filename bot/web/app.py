"""Web admin panel (FastAPI). Bot bilan bir jarayonda ishlaydi: DB ulanishi, Bot va tarqatma holati umumiy."""
import asyncio
import contextlib
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime
from math import ceil
from pathlib import Path
from urllib.parse import quote, urlencode

import uvicorn
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from bot import texts
from bot.config import settings
from bot.db import AUDIENCES, ROLES, STATUSES, Database
from bot.services.broadcast import Broadcaster
from bot.services.delivery import admin_message_link, deliver_pending
from bot.services.export import applications_csv
from bot.services.sheets import Sheets
from bot.services.status import change_status
from bot.utils import TASHKENT, local_time
from bot.web import auth
from bot.web.auth import CurrentUser, Forbidden, LoginRequired

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PAGE_SIZE = 25
LOGIN_MAX_FAILS = 5
LOGIN_WINDOW = 600  # soniya
TG_TEXT_LIMIT = 4096
ROLE_LABELS = {"admin": "To‘liq admin", "viewer": "Ko‘ruvchi"}


def url_with(request: Request, **params) -> str:
    """Joriy URL, query parametrlari almashtirilgan holda (sahifalash uchun)."""
    query = {**request.query_params, **params}
    query = {k: v for k, v in query.items() if v not in (None, "")}
    return f"{request.url.path}?{urlencode(query)}" if query else request.url.path


templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["local_time"] = local_time
templates.env.filters["dt"] = lambda d: d.astimezone(TASHKENT).strftime("%Y-%m-%d %H:%M:%S") if d else ""
templates.env.globals.update(
    STATUSES=STATUSES, STATUS_LABELS=texts.STATUS_LABELS,
    AUDIENCES=AUDIENCES, AUDIENCE_LABELS=texts.AUDIENCE_LABELS,
    ROLES=ROLES, ROLE_LABELS=ROLE_LABELS, ADMIN_USERNAME=settings.admin_username,
    url_with=url_with,
)


async def verify_csrf(request: Request) -> None:
    form = await request.form()
    expected = request.session.get("csrf", "")
    if not expected or not secrets.compare_digest(str(form.get("csrf", "")).encode(), expected.encode()):
        raise HTTPException(403, "CSRF token noto'g'ri. Sahifani yangilab, qayta urinib ko'ring.")


def render(request: Request, name: str, status_code: int = 200, **context) -> Response:
    csrf = request.session.setdefault("csrf", secrets.token_urlsafe(32))
    try:
        user = auth.current_user(request)
    except LoginRequired:
        user = None
    context = {
        "csrf": csrf, "user": user, "flash": request.session.pop("flash", None),
        "path": request.url.path, **context,
    }
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session["flash"] = {"message": message, "kind": kind}


def paginate(total: int, page: int) -> tuple[int, int, int]:
    """Qaytaradi: (sahifa, sahifalar soni, offset)."""
    pages = max(1, ceil(total / PAGE_SIZE))
    page = min(max(page, 1), pages)
    return page, pages, (page - 1) * PAGE_SIZE


def _safe_next(url: str) -> str:
    return url if url.startswith("/") and not url.startswith("//") else "/"


def _attachment(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename)}"


def create_app(bot: Bot, db: Database, sheets: Sheets | None, broadcaster: Broadcaster) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.web_secret_key or secrets.token_hex(32),
        session_cookie="sefer_admin",
        max_age=7 * 24 * 3600,
        same_site="lax",
        https_only=settings.web_https_only,
    )
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @app.exception_handler(LoginRequired)
    async def to_login(request: Request, _: LoginRequired):
        target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?{urlencode({'next': target})}", status_code=303)

    @app.exception_handler(Forbidden)
    async def forbidden(request: Request, _: Forbidden):
        return render(request, "403.html", status_code=403)

    # --- Kirish ---

    login_failures: dict[str, deque[float]] = defaultdict(deque)

    @app.get("/login")
    async def login_page(request: Request, next: str = "/"):
        if request.session.get("admin"):
            return RedirectResponse(_safe_next(next), status_code=303)
        return render(request, "login.html", next=next)

    @app.post("/login", dependencies=[Depends(verify_csrf)])
    async def login(request: Request, username: str = Form(""), password: str = Form(""), next: str = Form("/")):
        ip = request.client.host if request.client else "?"
        failures, now = login_failures[ip], time.monotonic()
        while failures and now - failures[0] > LOGIN_WINDOW:
            failures.popleft()
        if len(failures) >= LOGIN_MAX_FAILS:
            error = "Juda ko'p muvaffaqiyatsiz urinish. 10 daqiqadan keyin qayta urinib ko'ring."
            return render(request, "login.html", status_code=429, next=next, error=error)

        user = await auth.authenticate(db, username.strip(), password)
        if user is None:
            failures.append(now)
            log.warning("Web panelga noto'g'ri kirish urinishi (login=%r, ip=%s)", username[:32], ip)
            await asyncio.sleep(1)
            return render(request, "login.html", status_code=401, next=next, error="Login yoki parol noto'g'ri.")

        failures.clear()
        auth.start_session(request, user)
        log.info("Web panelga kirdi: %s (%s, ip=%s)", user.username, user.role, ip)
        return RedirectResponse(_safe_next(next), status_code=303)

    @app.post("/logout", dependencies=[Depends(verify_csrf)])
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # --- Kirgan foydalanuvchi ---

    async def load_user(request: Request) -> CurrentUser:
        """Sessiyadagi hisob bazada hali ham bor va roli o'zgarmaganini tekshiradi."""
        user = auth.current_user(request)
        if user.user_id is None:  # .env dagi asosiy hisob
            return user
        account = await db.admin_user_by_id(user.user_id)
        if account is None:  # hisob o'chirilgan
            request.session.clear()
            raise LoginRequired
        if account.role != user.role:  # rol o'zgargan — sessiyani yangilaymiz
            request.session["role"] = account.role
            return CurrentUser(username=account.username, role=account.role, user_id=account.id)
        return user

    async def load_admin(request: Request) -> CurrentUser:
        user = await load_user(request)
        if not user.is_admin:
            raise Forbidden
        return user

    # --- Panel (faqat kirganlar uchun) ---

    panel = APIRouter(dependencies=[Depends(load_user)])

    @panel.get("/")
    async def dashboard(request: Request):
        return render(
            request, "dashboard.html",
            stats=await db.stats(),
            counts=await db.status_counts(),
            latest=await db.list_applications(limit=8),
            job=broadcaster.job,
            sheets_enabled=sheets is not None,
        )

    @panel.post("/sync", dependencies=[Depends(load_admin), Depends(verify_csrf)])
    async def sync(request: Request):
        count = await deliver_pending(bot, db, sheets)
        flash(request, f"Qayta yuborildi: {count} ta ariza.")
        return RedirectResponse("/", status_code=303)

    @panel.get("/applications")
    async def applications(request: Request, status: str = "", q: str = "", page: int = 1):
        status = status if status in STATUSES else ""
        total = await db.count_applications(status or None, q)
        page, pages, offset = paginate(total, page)
        return render(
            request, "applications.html",
            apps=await db.list_applications(status or None, q, PAGE_SIZE, offset),
            counts=await db.status_counts(),
            total=total, page=page, pages=pages, status=status, q=q,
            export_url="/applications.csv?" + urlencode({"status": status, "q": q}),
        )

    @panel.get("/applications.csv")
    async def applications_export(status: str = "", q: str = ""):
        status = status if status in STATUSES else ""
        apps = await db.list_applications(status or None, q)
        filename = f"arizalar_{datetime.now(TASHKENT):%Y%m%d_%H%M}.csv"
        return Response(
            applications_csv(apps), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": _attachment(filename)},
        )

    @panel.get("/applications/{user_id}")
    async def application_detail(request: Request, user_id: int):
        app_ = await db.get_application(user_id)
        if app_ is None:
            raise HTTPException(404, "Ariza topilmadi")
        group_link = admin_message_link(app_.admin_msg_id) if app_.admin_msg_id else None
        return render(request, "application.html", app=app_, group_link=group_link)

    @panel.get("/applications/{user_id}/cv")
    async def application_cv(user_id: int):
        app_ = await db.get_application(user_id)
        if app_ is None:
            raise HTTPException(404, "Ariza topilmadi")
        try:
            file = await bot.get_file(app_.cv_file_id)
            content = await bot.download_file(file.file_path)
        except TelegramAPIError as e:
            log.exception("CV faylni Telegram'dan olib bo'lmadi (user %s)", user_id)
            raise HTTPException(502, f"Faylni Telegram'dan olib bo'lmadi: {e}")
        # Foydalanuvchi yuklagan fayl — brauzerda ochilmasin, faqat yuklab olinsin
        return Response(
            content.getvalue(), media_type="application/octet-stream",
            headers={
                "Content-Disposition": _attachment(app_.cv_file_name or f"cv_{user_id}"),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @panel.post("/applications/{user_id}/status", dependencies=[Depends(verify_csrf)])
    async def application_status(
        request: Request, user_id: int, user: CurrentUser = Depends(load_user),
        status: str = Form(...), notify: bool = Form(False),
    ):
        if status not in STATUSES:
            raise HTTPException(400, "Noma'lum holat")
        if not await db.has_application(user_id):
            raise HTTPException(404, "Ariza topilmadi")
        changed, notified = await change_status(bot, db, user_id, status, notify)
        if changed:
            log.info("Web panel: %s arizaga (%s) «%s» holatini qo'ydi", user.username, user_id, status)
        if not changed:
            flash(request, "Holat o'zgarmadi — ariza allaqachon shu holatda.", "info")
        elif notify and status in texts.STATUS_NOTIFY and not notified:
            flash(request, "Holat o'zgartirildi, lekin foydalanuvchiga xabar yetib bormadi (botni bloklagan bo'lishi mumkin).", "error")
        else:
            flash(request, "Holat o'zgartirildi" + (", foydalanuvchiga xabar yuborildi." if notified else "."))
        return RedirectResponse(f"/applications/{user_id}", status_code=303)

    @panel.get("/users")
    async def users(request: Request, q: str = "", page: int = 1):
        total = await db.count_users(q)
        page, pages, offset = paginate(total, page)
        return render(
            request, "users.html",
            users=await db.list_users(q, PAGE_SIZE, offset), total=total, page=page, pages=pages, q=q,
        )

    # --- Ommaviy xabar (faqat to'liq admin) ---

    async def broadcast_page(request: Request, audience: str = "all", text: str = "", **context) -> Response:
        return render(
            request, "broadcast.html",
            job=broadcaster.job,
            audience_counts={a: len(await db.audience_ids(a)) for a in AUDIENCES},
            admin_count=len(settings.admin_id_set),
            audience=audience, text=text, **context,
        )

    @panel.get("/broadcast", dependencies=[Depends(load_admin)])
    async def broadcast(request: Request):
        return await broadcast_page(request)

    @panel.post("/broadcast", dependencies=[Depends(load_admin), Depends(verify_csrf)])
    async def broadcast_send(
        request: Request, user: CurrentUser = Depends(load_admin),
        audience: str = Form("all"), text: str = Form(""), action: str = Form("start"),
    ):
        text = text.strip()
        error = None
        if audience not in AUDIENCES:
            error = "Auditoriya noto'g'ri."
        elif not text:
            error = "Xabar matni bo'sh."
        elif len(text) > TG_TEXT_LIMIT:
            error = f"Xabar {TG_TEXT_LIMIT} belgidan oshmasligi kerak."
        elif broadcaster.running:
            error = "Boshqa tarqatma hali tugamagan."
        if error:
            return await broadcast_page(request, audience, text, flash={"message": error, "kind": "error"})

        def send(user_id: int):
            return bot.send_message(user_id, text, parse_mode=None)

        if action == "test":
            delivered = 0
            for admin_id in settings.admin_id_set:
                try:
                    await send(admin_id)
                    delivered += 1
                except TelegramAPIError:
                    log.warning("Sinov xabari admin %s ga yuborilmadi", admin_id)
            message = f"Sinov xabari {delivered}/{len(settings.admin_id_set)} ta adminga yuborildi."
            return await broadcast_page(request, audience, text, flash={"message": message, "kind": "info"})

        job = await broadcaster.start(audience, send, started_by=f"web:{user.username}")
        log.info("Web panel: %s tarqatmani boshladi (%s, %s ta)", user.username, audience, job.total)
        flash(request, f"Tarqatma boshlandi: {job.total} ta foydalanuvchi.")
        return RedirectResponse("/broadcast", status_code=303)

    @panel.post("/broadcast/stop", dependencies=[Depends(load_admin), Depends(verify_csrf)])
    async def broadcast_stop(request: Request):
        broadcaster.cancel()
        flash(request, "Tarqatma to'xtatilmoqda.", "info")
        return RedirectResponse("/broadcast", status_code=303)

    # --- Hisoblar (faqat to'liq admin) ---

    @panel.get("/settings/admins", dependencies=[Depends(load_admin)])
    async def admins_page(request: Request):
        return render(request, "admins.html", accounts=await db.list_admin_users())

    @panel.post("/settings/admins", dependencies=[Depends(verify_csrf)])
    async def admin_create(
        request: Request, user: CurrentUser = Depends(load_admin),
        username: str = Form(""), password: str = Form(""), role: str = Form("viewer"),
    ):
        username = username.strip().lower()
        error = auth.check_username(username) or auth.check_password(password) or auth.check_role(role)
        if not error and not await db.create_admin_user(username, auth.hash_password(password), role):
            error = "Bunday login allaqachon mavjud."
        if error:
            flash(request, error, "error")
        else:
            log.info("Web panel: %s «%s» hisobini qo'shdi (%s)", user.username, username, role)
            flash(request, f"«{username}» qo'shildi.")
        return RedirectResponse("/settings/admins", status_code=303)

    @panel.post("/settings/admins/{account_id}/password", dependencies=[Depends(verify_csrf)])
    async def admin_reset_password(
        request: Request, account_id: int, user: CurrentUser = Depends(load_admin), password: str = Form(""),
    ):
        if error := auth.check_password(password):
            flash(request, error, "error")
        elif not await db.set_admin_password(account_id, auth.hash_password(password)):
            flash(request, "Hisob topilmadi.", "error")
        else:
            log.info("Web panel: %s #%s hisob parolini yangiladi", user.username, account_id)
            flash(request, "Parol yangilandi.")
        return RedirectResponse("/settings/admins", status_code=303)

    @panel.post("/settings/admins/{account_id}/role", dependencies=[Depends(verify_csrf)])
    async def admin_set_role(
        request: Request, account_id: int, user: CurrentUser = Depends(load_admin), role: str = Form(""),
    ):
        if user.user_id == account_id:
            flash(request, "O'z rolingizni o'zgartira olmaysiz.", "error")
        elif error := auth.check_role(role):
            flash(request, error, "error")
        elif not await db.set_admin_role(account_id, role):
            flash(request, "Hisob topilmadi.", "error")
        else:
            log.info("Web panel: %s #%s hisobga «%s» rolini berdi", user.username, account_id, role)
            flash(request, "Rol o'zgartirildi.")
        return RedirectResponse("/settings/admins", status_code=303)

    @panel.post("/settings/admins/{account_id}/delete", dependencies=[Depends(verify_csrf)])
    async def admin_delete(request: Request, account_id: int, user: CurrentUser = Depends(load_admin)):
        if user.user_id == account_id:
            flash(request, "O'z hisobingizni o'chira olmaysiz.", "error")
        elif not await db.delete_admin_user(account_id):
            flash(request, "Hisob topilmadi.", "error")
        else:
            log.info("Web panel: %s #%s hisobini o'chirdi", user.username, account_id)
            flash(request, "Hisob o'chirildi.")
        return RedirectResponse("/settings/admins", status_code=303)

    # --- O'z parolini o'zgartirish ---

    @panel.get("/settings/password")
    async def password_page(request: Request):
        return render(request, "password.html")

    @panel.post("/settings/password", dependencies=[Depends(verify_csrf)])
    async def password_change(
        request: Request, user: CurrentUser = Depends(load_user),
        current: str = Form(""), new: str = Form(""), repeat: str = Form(""),
    ):
        if user.from_env:
            flash(request, "Asosiy hisob paroli .env faylidagi ADMIN_PASSWORD orqali o'zgartiriladi.", "error")
            return RedirectResponse("/settings/password", status_code=303)

        account = await db.admin_user_by_id(user.user_id)
        if account is None:
            raise LoginRequired
        if not auth.verify_password(current, account.password_hash):
            flash(request, "Joriy parol noto'g'ri.", "error")
        elif new != repeat:
            flash(request, "Yangi parollar bir-biriga mos emas.", "error")
        elif error := auth.check_password(new):
            flash(request, error, "error")
        else:
            await db.set_admin_password(account.id, auth.hash_password(new))
            log.info("Web panel: %s o'z parolini o'zgartirdi", user.username)
            flash(request, "Parol o'zgartirildi.")
        return RedirectResponse("/settings/password", status_code=303)

    app.include_router(panel)
    return app


class _Server(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self):
        # SIGINT/SIGTERM'ni aiogram boshqaradi; to'xtatish WebServer.stop() orqali
        yield


class WebServer:
    def __init__(self, bot: Bot, db: Database, sheets: Sheets | None, broadcaster: Broadcaster):
        config = uvicorn.Config(
            create_app(bot, db, sheets, broadcaster),
            host=settings.web_host, port=settings.web_port, lifespan="off", log_level="info",
            # nginx ortida login cheklovi haqiqiy mijoz IP'si bo'yicha ishlashi uchun
            proxy_headers=True, forwarded_allow_ips=settings.web_forwarded_allow_ips,
        )
        self.server = _Server(config)
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        log.info("Web admin panel: http://%s:%s", settings.web_host, settings.web_port)
        self.task = asyncio.create_task(self.server.serve())

    async def stop(self) -> None:
        self.server.should_exit = True
        if self.task:
            await self.task
