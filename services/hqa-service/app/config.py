from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://hqa_user:hqa@postgres:5432/hqa_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    service_token: str
    demo_data_enabled: bool = False
    alert_price_drop_threshold_pct: float = 20.0
    alert_out_of_stock_spike_threshold_pct: float = 50.0
    alert_new_seller_min_count: int = 3
    hqa_price_drop_alert_percent: float = 20.0
    hqa_price_drop_warning_alert_percent: float = 10.0
    hqa_price_drop_critical_alert_percent: float = 20.0
    hqa_price_alert_min_sample: int = 5
    hqa_new_seller_lookback_days: int = 30
    hqa_out_of_stock_min_count: int = 10
    hqa_out_of_stock_alert_percent: float = 30.0
    hqa_out_of_stock_baseline_days: int = 7
    model_config = SettingsConfigDict(case_sensitive=False)


settings = Settings()
