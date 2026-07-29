from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Listing, ListingSnapshot
from app.schemas import BulkListingIn
from app.security import require_permission
from app.service import upsert_listing


def serialize(item: Listing) -> dict:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Listing).count() == 0:
            samples = BulkListingIn(listings=[
                {
                    "marketplace": "ebay", "external_listing_id": "EBAY-DEMO-001",
                    "listing_title": "Vintage stereo receiver demo", "seller_name": "Demo Seller",
                    "current_price": 899.0, "shipping_price": 45.0, "total_price": 944.0,
                    "currency": "USD", "quantity": 1, "listing_views": 42,
                    "listing_status": "active", "category_name": "Vintage Stereo Receivers",
                },
                {
                    "marketplace": "reverb", "external_listing_id": "REVERB-DEMO-001",
                    "listing_title": "Tube amplifier demo", "shop_name": "Demo Audio Shop",
                    "current_price": 1200.0, "shipping_price": 0.0, "total_price": 1200.0,
                    "currency": "USD", "quantity": 2, "listing_status": "active",
                    "category_name": "Amplifiers & Preamps",
                },
            ])
            for item in samples.listings:
                upsert_listing(db, item)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed()
    yield


app = FastAPI(title="HQA Service", version="2.0.0", lifespan=lifespan)


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.query(Listing).limit(1).all()
    return {"status": "ready", "database": "ok"}


@app.get("/internal/v1/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    by_marketplace = dict(db.query(Listing.marketplace, func.count(Listing.id)).group_by(Listing.marketplace).all())
    active = db.query(func.count(Listing.id)).filter(Listing.listing_status == "active").scalar() or 0
    ended = db.query(func.count(Listing.id)).filter(Listing.listing_status != "active").scalar() or 0
    return {"active_listings": active, "inactive_listings": ended, "by_marketplace": by_marketplace}


@app.get("/internal/v1/listings")
def listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    marketplace: str | None = None,
    status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    query = db.query(Listing)
    if marketplace:
        query = query.filter(Listing.marketplace == marketplace.lower())
    if status:
        query = query.filter(Listing.listing_status == status)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Listing.listing_title.ilike(pattern), Listing.external_listing_id.ilike(pattern)))
    total = query.count()
    rows = query.order_by(Listing.last_seen_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [serialize(row) for row in rows], "page": page, "page_size": page_size,
            "total": total, "pages": max(1, (total + page_size - 1) // page_size)}


@app.get("/internal/v1/listings/{listing_id}")
def listing_detail(
    listing_id: str,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    item = db.query(Listing).filter(Listing.id == listing_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Listing not found")
    snapshots = db.query(ListingSnapshot).filter(ListingSnapshot.listing_id == listing_id).order_by(
        ListingSnapshot.captured_at.desc()).limit(100).all()
    return {"listing": serialize(item), "snapshots": [
        {column.name: getattr(s, column.name) for column in s.__table__.columns} for s in snapshots
    ]}


@app.post("/internal/v1/listings/bulk-upsert")
def bulk_upsert(
    payload: BulkListingIn,
    x_service_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if x_service_token != settings.service_token:
        raise HTTPException(status_code=403, detail="Invalid service token")
    created = 0
    for item in payload.listings:
        _, was_created = upsert_listing(db, item)
        created += int(was_created)
    db.commit()
    return {"processed": len(payload.listings), "created": created, "updated": len(payload.listings) - created}
