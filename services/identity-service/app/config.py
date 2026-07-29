from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://identity_user:identity@postgres:5432/identity_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 10
    session_idle_minutes: int = 15
    session_absolute_hours: int = 24
    bootstrap_superadmin_email: str = "root@example.com"
    bootstrap_superadmin_password: str = "ChangeMe123!"
    bootstrap_hqa_admin_email: str = "hqa.admin@example.com"
    bootstrap_hqa_admin_password: str = "Admin123!"
    bootstrap_hqa_user_email: str = "hqa.user@example.com"
    bootstrap_hqa_user_password: str = "User123!"
    model_config = SettingsConfigDict(case_sensitive=False)


settings = Settings()
