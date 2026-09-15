from datetime import datetime, timedelta, timezone

TASHKENT = timezone(timedelta(hours=5))


def local_time(utc: str | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """SQLite datetime('now') (UTC) qiymatini Toshkent vaqtida formatlaydi."""
    if not utc:
        return ""
    return datetime.fromisoformat(utc).replace(tzinfo=timezone.utc).astimezone(TASHKENT).strftime(fmt)
