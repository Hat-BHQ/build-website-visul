from datetime import datetime
from uuid import uuid4
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def uid() -> str:
    return str(uuid4())


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("marketplace", "external_listing_id", name="uq_market_listing"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    marketplace: Mapped[str] = mapped_column(String(32), index=True)
    external_listing_id: Mapped[str] = mapped_column(String(128), index=True)
    listing_title: Mapped[str] = mapped_column(Text)
    listing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shop_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    listing_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    shipping_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_status_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(String(36), index=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    shipping_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_status: Mapped[str] = mapped_column(String(32))
    state_hash: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
