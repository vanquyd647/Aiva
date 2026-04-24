"""Application settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "AI Assist Backend"
    ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "sqlite:///./backend/app.db"
    REDIS_URL: str | None = None
    AUTO_CREATE_DB_SCHEMA: bool = True

    CORS_ALLOW_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    INITIAL_ADMIN_EMAIL: str = "admin@aiassist.app"
    INITIAL_ADMIN_PASSWORD: str = "ChangeMeNow!123"
    INITIAL_ADMIN_NAME: str = "System Admin"

    ALLOW_PUBLIC_REGISTRATION: bool = False
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 8
    RATE_LIMIT_GEMINI_KEY_ROTATE_PER_MINUTE: int = 4

    USER_LIST_CACHE_TTL_SECONDS: int = 30

    GEMINI_SECRET_ENCRYPTION_KEY: str | None = None
    GEMINI_FALLBACK_ENV_API_KEY_ENABLED: bool = True
    GEMINI_VALIDATION_MODEL: str = "gemma-4-31b-it"

    USAGE_WINDOW_DAYS: int = 30
    QUOTA_ALERT_THRESHOLD_RATIO: float = 0.8
    QUOTA_USER_MESSAGE_LIMIT: int = 400
    QUOTA_USER_TOKEN_LIMIT: int = 250000
    QUOTA_ADMIN_MESSAGE_LIMIT: int = 3000
    QUOTA_ADMIN_TOKEN_LIMIT: int = 1500000

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    def validate_runtime(self) -> None:
        """Validate security-sensitive settings before app startup."""
        if not self.is_production:
            return

        insecure_secrets = {
            "change-this-in-production",
            "replace-with-a-strong-random-secret",
            "",
        }
        insecure_admin_passwords = {
            "ChangeMeNow!123",
            "admin",
            "password",
            "",
        }

        if self.SECRET_KEY in insecure_secrets:
            raise ValueError("SECRET_KEY must be changed in production")

        if self.INITIAL_ADMIN_PASSWORD in insecure_admin_passwords:
            raise ValueError("INITIAL_ADMIN_PASSWORD must be changed in production")

        if self.CORS_ALLOW_ORIGINS == ["*"]:
            raise ValueError("CORS_ALLOW_ORIGINS cannot be wildcard in production")

        if self.AUTO_CREATE_DB_SCHEMA:
            raise ValueError("AUTO_CREATE_DB_SCHEMA must be false in production")

    @property
    def sqlite_connect_args(self) -> dict:
        if self.DATABASE_URL.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}


settings = Settings()
