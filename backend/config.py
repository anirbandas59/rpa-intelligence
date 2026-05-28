from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    secret_key: str
    access_token_expire_minutes: int = 1440

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
