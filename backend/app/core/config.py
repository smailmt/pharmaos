"""Configuration centralisée — variables d'environnement validées par Pydantic."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # App
    APP_NAME: str = "PharmaOS"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Sécurité
    SECRET_KEY: str = "change-me-in-production-min-32-chars-long-abcdefghij"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    POSTGRES_USER: str = "pharmaos"
    POSTGRES_PASSWORD: str = "pharmaos_dev"
    POSTGRES_DB: str = "pharmaos"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # Twilio (SMS + WhatsApp) — optionnel, mode preview si vide
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_SMS: str = ""           # ex: +212XXXXXXXX
    TWILIO_FROM_WHATSAPP: str = ""      # ex: +14155238886 (sandbox Twilio)

    # Business
    DEFAULT_CURRENCY: str = "MAD"
    DEFAULT_VAT_RATE: float = 0.07  # 7% médicaments Maroc
    CREDIT_REMINDER_DAYS_BEFORE: int = 3
    CREDIT_OVERDUE_REMINDER_INTERVAL: int = 7

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Pour Alembic (migrations synchrones)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
