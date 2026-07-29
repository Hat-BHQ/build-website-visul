from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://sync_user:sync@postgres:5432/sync_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    service_token: str
    hqa_service_url: str = "http://hqa-service:8000"
    celery_broker_url: str = "amqp://hq:hq@rabbitmq:5672//"
    celery_result_backend: str = "redis://:redis@redis:6379/1"
    model_config = SettingsConfigDict(case_sensitive=False)


settings = Settings()
