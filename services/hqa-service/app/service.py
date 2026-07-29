import hashlib
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Listing, ListingSnapshot
from app.schemas import ListingIn


def state_hash(item: ListingIn) -> str:
    state = {
        "current_price": item.current_price,
        "shipping_price": item.shipping_price,
        "total_price": item.total_price,
        "quantity": item.quantity,
        "listing_views": item.listing_views,
        "listing_status": item.listing_status,
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def upsert_listing(db: Session, item: ListingIn) -> tuple[Listing, bool]:
    listing = db.query(Listing).filter(
        Listing.marketplace == item.marketplace.lower(),
        Listing.external_listing_id == item.external_listing_id,
    ).first()
    created = listing is None
    if listing is None:
        listing = Listing(
            marketplace=item.marketplace.lower(),
            external_listing_id=item.external_listing_id,
            listing_title=item.listing_title,
        )
        db.add(listing)
        db.flush()
    new_hash = state_hash(item)
    changed = listing.state_hash != new_hash
    for field, value in item.model_dump().items():
        if field == "marketplace":
            value = value.lower()
        setattr(listing, field, value)
    listing.last_seen_at = datetime.utcnow()
    listing.state_hash = new_hash
    if changed:
        db.flush()
        db.add(ListingSnapshot(
            listing_id=listing.id,
            current_price=item.current_price,
            shipping_price=item.shipping_price,
            total_price=item.total_price,
            quantity=item.quantity,
            listing_views=item.listing_views,
            listing_status=item.listing_status,
            state_hash=new_hash,
        ))
    return listing, created
