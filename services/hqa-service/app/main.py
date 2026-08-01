from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.keyword_catalog import load_keyword_catalog
from app.report_config import REPORT_GROUPS_BY_KEY, get_keyword_metadata
from app.security import require_permission
from app.service import (
    fetch_dashboard_counts,
    fetch_listing_by_id,
    fetch_listings,
    fetch_marketplace_filter_options,
    fetch_marketplace_raw_listings,
    fetch_marketplace_report_listings,
    fetch_marketplace_report_summary,
)


app = FastAPI(title="HQA Service", version="2.0.0")


def _today_hcm():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


@app.on_event("startup")
def startup_validate_keyword_catalog():
    try:
        load_keyword_catalog()
    except RuntimeError as exc:
        raise RuntimeError(f"HQA keyword catalog initialization failed: {exc}") from exc


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


@app.get("/internal/v1/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_dashboard_counts(db)


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
    items, total = fetch_listings(
        db,
        page=page,
        page_size=page_size,
        marketplace=marketplace,
        status=status,
        q=q,
    )
    return {
        "items": [dict(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@app.get("/internal/v1/listings/{listing_id}")
def listing_detail(
    listing_id: str,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    item = fetch_listing_by_id(db, listing_id)
    if not item:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"listing": dict(item), "snapshots": []}


@app.get("/internal/v1/reports/marketplace/summary")
@app.get("/reports/marketplace/summary")
def marketplace_report_summary(
    report_date: date | None = Query(default=None),
    marketplace: str | None = None,
    q: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    listing_location: str | None = None,
    category_name: str | None = None,
    seller: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    listing_status: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    selected_date = report_date or _today_hcm()
    payload = fetch_marketplace_report_summary(
        db,
        report_date=selected_date,
        marketplace=marketplace,
        q=q,
        brand=brand,
        model=model,
        category=category,
        listing_location=listing_location,
        category_name=category_name,
        seller=seller,
        condition=condition,
        buying_options=buying_options,
        listing_status=listing_status,
        price_min=price_min,
        price_max=price_max,
    )
    payload["keyword_catalog"] = get_keyword_metadata()
    return payload


@app.get("/internal/v1/reports/marketplace/listings")
@app.get("/reports/marketplace/listings")
def marketplace_report_listings(
    report_key: str,
    report_date: date | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    q: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    listing_location: str | None = None,
    category_name: str | None = None,
    seller: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    listing_status: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    sort: str = Query(default="price_desc"),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    if report_key not in REPORT_GROUPS_BY_KEY:
        raise HTTPException(status_code=400, detail="Invalid report_key")

    selected_report_date = report_date
    selected_date_from = date_from
    selected_date_to = date_to
    try:
        items, total = fetch_marketplace_report_listings(
            db,
            report_key=report_key,
            report_date=selected_report_date,
            date_from=selected_date_from,
            date_to=selected_date_to,
            page=page,
            page_size=page_size,
            q=q,
            marketplace=marketplace,
            brand=brand,
            model=model,
            category=category,
            listing_location=listing_location,
            category_name=category_name,
            seller=seller,
            condition=condition,
            buying_options=buying_options,
            listing_status=listing_status,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    applied_filters = {
        "q": q,
        "marketplace": marketplace,
        "brand": brand,
        "model": model,
        "category": category,
        "listing_location": listing_location,
        "category_name": category_name,
        "seller": seller,
        "condition": condition,
        "buying_options": buying_options,
        "listing_status": listing_status,
        "price_min": price_min,
        "price_max": price_max,
        "date_from": selected_date_from.isoformat() if selected_date_from else None,
        "date_to": selected_date_to.isoformat() if selected_date_to else None,
        "sort": sort,
    }
    return {
        "report_key": report_key,
        "report_date": selected_report_date.isoformat() if selected_report_date else None,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "applied_filters": applied_filters,
    }


@app.get("/internal/v1/reports/marketplace/raw-listings")
@app.get("/reports/marketplace/raw-listings")
def marketplace_raw_listings(
    report_date: date = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    q: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    listing_location: str | None = None,
    category_name: str | None = None,
    seller: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    listing_status: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    sort: str = Query(default="collected_at_desc"),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    try:
        items, total = fetch_marketplace_raw_listings(
            db,
            report_date=report_date,
            page=page,
            page_size=page_size,
            q=q,
            marketplace=marketplace,
            brand=brand,
            model=model,
            category=category,
            listing_location=listing_location,
            category_name=category_name,
            seller=seller,
            condition=condition,
            buying_options=buying_options,
            listing_status=listing_status,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "report_date": report_date.isoformat(),
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "applied_filters": {
            "q": q,
            "marketplace": marketplace,
            "brand": brand,
            "model": model,
            "category": category,
            "listing_location": listing_location,
            "category_name": category_name,
            "seller": seller,
            "condition": condition,
            "buying_options": buying_options,
            "listing_status": listing_status,
            "price_min": price_min,
            "price_max": price_max,
            "sort": sort,
        },
    }


@app.get("/internal/v1/reports/marketplace/filter-options")
@app.get("/reports/marketplace/filter-options")
def marketplace_filter_options(
    report_date: date = Query(...),
    view: str = Query(default="all_listings"),
    report_key: str | None = None,
    q: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    category_name: str | None = None,
    buying_options: str | None = None,
    listing_status: str | None = None,
    seller: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    try:
        return fetch_marketplace_filter_options(
            db,
            report_date=report_date,
            view=view,
            report_key=report_key,
            q=q,
            marketplace=marketplace,
            brand=brand,
            model=model,
            category=category,
            listing_location=listing_location,
            condition=condition,
            category_name=category_name,
            buying_options=buying_options,
            listing_status=listing_status,
            seller=seller,
            price_min=price_min,
            price_max=price_max,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/v1/listings/bulk-upsert")
def bulk_upsert(
    payload: dict,
    x_service_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=501,
        detail="Real HQA sync is not implemented yet. Demo data generation is disabled.",
    )