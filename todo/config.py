from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database — override via .env or container env
    DATABASE_URL: str = "postgresql+psycopg2://todo_user:todo_password@localhost:5432/todo_db"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_EXPIRE_SECONDS: int = 60  # TTL

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_ENABLED: bool = True
    KAFKA_TOPIC_USERS: str
    KAFKA_TOPIC_TASKS: str
    KAFKA_CONSUMER_GROUP: str

    # kafka publisher (outbox → broker)
    OUTBOX_BATCH_SIZE: int
    OUTBOX_POLL_SECONDS: float
    OUTBOX_MAX_ATTEMPTS: int

    # kafka consumer (broker → handlers)
    KAFKA_COMMIT_EVERY: int
    KAFKA_COMMIT_INTERVAL_SEC: float

    model_config = SettingsConfigDict(
        # __file__ = gives path of current file (like, Where am I?)
        # __file__ → points to todo/config.py, .parent → goes up one level → todo/ folder
        # .parent again → goes up one more level → todo-api/ (root folder)
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
