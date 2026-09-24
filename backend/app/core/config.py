"""
IMANI Business OS — Production Foundation Configuration

Central configuration for all IMANI services.
Supports multi-environment setup via .env.development / .env.staging / .env.production.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Supports .env.development, .env.staging, .env.production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Rental OS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    APP_ENV: str = "development"  # development | staging | production
    LOG_LEVEL: str = "DEBUG"

    # Backward compat: ENVIRONMENT = APP_ENV
    @property
    def ENVIRONMENT(self) -> str:
        return self.APP_ENV

    # ── Security ─────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    JWT_SECRET: Optional[str] = None  # fallback to SECRET_KEY if not set
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    @property
    def effective_jwt_secret(self) -> str:
        return self.JWT_SECRET or self.SECRET_KEY

    # Backward compat: code that uses settings.ALGORITHM still works
    @property
    def ALGORITHM(self) -> str:
        return self.JWT_ALGORITHM

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://imani:imani@localhost:5432/rental"
    )
    DATABASE_POOL_SIZE: int = 30
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.imani.co.ke",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── Notifications (SMS / WhatsApp) ──────────────────────────
    AT_API_KEY: str = ""
    AT_USERNAME: str = ""
    AT_SENDER_ID: str = "Rental OS"
    AT_WHATSAPP_NUMBER: str = ""  # Your WhatsApp Business number linked to AT
    AT_WEBHOOK_BASE_URL: str = ""  # Public URL for AT to call back (e.g. https://yourdomain.com)

    # ── Facebook / Instagram Bot ───────────────────────────────────
    FB_APP_ID: str = ""
    FB_APP_SECRET: str = ""
    FB_PAGE_ACCESS_TOKEN: str = ""
    FB_PAGE_ID: str = ""
    FB_WEBHOOK_SECRET: str = ""
    IG_BUSINESS_ID: str = ""  # Instagram Business Account ID linked to FB Page
    IG_ACCESS_TOKEN: str = ""  # Instagram Graph API token (same as FB_PAGE_ACCESS_TOKEN usually)

    # ── M-Pesa Daraja ────────────────────────────────────────────
    # New MPESA_* names (preferred), fallback to DARAJA_* for backward compat
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_PASSKEY: str = ""
    MPESA_SHORTCODE: str = "174379"
    MPESA_ENVIRONMENT: str = "sandbox"  # sandbox | production
    MPESA_CALLBACK_BASE: str = ""
    # Production default callback secret. Required in production; used as the
    # fallback for business payment gateways that don't set their own.
    MPESA_CALLBACK_SECRET: str = ""

    # Legacy DARAJA_* support (mapped via aliases)
    @property
    def DARAJA_CONSUMER_KEY(self) -> str:
        return self.MPESA_CONSUMER_KEY

    @property
    def DARAJA_CONSUMER_SECRET(self) -> str:
        return self.MPESA_CONSUMER_SECRET

    @property
    def DARAJA_PASSKEY(self) -> str:
        return self.MPESA_PASSKEY

    @property
    def DARAJA_SHORTCODE(self) -> str:
        return self.MPESA_SHORTCODE

    @property
    def DARAJA_ENVIRONMENT(self) -> str:
        return self.MPESA_ENVIRONMENT

    # ── Storage ──────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"  # local | gdrive | s3
    STORAGE_LOCAL_PATH: Path = Path("/home/nyorii/Projects/rental-os/storage")
    GOOGLE_DRIVE_CLIENT_ID: str = ""
    GOOGLE_DRIVE_CLIENT_SECRET: str = ""

    # ── CCTV ─────────────────────────────────────────────────────
    CCTV_STORAGE_PATH: Path = Path("/data/imani/cctv")
    CCTV_RETAIN_DAYS: int = 30

    # ── AI ───────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_MODEL: str = "imani:latest"
    OPENAI_API_KEY: str = ""

    # ── Email ────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@imani.co.ke"

    # ── Rate Limiting ────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5

    # ── Business Defaults ────────────────────────────────────────
    DEFAULT_CURRENCY: str = "KES"
    DEFAULT_TAX_RATE: float = 0.16  # 16% VAT
    TRIAL_DAYS: int = 14

    # ── Encryption ───────────────────────────────────────────────
    ENCRYPTION_KEY: str = "change-me-in-production"

    # ── Computed Properties ──────────────────────────────────────
    @property
    def access_token_expiry(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

    @property
    def refresh_token_expiry(self) -> timedelta:
        return timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)


settings = Settings()
