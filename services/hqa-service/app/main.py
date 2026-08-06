from datetime import date, datetime
import csv
import io
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.keyword_catalog import load_keyword_catalog
from app.report_config import REPORT_GROUPS_BY_KEY, get_keyword_metadata
from app.security import require_permission
from app.service import (
    fetch_all_listings,
    fetch_all_listings_export_rows,
    fetch_all_listings_filter_option_page,
    fetch_all_listings_filter_options,
    fetch_all_listings_summary,
    fetch_duplicate_listing_groups,
    fetch_duplicate_listing_summary,
    fetch_dashboard_counts,
    fetch_hqa_dashboard_alerts,
    fetch_hqa_dashboard_export_rows,
    fetch_hqa_dashboard_filter_options,
    fetch_hqa_dashboard_prices_by_keyword,
    fetch_hqa_dashboard_prices_summary,
    fetch_hqa_dashboard_prices_trend,
    fetch_hqa_dashboard_sellers_summary,
    fetch_hqa_dashboard_sellers_trend,
    fetch_hqa_dashboard_top_sellers,
    fetch_listing_by_id,
    fetch_listings,
    fetch_marketplace_filter_options,
    fetch_marketplace_dashboard_alerts,
    fetch_marketplace_dashboard_keyword_summary,
    fetch_marketplace_dashboard_price_trend,
    fetch_marketplace_dashboard_seller_trend,
    fetch_marketplace_dashboard_status_trend,
    fetch_marketplace_dashboard_summary,
    fetch_marketplace_raw_listings_export,
    fetch_marketplace_report_listings_export,
    fetch_marketplace_raw_listings,
    fetch_marketplace_report_listings,
    fetch_marketplace_report_summary,
    cleanup_duplicate_listings,
)


app = FastAPI(title="HQA Service", version="2.0.0")


class DuplicateCleanupRequest(BaseModel):
    confirmation: str


def _today_hcm():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def _to_csv_response(filename: str, rows: list[dict], *, include_bom: bool = False) -> Response:
    if not rows:
        rows = [{"message": "no_data"}]
    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    content = output.getvalue()
    if include_bom:
        content = "\ufeff" + content
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _get_query_list(request: Request, *keys: str) -> list[str] | None:
    values: list[str] = []
    for key in keys:
        for raw_value in request.query_params.getlist(key):
            normalized = (raw_value or "").strip()
            if normalized:
                values.append(normalized)
    if not values:
        return None
    return list(dict.fromkeys(values))


def _collect_hqa_dashboard_filters(
    request: Request,
    *,
    keyword: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: float | None,
    max_price: float | None,
    currency: str | None,
) -> dict:
    return {
        "keyword": keyword,
        "marketplaces": _get_query_list(request, "marketplace", "marketplaces"),
        "brands": _get_query_list(request, "brand", "brands"),
        "models": _get_query_list(request, "model", "models"),
        "statuses": _get_query_list(request, "status", "statuses"),
        "category_names": _get_query_list(request, "category_name", "category_names"),
        "buying_options": _get_query_list(request, "buying_option", "buying_options"),
        "sellers": _get_query_list(request, "seller", "sellers"),
        "currency": currency,
        "date_from": date_from,
        "date_to": date_to,
        "min_price": min_price,
        "max_price": max_price,
    }


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


@app.get("/internal/v1/hqa/listings")
def hqa_all_listings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    condition: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    category_name: list[str] | None = Query(default=None),
    buying_option: list[str] | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    sort_collected: str = Query(default="newest"),
    search: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    try:
        items, pagination = fetch_all_listings(
            db,
            page=page,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
            marketplace=marketplace,
            brand=brand,
            model=model,
            conditions=condition,
            statuses=status,
            category_names=category_name,
            buying_options=buying_option,
            min_price=min_price,
            max_price=max_price,
            sort_collected=sort_collected,
            search=search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "items": items,
        **pagination,
        "applied_filters": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "marketplace": marketplace,
            "brand": brand,
            "model": model,
            "condition": condition or [],
            "status": status or [],
            "category_name": category_name or [],
            "buying_option": buying_option or [],
            "min_price": min_price,
            "max_price": max_price,
            "sort_collected": sort_collected,
            "search": search,
        },
    }


@app.get("/internal/v1/hqa/listings/summary")
def hqa_all_listings_summary(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    condition: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    category_name: list[str] | None = Query(default=None),
    buying_option: list[str] | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    search: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    try:
        return fetch_all_listings_summary(
            db,
            from_date=from_date,
            to_date=to_date,
            marketplace=marketplace,
            brand=brand,
            model=model,
            conditions=condition,
            statuses=status,
            category_names=category_name,
            buying_options=buying_option,
            min_price=min_price,
            max_price=max_price,
            search=search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/listings/filter-options")
def hqa_all_listings_filter_options(
    field: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    condition: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    category_name: list[str] | None = Query(default=None),
    buying_option: list[str] | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    search: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.view")),
):
    if field:
        try:
            return fetch_all_listings_filter_option_page(
                db,
                field=field,
                page=page,
                page_size=page_size,
                search=search,
                from_date=from_date,
                to_date=to_date,
                marketplace=marketplace,
                brand=brand,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return fetch_all_listings_filter_options(
            db,
            from_date=from_date,
            to_date=to_date,
            marketplace=marketplace,
            brand=brand,
            model=model,
            conditions=condition,
            statuses=status,
            category_names=category_name,
            buying_options=buying_option,
            min_price=min_price,
            max_price=max_price,
            search=search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/listings/export")
def hqa_all_listings_export(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    condition: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    category_name: list[str] | None = Query(default=None),
    buying_option: list[str] | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    sort_collected: str = Query(default="newest"),
    search: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.listings.export")),
):
    try:
        rows = fetch_all_listings_export_rows(
            db,
            from_date=from_date,
            to_date=to_date,
            marketplace=marketplace,
            brand=brand,
            model=model,
            conditions=condition,
            statuses=status,
            category_names=category_name,
            buying_options=buying_option,
            min_price=min_price,
            max_price=max_price,
            sort_collected=sort_collected,
            search=search,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No data available for export")
    return _to_csv_response("hqa_all_listings.csv", rows, include_bom=True)


@app.get("/internal/v1/hqa/data-check/duplicates/summary")
def hqa_duplicate_listing_summary(
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.data_cleanup.view")),
):
    return fetch_duplicate_listing_summary(db)


@app.get("/internal/v1/hqa/data-check/duplicates")
def hqa_duplicate_listing_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    marketplace: str | None = None,
    listing_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.data_cleanup.view")),
):
    try:
        return fetch_duplicate_listing_groups(
            db,
            page=page,
            page_size=page_size,
            marketplace=marketplace,
            listing_id=listing_id,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/internal/v1/hqa/data-check/duplicates/cleanup")
def hqa_duplicate_listing_cleanup(
    payload: DuplicateCleanupRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.data_cleanup.execute")),
):
    if payload.confirmation != "DELETE_DUPLICATE_LISTINGS":
        raise HTTPException(status_code=400, detail="Invalid confirmation token")
    try:
        return cleanup_duplicate_listings(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/filter-options")
def hqa_dashboard_filter_options(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_filter_options(db, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/sellers/summary")
def hqa_dashboard_sellers_summary(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_sellers_summary(db, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/sellers/trend")
def hqa_dashboard_sellers_trend(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    granularity: str = Query(default="month"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_sellers_trend(db, granularity=granularity, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/sellers/top")
def hqa_dashboard_sellers_top(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_top_sellers(db, limit=limit, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/prices/summary")
def hqa_dashboard_prices_summary(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_prices_summary(db, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/prices/trend")
def hqa_dashboard_prices_trend(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    granularity: str = Query(default="month"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_prices_trend(db, granularity=granularity, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/prices/by-keyword")
def hqa_dashboard_prices_by_keyword(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_prices_by_keyword(db, limit=limit, **filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/alerts")
def hqa_dashboard_alerts(
    request: Request,
    keyword: str | None = None,
    currency: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
    )
    try:
        return fetch_hqa_dashboard_alerts(
            db,
            **filters,
            price_drop_threshold_pct=settings.hqa_price_drop_alert_percent,
            min_sample_for_price_alert=settings.hqa_price_alert_min_sample,
            new_seller_lookback_days=settings.hqa_new_seller_lookback_days,
            out_of_stock_min_count=settings.hqa_out_of_stock_min_count,
            out_of_stock_alert_percent=settings.hqa_out_of_stock_alert_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/internal/v1/hqa/dashboard/export")
def hqa_dashboard_export(
    request: Request,
    dataset: str = Query(default="sellers_summary"),
    granularity: str = Query(default="month"),
    top_limit: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
    currency: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = _collect_hqa_dashboard_filters(
        request,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
    )
    try:
        rows = fetch_hqa_dashboard_export_rows(
            db,
            dataset=dataset,
            granularity=granularity,
            top_limit=top_limit,
            **filters,
            price_drop_threshold_pct=settings.hqa_price_drop_alert_percent,
            min_sample_for_price_alert=settings.hqa_price_alert_min_sample,
            new_seller_lookback_days=settings.hqa_new_seller_lookback_days,
            out_of_stock_min_count=settings.hqa_out_of_stock_min_count,
            out_of_stock_alert_percent=settings.hqa_out_of_stock_alert_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="No data available for export")
    return _to_csv_response(f"hqa_dashboard_{dataset}.csv", rows, include_bom=True)


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
    page_size: int = Query(default=50, ge=1, le=200),
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
    report_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
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
        items, pagination = fetch_marketplace_raw_listings(
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
        "items": items,
        "report_date": report_date.isoformat() if report_date else None,
        **pagination,
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
    report_date: date | None = Query(default=None),
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
    if view == "report" and report_date is None:
        raise HTTPException(status_code=422, detail="report_date is required for report view")
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


@app.get("/internal/v1/reports/marketplace/raw-listings/export-csv")
def marketplace_raw_listings_export_csv(
    report_date: date | None = Query(default=None),
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
    rows = fetch_marketplace_raw_listings_export(
        db,
        report_date=report_date,
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
    return _to_csv_response("hqa_all_listings.csv", rows)


@app.get("/internal/v1/reports/marketplace/listings/export-csv")
def marketplace_report_listings_export_csv(
    report_key: str,
    report_date: date | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
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
    rows = fetch_marketplace_report_listings_export(
        db,
        report_key=report_key,
        report_date=report_date,
        date_from=date_from,
        date_to=date_to,
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
    return _to_csv_response(f"hqa_daily_report_{report_key}.csv", rows)


@app.get("/internal/v1/reports/marketplace/dashboard/summary")
def marketplace_dashboard_summary(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_summary(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/price-trend")
def marketplace_dashboard_price_trend(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_price_trend(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/seller-trend")
def marketplace_dashboard_seller_trend(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_seller_trend(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/status-trend")
def marketplace_dashboard_status_trend(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_status_trend(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/keyword-summary")
def marketplace_dashboard_keyword_summary(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_keyword_summary(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/alerts")
def marketplace_dashboard_alerts(
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    return fetch_marketplace_dashboard_alerts(
        db,
        keyword=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        category_name=category_name,
        listing_location=listing_location,
        condition=condition,
        buying_options=buying_options,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
        price_drop_threshold_pct=settings.alert_price_drop_threshold_pct,
        out_of_stock_spike_threshold_pct=settings.alert_out_of_stock_spike_threshold_pct,
        new_seller_min_count=settings.alert_new_seller_min_count,
    )


@app.get("/internal/v1/reports/marketplace/dashboard/export-csv")
def marketplace_dashboard_export_csv(
    dataset: str = Query(default="summary"),
    keyword: str | None = None,
    marketplace: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    category_name: str | None = None,
    listing_location: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    seller: str | None = None,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.dashboard.view")),
):
    filters = {
        "keyword": keyword,
        "marketplace": marketplace,
        "brand": brand,
        "model": model,
        "category": category,
        "category_name": category_name,
        "listing_location": listing_location,
        "condition": condition,
        "buying_options": buying_options,
        "seller": seller,
        "date_from": date_from,
        "date_to": date_to,
    }
    if dataset == "summary":
        rows = [fetch_marketplace_dashboard_summary(db, **filters)]
    elif dataset == "price_trend":
        rows = fetch_marketplace_dashboard_price_trend(db, **filters)["points"]
    elif dataset == "seller_trend":
        rows = fetch_marketplace_dashboard_seller_trend(db, **filters)["points"]
    elif dataset == "status_trend":
        rows = fetch_marketplace_dashboard_status_trend(db, **filters)["points"]
    elif dataset == "keyword_summary":
        rows = fetch_marketplace_dashboard_keyword_summary(db, **filters)["items"]
    elif dataset == "alerts":
        rows = fetch_marketplace_dashboard_alerts(
            db,
            **filters,
            price_drop_threshold_pct=settings.alert_price_drop_threshold_pct,
            out_of_stock_spike_threshold_pct=settings.alert_out_of_stock_spike_threshold_pct,
            new_seller_min_count=settings.alert_new_seller_min_count,
        )["alerts"]
    else:
        raise HTTPException(status_code=400, detail="Invalid dataset")
    return _to_csv_response(f"hqa_dashboard_{dataset}.csv", rows)


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