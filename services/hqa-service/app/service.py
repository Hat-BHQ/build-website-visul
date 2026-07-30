from __future__ import annotations

from datetime import date
from decimal import Decimal
from sqlalchemy import and_, case, func, literal, not_, or_, select
from sqlalchemy.orm import Session
from app.keyword_catalog import KeywordEntry, load_keyword_catalog, normalize_match_text
from app.models import marketplace_research_results as listing_table
from app.report_config import (
    ALLOWED_ORIGINAL_CATEGORIES,
    BLOCKED_CONDITION,
    MIN_PRICE_FOR_GROUPED_TABLES,
    REPORT_GROUPS,
    REPORT_GROUPS_BY_KEY,
)


def _normalize_text(expr):
    return func.lower(func.trim(func.coalesce(expr, "")))


def _normalize_category_name(expr):
    return func.rtrim(_normalize_text(expr), ".")


def _status_expression():
    return func.coalesce(func.nullif(_normalize_text(listing_table.c.listing_status), ""), literal("unknown"))


def _normalized_title_expression():
    return func.regexp_replace(
        func.lower(func.coalesce(listing_table.c.listing_title, "")),
        "[^a-z0-9]+",
        "",
        "g",
    )


def _listing_base_select():
    marketplace_lower = _normalize_text(listing_table.c.marketplace)
    status_expression = _status_expression()

    return select(
        listing_table.c.id,
        listing_table.c.research_date,
        listing_table.c.collected_at,
        listing_table.c.marketplace,
        listing_table.c.listing_id,
        listing_table.c.listing_id.label("external_listing_id"),
        listing_table.c.listing_title,
        listing_table.c.listing_url,
        listing_table.c.image_url,
        listing_table.c.seller_or_shop,
        listing_table.c.price,
        listing_table.c.currency,
        listing_table.c["condition"],
        listing_table.c["condition"].label("condition_name"),
        listing_table.c.category,
        listing_table.c.category_name,
        status_expression.label("listing_status"),
        status_expression.label("status"),
        listing_table.c.listing_location,
        listing_table.c.listing_views,
        func.coalesce(listing_table.c.quantity, listing_table.c["count"], 0).label("quantity"),
        listing_table.c.updated_at,
        case((marketplace_lower == "ebay", listing_table.c.seller_or_shop), else_=None).label("seller_name"),
        case((marketplace_lower != "ebay", listing_table.c.seller_or_shop), else_=None).label("shop_name"),
        listing_table.c.price.label("current_price"),
    )


def _shared_report_constraints():
    normalized_condition = _normalize_text(listing_table.c["condition"])
    normalized_category = _normalize_text(listing_table.c.category)
    return [
        or_(normalized_condition == "", normalized_condition != BLOCKED_CONDITION),
        normalized_category.in_(ALLOWED_ORIGINAL_CATEGORIES),
    ]


def _group_category_name_filter(group_key: str):
    group = REPORT_GROUPS_BY_KEY[group_key]
    normalized_names = [name.strip().lower().rstrip(".") for name in group.category_names]
    if not normalized_names:
        return None
    return _normalize_category_name(listing_table.c.category_name).in_(normalized_names)


def _group_keywords_filter(group_key: str):
    group = REPORT_GROUPS_BY_KEY[group_key]
    if not group.keyword_filter_enabled:
        return None
    if not group.keyword_entries:
        return None
    normalized_title = _normalized_title_expression()
    filters = []
    for entry in group.keyword_entries:
        expression = _keyword_entry_match_expression(entry, normalized_title)
        if expression is not None:
            filters.append(expression)
    if not filters:
        return None
    return or_(*filters)


def _keyword_entry_match_expression(entry: KeywordEntry, normalized_title):
    if entry.match_strategy == "brand_model":
        return and_(
            normalized_title.contains(entry.normalized_brand),
            normalized_title.contains(entry.normalized_model),
        )
    if entry.match_strategy == "model":
        return normalized_title.contains(entry.normalized_model)
    if entry.match_strategy == "keyword":
        return normalized_title.contains(entry.normalized_keyword)
    return None


def _exclude_keywords_filter():
    catalog = load_keyword_catalog()
    excludes = [keyword for keyword in catalog["exclude_keywords"] if keyword.strip()]
    if not excludes:
        return None
    normalized_title = _normalized_title_expression()
    conditions = [not_(normalized_title.contains(normalize_match_text(keyword))) for keyword in excludes]
    return conditions


def _apply_common_ui_filters(
    statement,
    *,
    q: str | None,
    marketplace: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
):
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                listing_table.c.listing_title.ilike(pattern),
                listing_table.c.listing_id.ilike(pattern),
            )
        )
    if marketplace:
        statement = statement.where(_normalize_text(listing_table.c.marketplace) == marketplace.strip().lower())
    if category_name:
        statement = statement.where(_normalize_category_name(listing_table.c.category_name) == category_name.strip().lower().rstrip("."))
    if seller:
        statement = statement.where(_normalize_text(listing_table.c.seller_or_shop).ilike(f"%{seller.strip().lower()}%"))
    if condition:
        statement = statement.where(_normalize_text(listing_table.c["condition"]) == condition.strip().lower())
    if price_min is not None:
        statement = statement.where(func.coalesce(listing_table.c.price, 0) >= price_min)
    if price_max is not None:
        statement = statement.where(func.coalesce(listing_table.c.price, 0) <= price_max)
    return statement


def _apply_sort(statement, sort: str):
    if sort != "price_desc":
        raise ValueError("Invalid sort option")
    return statement.order_by(
        listing_table.c.price.is_(None),
        listing_table.c.price.desc(),
        listing_table.c.id.desc(),
    )


def _build_report_statement(
    report_key: str,
    *,
    report_date: date | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    marketplace: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
):
    if report_key not in REPORT_GROUPS_BY_KEY:
        raise ValueError("Invalid report_key")

    shared = _shared_report_constraints()
    status = _status_expression()
    statement = _listing_base_select()

    if report_key in ("ended", "out_of_stock"):
        statement = statement.where(status == report_key)
        if date_from:
            statement = statement.where(listing_table.c.research_date >= date_from)
        if date_to:
            statement = statement.where(listing_table.c.research_date <= date_to)
    else:
        if report_date is None:
            raise ValueError("report_date is required for report groups 1-6")
        statement = statement.where(listing_table.c.research_date == report_date)
        statement = statement.where(func.coalesce(listing_table.c.price, 0) > MIN_PRICE_FOR_GROUPED_TABLES)
        statement = statement.where(status.notin_(["ended", "out_of_stock"]))
        category_filter = _group_category_name_filter(report_key)
        if category_filter is not None:
            statement = statement.where(category_filter)
        keyword_filter = _group_keywords_filter(report_key)
        if keyword_filter is not None:
            statement = statement.where(keyword_filter)
        exclude_filter = _exclude_keywords_filter()
        if exclude_filter is not None:
            for condition_expr in exclude_filter:
                statement = statement.where(condition_expr)

    for condition_expr in shared:
        statement = statement.where(condition_expr)

    statement = _apply_common_ui_filters(
        statement,
        q=q,
        marketplace=marketplace,
        category_name=category_name,
        seller=seller,
        condition=condition,
        price_min=price_min,
        price_max=price_max,
    )
    return statement


def fetch_marketplace_report_summary(
    db: Session,
    *,
    report_date: date,
    marketplace: str | None,
    q: str | None,
) -> dict:
    groups_payload = []
    count_map: dict[str, int] = {}

    for group in REPORT_GROUPS:
        statement = _build_report_statement(
            group.key,
            report_date=report_date,
            date_from=None,
            date_to=None,
            q=q,
            marketplace=marketplace,
            category_name=None,
            seller=None,
            condition=None,
            price_min=None,
            price_max=None,
        )
        count_value = db.execute(select(func.count()).select_from(statement.order_by(None).subquery())).scalar_one()
        count_map[group.key] = int(count_value or 0)
        groups_payload.append(
            {
                "key": group.key,
                "table_number": group.table_number,
                "title": group.title,
                "count": count_map[group.key],
                "keyword_filter_enabled": group.keyword_filter_enabled,
                "keyword_count": len(group.title_keywords),
            }
        )

    total_new_today = sum(count_map[key] for key in ["main_repeated", "amplifier_receiver", "speaker_parts", "other_home_audio", "vintage_accessories", "non_audio_irrelevant"])
    total_ended = count_map["ended"]
    total_out_of_stock = count_map["out_of_stock"]

    return {
        "report_date": report_date.isoformat(),
        "total_new_today": total_new_today,
        "total_ended": total_ended,
        "total_out_of_stock": total_out_of_stock,
        "total_matched": total_new_today + total_ended + total_out_of_stock,
        "groups": groups_payload,
    }


def fetch_marketplace_report_listings(
    db: Session,
    *,
    report_key: str,
    report_date: date | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
    q: str | None,
    marketplace: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
    sort: str,
) -> tuple[list[dict], int]:
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if price_min is not None and price_max is not None and price_min > price_max:
        raise ValueError("price_min must be <= price_max")

    statement = _build_report_statement(
        report_key,
        report_date=report_date,
        date_from=date_from,
        date_to=date_to,
        q=q,
        marketplace=marketplace,
        category_name=category_name,
        seller=seller,
        condition=condition,
        price_min=price_min,
        price_max=price_max,
    )
    count_query = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int(db.execute(count_query).scalar_one() or 0)

    data_query = _apply_sort(statement, sort).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(data_query).mappings().all()
    return [dict(row) for row in rows], total


def fetch_dashboard_counts(db: Session) -> dict:
    status_expression = _status_expression()
    row = db.execute(
        select(
            func.coalesce(func.sum(case((status_expression == "active", 1), else_=0)), 0).label("active_listings"),
            func.coalesce(func.sum(case((status_expression != "active", 1), else_=0)), 0).label("inactive_listings"),
            func.coalesce(func.sum(case((_normalize_text(listing_table.c.marketplace) == "ebay", 1), else_=0)), 0).label("ebay"),
            func.coalesce(func.sum(case((_normalize_text(listing_table.c.marketplace) == "reverb", 1), else_=0)), 0).label("reverb"),
            func.coalesce(func.sum(case((_normalize_text(listing_table.c.marketplace) == "etsy", 1), else_=0)), 0).label("etsy"),
        ).select_from(listing_table)
    ).mappings().one()
    return {
        "active_listings": int(row["active_listings"] or 0),
        "inactive_listings": int(row["inactive_listings"] or 0),
        "by_marketplace": {
            "ebay": int(row["ebay"] or 0),
            "reverb": int(row["reverb"] or 0),
            "etsy": int(row["etsy"] or 0),
        },
    }


def fetch_listings(
    db: Session,
    *,
    page: int,
    page_size: int,
    marketplace: str | None = None,
    status: str | None = None,
    q: str | None = None,
):
    statement = _listing_base_select()
    if marketplace:
        statement = statement.where(_normalize_text(listing_table.c.marketplace) == marketplace.lower())
    if status:
        statement = statement.where(_status_expression() == status.lower())
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                listing_table.c.listing_title.ilike(pattern),
                listing_table.c.listing_id.ilike(pattern),
            )
        )

    total = db.execute(select(func.count()).select_from(statement.order_by(None).subquery())).scalar_one()
    items = db.execute(
        statement.order_by(listing_table.c.updated_at.is_(None), listing_table.c.updated_at.desc(), listing_table.c.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    return items, int(total or 0)


def fetch_listing_by_id(db: Session, listing_id: str):
    statement = _listing_base_select().where(listing_table.c.id == listing_id)
    return db.execute(statement).mappings().first()
