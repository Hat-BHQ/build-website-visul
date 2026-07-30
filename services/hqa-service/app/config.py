from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://hqa_user:hqa@postgres:5432/hqa_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    service_token: str
    demo_data_enabled: bool = False
    model_config = SettingsConfigDict(case_sensitive=False)


settings = Settings()
