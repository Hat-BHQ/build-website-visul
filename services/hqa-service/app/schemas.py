from datetime import datetime
from pydantic import BaseModel, Field


class ListingIn(BaseModel):
    marketplace: str
    external_listing_id: str
    listing_title: str
    listing_url: str | None = None
    seller_name: str | None = None
    shop_name: str | None = None
    category_name: str | None = None
    condition_name: str | None = None
    listing_location: str | None = None
    image_url: str | None = None
    current_price: float | None = None
    shipping_price: float | None = None
    total_price: float | None = None
    currency: str | None = None
    quantity: int | None = None
    listing_views: int | None = None
    listing_status: str = "active"
    published_at: datetime | None = None


class BulkListingIn(BaseModel):
    listings: list[ListingIn] = Field(min_length=1, max_length=1000)
