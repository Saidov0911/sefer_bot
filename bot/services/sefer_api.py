"""Sefer backend'idan saytga kirish kodini so'raydi."""
import logging

import aiohttp

from bot.config import settings

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)


class SeferApiError(Exception):
    """Kod berilmadi. too_many — foydalanuvchi limitdan oshgan (qolgan hollarda backend ishlamayapti)."""

    def __init__(self, message: str, too_many: bool = False):
        super().__init__(message)
        self.too_many = too_many


async def request_login_code(
    telegram_id: int, phone: str, first_name: str, last_name: str | None, username: str | None
) -> tuple[str, int]:
    """Qaytaradi: (kod, necha soniya amal qilishi)."""
    url = settings.sefer_api_url.rstrip("/") + "/api/v1/auth/telegram/codes"
    payload = {
        "telegramId": telegram_id,
        "phone": phone,
        "firstName": first_name,
        "lastName": last_name or "",
        "username": username or "",
    }
    headers = {"Authorization": f"Bearer {settings.sefer_api_token}"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 429:
                    raise SeferApiError("too many codes requested", too_many=True)
                if resp.status != 200:
                    raise SeferApiError(f"status {resp.status}: {(await resp.text())[:200]}")
                data = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as e:
        raise SeferApiError(f"{type(e).__name__}: {e}") from e
    return data["code"], int(data["expiresIn"])
