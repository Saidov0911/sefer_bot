"""Web panel uchun Sefer saytining admin API'si (foydalanuvchilar, do'konlar, bandlovlar,
shubhali juftliklar). Bot bilan bir xil manzil va token ishlatiladi."""
import aiohttp

from bot.config import settings

TIMEOUT = aiohttp.ClientTimeout(total=15)


class SiteApiError(Exception):
    """Sayt API'si javob bermadi yoki xato qaytardi. Xabar panelda ko'rsatiladi."""


async def _request(method: str, path: str, **kwargs) -> dict:
    if not settings.login_enabled:
        raise SiteApiError("Sayt API'si sozlanmagan (.env da SEFER_API_URL va SEFER_API_TOKEN).")
    url = settings.sefer_api_url.rstrip("/") + "/api/v1/admin" + path
    headers = {"Authorization": f"Bearer {settings.sefer_api_token}"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.request(method, url, headers=headers, **kwargs) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise SiteApiError(data.get("error") or f"Sayt API'si {resp.status} qaytardi.")
                return data
    except (aiohttp.ClientError, TimeoutError, ValueError) as e:
        raise SiteApiError(f"Sayt API'siga ulanib bo'lmadi ({type(e).__name__}).") from e


async def stats() -> dict:
    return await _request("GET", "/stats")


async def users(q: str, page: int, limit: int) -> dict:
    return await _request("GET", "/users", params={"q": q, "page": page, "limit": limit})


async def shops() -> dict:
    return await _request("GET", "/shops")


async def bookings(page: int, limit: int) -> dict:
    return await _request("GET", "/bookings", params={"page": page, "limit": limit})


async def reviews(page: int, limit: int) -> dict:
    return await _request("GET", "/reviews", params={"status": "pending", "page": page, "limit": limit})


async def decide_review(review_id: int, verdict: str) -> dict:
    return await _request("POST", f"/reviews/{review_id}", json={"verdict": verdict})


async def refresh_reviews() -> dict:
    return await _request("POST", "/reviews/refresh")
