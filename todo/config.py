from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_EXPIRE_SECONDS: int = 60  # TTL

    model_config = SettingsConfigDict(
        # __file__ = gives path of current file (like, Where am I?)
        # __file__ → points to todo/config.py, .parent → goes up one level → todo/ folder
        # .parent again → goes up one more level → day8-secure-todo/ (root folder)
        # / ".env" → adds the .env file name
        # .parent.parent = go up two levels from the current file.

        # alternative way: Option 1: From root (most common)
        # env_file="../.env"
        # .parent.parent method is more robust because it works even if you move folders around.

        env_file=Path(__file__).parent.parent / ".env",  # Adjust if .env location changes
        env_file_encoding="utf-8",
        extra="ignore"  # ignores extra env variables
    )


# THIS is old way, use model_config:
# class Config:
#     env_file = "../.env"
#     env_file_encoding = "utf-8"

settings = Settings()
