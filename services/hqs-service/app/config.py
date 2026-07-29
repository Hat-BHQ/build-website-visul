from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://hqs_user:hqs@postgres:5432/hqs_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    model_config = SettingsConfigDict(case_sensitive=False)
settings = Settings()
