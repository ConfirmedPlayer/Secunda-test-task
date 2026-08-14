from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    rabbitmq_url: str
    api_key: str

    gateway_delay_min: float = 2.0
    gateway_delay_max: float = 5.0
    gateway_success_rate: float = 0.9

    webhook_timeout: float = 5.0
    webhook_max_attempts: int = 3
    webhook_backoff_base: float = 1.0

    outbox_poll_interval: float = 0.5
    outbox_batch_size: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
