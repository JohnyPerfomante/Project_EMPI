from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_REVISION = "4328cf26390c98c5e3c738b4460a05b95f4911f5"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://empi:empi@127.0.0.1:55432/empi"
    jwt_secret: SecretStr = SecretStr("")
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    access_minutes: int = Field(15, ge=1, le=60)
    refresh_days: int = Field(7, ge=1, le=30)
    login_limit: int = Field(10, ge=3, le=100)
    registration_limit: int = Field(5, ge=1, le=100)
    nlp_provider: Literal["local", "test"] = "local"
    nlp_model: str = DEFAULT_MODEL
    nlp_revision: str = DEFAULT_REVISION
    nlp_device: str = "cpu"
    nlp_threads: int = Field(4, ge=1, le=32)
    nlp_offline: bool = True
    stanza_dir: str | None = None
    job_lease_seconds: int = Field(300, ge=15)
    demo_password: SecretStr = SecretStr("")
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def secure_environment(self):
        if self.nlp_provider == "test" and self.app_env != "test":
            raise ValueError("The test NLP provider requires APP_ENV=test")
        if self.app_env == "production" and (
            not self.cookie_secure or len(self.jwt_secret.get_secret_value()) < 32 or "*" in self.cors_origins
        ):
            raise ValueError("Production requires HTTPS cookies, a strong JWT secret and explicit origins")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
