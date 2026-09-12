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
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_USERS: str = "todo.users"
    KAFKA_TOPIC_TASKS: str = "todo.tasks"
    KAFKA_CONSUMER_GROUP: str = "todo-api"

    # kafka publisher (outbox → broker)
    OUTBOX_BATCH_SIZE: int = 100
    OUTBOX_POLL_SECONDS: float = 2.0
    OUTBOX_MAX_ATTEMPTS: int = 5

    # kafka consumer (broker → handlers)
    KAFKA_COMMIT_EVERY: int = 10
    KAFKA_COMMIT_INTERVAL_SEC: float = 5.0

    model_config = SettingsConfigDict(
        # __file__ = path of current file, .parent.parent = go up two levels from the current file.
        env_file=Path(__file__).parent.parent / ".env",  # Adjust if .env location changes
        env_file_encoding="utf-8",
        extra="ignore"  # ignores extra env variables
    )


settings = Settings()
