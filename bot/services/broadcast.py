"""Ommaviy xabar yuborish. Bir vaqtda faqat bitta tarqatma ishlaydi; holati bot va web panelda ko'rinadi."""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter

from bot.db import Database

log = logging.getLogger(__name__)

# Telegram limiti ~30 xabar/soniya; zaxira bilan
SEND_DELAY = 0.05

SendFunc = Callable[[int], Awaitable[object]]


@dataclass
class BroadcastJob:
    audience: str
    total: int
    started_by: str
    sent: int = 0
    blocked: int = 0
    failed: int = 0
    cancelled: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def done(self) -> int:
        return self.sent + self.blocked + self.failed

    @property
    def running(self) -> bool:
        return self.finished_at is None

    @property
    def percent(self) -> int:
        return 100 if not self.total else self.done * 100 // self.total


class Broadcaster:
    def __init__(self, db: Database):
        self.db = db
        self.job: BroadcastJob | None = None
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self.job is not None and self.job.running

    async def start(
        self,
        audience: str,
        send: SendFunc,
        started_by: str,
        on_done: Callable[[BroadcastJob], Awaitable[object]] | None = None,
    ) -> BroadcastJob:
        if self.running:
            raise RuntimeError("Boshqa tarqatma hali tugamagan")
        user_ids = await self.db.audience_ids(audience)
        self.job = BroadcastJob(audience=audience, total=len(user_ids), started_by=started_by)
        self._task = asyncio.create_task(self._run(self.job, user_ids, send, on_done))
        return self.job

    def cancel(self) -> None:
        if self.running:
            self.job.cancelled = True

    async def _run(self, job: BroadcastJob, user_ids: list[int], send: SendFunc, on_done) -> None:
        log.info("Tarqatma boshlandi: %s ta foydalanuvchi (%s, %s)", job.total, job.audience, job.started_by)
        try:
            for user_id in user_ids:
                if job.cancelled:
                    break
                try:
                    await self._send_one(send, user_id)
                    job.sent += 1
                except TelegramForbiddenError:  # botni bloklagan yoki akkaunt o'chirilgan
                    job.blocked += 1
                    await self.db.set_user_active(user_id, False)
                except TelegramAPIError as e:
                    job.failed += 1
                    log.warning("Tarqatma: user %s ga yuborilmadi: %s", user_id, e)
                await asyncio.sleep(SEND_DELAY)
        except Exception:
            log.exception("Tarqatma kutilmagan xato bilan to'xtadi")
        finally:
            job.finished_at = datetime.now(timezone.utc)
            log.info("Tarqatma tugadi: sent=%s blocked=%s failed=%s", job.sent, job.blocked, job.failed)

        if on_done:
            try:
                await on_done(job)
            except Exception:
                log.exception("Tarqatma natijasini yuborib bo'lmadi")

    @staticmethod
    async def _send_one(send: SendFunc, user_id: int) -> None:
        try:
            await send(user_id)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            await send(user_id)
