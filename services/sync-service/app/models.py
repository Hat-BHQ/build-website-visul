from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def uid() -> str:
    return str(uuid4())


class SyncJob(Base):
    __tablename__ = "sync_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_sync_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    marketplace: Mapped[str] = mapped_column(String(32), index=True)
    sync_type: Mapped[str] = mapped_column(String(32), default="status")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    requested_by: Mapped[str] = mapped_column(String(36), index=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MarketplaceAccount(Base):
    __tablename__ = "marketplace_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    marketplace: Mapped[str] = mapped_column(String(32), index=True)
    account_name: Mapped[str] = mapped_column(String(128))
    secret_ref: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    remaining_quota: Mapped[int] = mapped_column(Integer, default=0)
    concurrent_limit: Mapped[int] = mapped_column(Integer, default=1)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
