from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hostel/PG Life API"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "hostelpg"
    redis_url: str = ""  # optional: caching + rate limiting; in-memory fallback if empty

    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_expire_minutes: int = 60 * 24 * 7

    # Free Gemini API key from https://aistudio.google.com/apikey
    # Leave empty to run fully offline with the built-in fallback AI.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"  # fast, bigger free quota; or gemini-3.8-flash
    gemini_embed_model: str = "gemini-embedding-001"

    # Email (free with a Gmail "app password": https://myaccount.google.com/apppasswords)
    # If SMTP_USER is empty, codes are printed in the backend terminal instead (dev mode).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # defaults to smtp_user
    # Dev mode only (no SMTP): also return the code in the API response so the UI can show it
    show_dev_codes: bool = True

    # Google sign-in: OAuth Client ID from https://console.cloud.google.com/apis/credentials
    google_client_id: str = ""

    ai_daily_limit_per_user: int = 100
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "uploads"

    # Matching: weight of the habits score vs the personality (embedding) score
    habits_weight: float = 0.7

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user.strip() and self.smtp_password.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
