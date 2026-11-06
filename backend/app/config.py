from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings.

    Environment variables take precedence over the repository-root `.env`.
    """

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str
    storage_dir: Path = BACKEND_DIR / "var" / "uploads"  # override with an absolute path
    max_upload_bytes: int = 10 * 1024 * 1024
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
