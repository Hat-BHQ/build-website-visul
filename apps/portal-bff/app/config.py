from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    identity_service_url: str = "http://identity-service:8000"
    hqa_service_url: str = "http://hqa-service:8000"
    sync_service_url: str = "http://sync-api:8000"
    hqs_service_url: str = "http://hqs-service:8000"
    cookie_name: str = "hq_refresh"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    allowed_origins: str = "http://localhost:8080,http://localhost:5173"
    model_config = SettingsConfigDict(case_sensitive=False)

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


settings = Settings()
