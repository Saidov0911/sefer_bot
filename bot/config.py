from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str

    # Majburiy obuna: bot shu kanalda admin bo'lishi shart
    channel_id: str  # "@sefer_uz" yoki "-100..."
    channel_url: str
    instagram_url: str

    # Anketalar yuboriladigan yopiq guruh va bot adminlari
    admin_chat_id: int
    admin_ids: str = ""  # vergul bilan: "111,222"

    required_referrals: int = 3
    essay_max_words: int = 200

    db_path: Path = Path("data/bot.db")
    redis_url: str | None = None

    # Google Sheets (ixtiyoriy — bo'sh bo'lsa o'chirilgan)
    google_credentials_file: Path | None = None
    google_sheet_id: str | None = None
    google_worksheet: str = "Arizalar"

    @cached_property
    def admin_id_set(self) -> set[int]:
        return {int(x) for x in self.admin_ids.replace(" ", "").split(",") if x}

    @property
    def sheets_enabled(self) -> bool:
        return bool(self.google_credentials_file and self.google_sheet_id)


settings = Settings()
