from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import json
import logging
import re
from sqlalchemy import and_, case, delete, func, literal, literal_column, not_, or_, select, tuple_
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


UNKNOWN_FILTER_VALUE = "__unknown__"
FILTER_OPTIONS_LIMIT = 500
KNOWN_LISTING_STATUSES = {"active", "ended", "new_listing", "out_of_stock"}
ALLOWED_FILTER_FIELDS = {
    "model": "model",
    "condition": "condition",
    "status": "listing_status",
    "category_name": "category_name",
    "buying_option": "buying_options",
    "marketplace": "marketplace",
    "brand": "brand",
}
DEFAULT_FILTER_OPTION_PAGE_SIZE = 30
MAX_FILTER_OPTION_PAGE_SIZE = 100
ACCESSORIES_CATEGORY_NAMES = (
    "other vintage audio & video",
    "other vintage a/v parts & accs",
    "knobs, jacks & switches",
    "cases, covers & skins",
)

logger = logging.getLogger(__name__)


def _normalize_filter_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalized_value_expression(expr):
    return func.lower(func.trim(func.coalesce(expr, "")))


def _normalized_buying_options_expression():
    return _normalized_value_expression(listing_table.c.buying_options)


def _normalized_buying_options_with_delimiter_expression():
    normalized = _normalized_buying_options_expression()
    compact = func.replace(normalized, " ", "")
    return literal(",") + compact + literal(",")


def _buying_options_token_match_expression(value: str):
    normalized = _normalize_filter_value(value)
    token = normalized.replace(" ", "")
    return _normalized_buying_options_with_delimiter_expression().contains(f",{token},")


def _apply_normalized_text_filter(statement, column_expr, value: str | None):
    if value is None:
        return statement
    normalized_value = _normalize_filter_value(value)
    if not normalized_value:
        return statement
    normalized_column = _normalized_value_expression(column_expr)
    if normalized_value == UNKNOWN_FILTER_VALUE:
        return statement.where(normalized_column == "")
    return statement.where(normalized_column == normalized_value)


def _normalize_text(expr):
    return func.lower(func.trim(func.coalesce(expr, "")))


def _normalize_category_name(expr):
    return func.rtrim(_normalize_text(expr), ".")


def _raw_status_expression():
    return _normalize_text(listing_table.c.listing_status)


def _status_expression():
    raw_status = _raw_status_expression()
    return case(
        (raw_status == "active", literal("active")),
        (raw_status == "ended", literal("ended")),
        (raw_status == "new_listing", literal("new_listing")),
        (raw_status == "out_of_stock", literal("out_of_stock")),
        else_=literal("unknown"),
    )


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
        listing_table.c.listing_published_at,
        listing_table.c.last_status_checked_at,
        listing_table.c.listing_location,
        listing_table.c.listing_views,
        func.coalesce(listing_table.c.quantity, listing_table.c["count"], 0).label("quantity"),
        listing_table.c.updated_at,
        listing_table.c.brand,
        listing_table.c.model,
        listing_table.c.buying_options,
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
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
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
    statement = _apply_normalized_text_filter(statement, listing_table.c.brand, brand)
    statement = _apply_normalized_text_filter(statement, listing_table.c.model, model)
    statement = _apply_normalized_text_filter(statement, listing_table.c.category, category)
    statement = _apply_normalized_text_filter(statement, listing_table.c.listing_location, listing_location)
    if category_name:
        normalized_category_name = _normalize_filter_value(category_name)
        if normalized_category_name == UNKNOWN_FILTER_VALUE:
            statement = statement.where(_normalize_category_name(listing_table.c.category_name) == "")
        else:
            statement = statement.where(
                _normalize_category_name(listing_table.c.category_name)
                == normalized_category_name.rstrip(".")
            )
    statement = _apply_normalized_text_filter(statement, listing_table.c["condition"], condition)
    if seller:
        statement = statement.where(_normalize_text(listing_table.c.seller_or_shop).ilike(f"%{seller.strip().lower()}%"))
    if buying_options:
        normalized_buying_options = _normalize_filter_value(buying_options)
        if normalized_buying_options == UNKNOWN_FILTER_VALUE:
            statement = statement.where(_normalized_buying_options_expression() == "")
        else:
            statement = statement.where(_buying_options_token_match_expression(normalized_buying_options))
    if listing_status:
        normalized_status = _normalize_filter_value(listing_status)
        if normalized_status not in KNOWN_LISTING_STATUSES.union({"unknown"}):
            raise ValueError("Invalid listing_status")
        statement = statement.where(_status_expression() == normalized_status)
    if price_min is not None:
        statement = statement.where(func.coalesce(listing_table.c.price, 0) >= price_min)
    if price_max is not None:
        statement = statement.where(func.coalesce(listing_table.c.price, 0) <= price_max)
    return statement


def _apply_report_sort(statement, sort: str):
    if sort != "price_desc":
        raise ValueError("Invalid sort option")
    return statement.order_by(
        listing_table.c.price.is_(None),
        listing_table.c.price.desc(),
        listing_table.c.id.desc(),
    )


def _apply_raw_sort(statement, sort: str):
    if sort == "collected_at_desc":
        return statement.order_by(
            listing_table.c.collected_at.is_(None),
            listing_table.c.collected_at.desc(),
            listing_table.c.id.desc(),
        )
    if sort == "price_desc":
        return statement.order_by(
            listing_table.c.price.is_(None),
            listing_table.c.price.desc(),
            listing_table.c.id.desc(),
        )
    if sort == "price_asc":
        return statement.order_by(
            listing_table.c.price.is_(None),
            listing_table.c.price.asc(),
            listing_table.c.id.desc(),
        )
    if sort == "title_asc":
        return statement.order_by(
            listing_table.c.listing_title.is_(None),
            _normalize_text(listing_table.c.listing_title).asc(),
            listing_table.c.id.desc(),
        )
    raise ValueError("Invalid sort option")


def _build_report_statement(
    report_key: str,
    *,
    report_date: date | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
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
    return statement


def _build_raw_listings_statement(
    *,
    report_date: date | None,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
):
    statement = _listing_base_select()
    if report_date is not None:
        statement = statement.where(listing_table.c.research_date == report_date)

    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                listing_table.c.listing_title.ilike(pattern),
                listing_table.c.listing_id.ilike(pattern),
                listing_table.c.seller_or_shop.ilike(pattern),
            )
        )

    statement = _apply_common_ui_filters(
        statement,
        q=None,
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
    )
    return statement


def fetch_marketplace_report_summary(
    db: Session,
    *,
    report_date: date,
    marketplace: str | None,
    q: str | None,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
    listing_location: str | None = None,
    category_name: str | None = None,
    seller: str | None = None,
    condition: str | None = None,
    buying_options: str | None = None,
    listing_status: str | None = None,
    price_min: Decimal | float | None = None,
    price_max: Decimal | float | None = None,
) -> dict:
    database_total_rows = int(db.execute(select(func.count()).select_from(listing_table)).scalar_one() or 0)
    database_unique_listings = int(
        db.execute(
            select(
                func.count(
                    func.distinct(
                        func.nullif(func.trim(listing_table.c.listing_id), literal_column("''"))
                    )
                )
            ).select_from(listing_table)
        ).scalar_one()
        or 0
    )

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
    raw_total_statement = _build_raw_listings_statement(
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
    )
    total_listings_on_date = int(
        db.execute(select(func.count()).select_from(raw_total_statement.order_by(None).subquery())).scalar_one() or 0
    )

    return {
        "report_date": report_date.isoformat(),
        "database_total_rows": database_total_rows,
        "database_unique_listings": database_unique_listings,
        "total_listings_on_date": total_listings_on_date,
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
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
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
    count_query = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int(db.execute(count_query).scalar_one() or 0)

    data_query = _apply_report_sort(statement, sort).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(data_query).mappings().all()
    return [dict(row) for row in rows], total


def fetch_marketplace_raw_listings(
    db: Session,
    *,
    report_date: date | None,
    page: int,
    page_size: int,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
    sort: str,
) -> tuple[list[dict], int]:
    if price_min is not None and price_max is not None and price_min > price_max:
        raise ValueError("price_min must be <= price_max")
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be between 1 and 200")

    statement = _build_raw_listings_statement(
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
    )
    total = int(db.execute(select(func.count()).select_from(statement.order_by(None).subquery())).scalar_one() or 0)
    offset = (page - 1) * page_size
    rows = db.execute(_apply_raw_sort(statement, sort).offset(offset).limit(page_size)).mappings().all()
    total_pages = (total + page_size - 1) // page_size if total else 0
    if total == 0 or offset >= total:
        from_record = 0
        to_record = 0
    else:
        from_record = offset + 1
        to_record = min(offset + len(rows), total)

    return [dict(row) for row in rows], {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_previous": page > 1 and total_pages > 0,
        "has_next": page < total_pages,
        "from_record": from_record,
        "to_record": to_record,
    }


def _collect_text_options(db: Session, statement, column_name: str) -> tuple[list[dict], bool]:
    base = statement.order_by(None).subquery("scope_base")
    column_expr = base.c[column_name]
    clean_expression = func.trim(func.coalesce(column_expr, literal_column("''")))
    normalized_expression = func.lower(clean_expression)

    query = (
        select(
            normalized_expression.label("normalized_value"),
            func.min(clean_expression).label("label"),
            func.count().label("count"),
        )
        .select_from(base)
        .group_by(normalized_expression)
        .order_by(normalized_expression.asc())
    )
    rows = [dict(row) for row in db.execute(query).mappings().all()]

    items: list[dict] = []
    unknown_count = 0
    for row in rows:
        normalized_value = (row.get("normalized_value") or "").strip().lower()
        count_value = int(row.get("count") or 0)
        if not normalized_value:
            unknown_count += count_value
            continue
        label = (row.get("label") or "").strip() or normalized_value
        items.append(
            {
                "value": normalized_value,
                "label": label,
                "count": count_value,
            }
        )

    if unknown_count > 0:
        items.append(
            {
                "value": UNKNOWN_FILTER_VALUE,
                "label": "UNKNOWN",
                "count": unknown_count,
            }
        )

    items.sort(key=lambda item: item["label"].lower())
    truncated = len(items) > FILTER_OPTIONS_LIMIT
    return items[:FILTER_OPTIONS_LIMIT], truncated


def _collect_buying_options(db: Session, statement) -> tuple[list[dict], bool]:
    base = statement.order_by(None).subquery("scope_base")
    buying_options_column = base.c.buying_options
    clean_expression = func.trim(
        func.coalesce(
            buying_options_column,
            literal_column("''"),
        )
    )
    normalized_expression = func.lower(clean_expression)

    query = (
        select(
            normalized_expression.label("normalized_value"),
            func.min(clean_expression).label("label"),
            func.count().label("count"),
        )
        .select_from(base)
        .group_by(normalized_expression)
        .order_by(normalized_expression.asc())
    )
    rows = [dict(row) for row in db.execute(query).mappings().all()]

    grouped: dict[str, dict] = {}
    unknown_count = 0
    for row in rows:
        raw_value = (row.get("normalized_value") or "").strip().lower()
        label_value = (row.get("label") or "").strip()
        count_value = int(row.get("count") or 0)
        if not raw_value:
            unknown_count += count_value
            continue
        tokens = [token.strip() for token in raw_value.split(",") if token.strip()]
        label_tokens = [token.strip() for token in label_value.split(",") if token.strip()]
        if not tokens:
            unknown_count += count_value
            continue
        for index, token in enumerate(tokens):
            normalized_token = token.lower()
            label_token = label_tokens[index] if index < len(label_tokens) else token
            bucket = grouped.setdefault(
                normalized_token,
                {"count": 0, "label_counts": defaultdict(int)},
            )
            bucket["count"] += count_value
            bucket["label_counts"][label_token] += count_value

    items: list[dict] = []
    for normalized_token, payload in grouped.items():
        label_counts = payload["label_counts"]
        label = sorted(label_counts.items(), key=lambda item: (-item[1], item[0].lower()))[0][0]
        items.append({
            "value": normalized_token,
            "label": label,
            "count": payload["count"],
        })

    if unknown_count > 0:
        items.append({
            "value": UNKNOWN_FILTER_VALUE,
            "label": "UNKNOWN",
            "count": unknown_count,
        })

    items.sort(key=lambda item: item["label"].lower())
    truncated = len(items) > FILTER_OPTIONS_LIMIT
    return items[:FILTER_OPTIONS_LIMIT], truncated


def _scope_filters_without(filters: dict[str, str | None], skip_key: str) -> dict[str, str | None]:
    scoped = dict(filters)
    scoped[skip_key] = None
    return scoped


def _filter_options_cache_key(
    *,
    view: str,
    report_key: str | None,
    report_date: date | None,
    filters: dict[str, str | None],
) -> tuple:
    report_date_key = report_date.isoformat() if report_date else "all_dates"
    normalized_filters = tuple(sorted((key, value) for key, value in filters.items()))
    return (view, report_key or "", report_date_key, normalized_filters)


def _build_scope_statement(
    *,
    view: str,
    report_key: str | None,
    report_date: date | None,
    filters: dict[str, str | None],
):
    if view == "all_listings":
        return _build_raw_listings_statement(
            report_date=report_date,
            q=filters.get("q"),
            marketplace=filters.get("marketplace"),
            brand=filters.get("brand"),
            model=filters.get("model"),
            category=filters.get("category"),
            listing_location=filters.get("listing_location"),
            category_name=filters.get("category_name"),
            seller=filters.get("seller"),
            condition=filters.get("condition"),
            buying_options=filters.get("buying_options"),
            listing_status=filters.get("listing_status"),
            price_min=filters.get("price_min"),
            price_max=filters.get("price_max"),
        )

    if not report_key or report_key not in REPORT_GROUPS_BY_KEY:
        raise ValueError("report_key is required for report view")

    if report_key in ("ended", "out_of_stock"):
        return _build_report_statement(
            report_key,
            report_date=None,
            date_from=report_date,
            date_to=report_date,
            q=filters.get("q"),
            marketplace=filters.get("marketplace"),
            brand=filters.get("brand"),
            model=filters.get("model"),
            category=filters.get("category"),
            listing_location=filters.get("listing_location"),
            category_name=filters.get("category_name"),
            seller=filters.get("seller"),
            condition=filters.get("condition"),
            buying_options=filters.get("buying_options"),
            listing_status=filters.get("listing_status"),
            price_min=filters.get("price_min"),
            price_max=filters.get("price_max"),
        )

    return _build_report_statement(
        report_key,
        report_date=report_date,
        date_from=None,
        date_to=None,
        q=filters.get("q"),
        marketplace=filters.get("marketplace"),
        brand=filters.get("brand"),
        model=filters.get("model"),
        category=filters.get("category"),
        listing_location=filters.get("listing_location"),
        category_name=filters.get("category_name"),
        seller=filters.get("seller"),
        condition=filters.get("condition"),
        buying_options=filters.get("buying_options"),
        listing_status=filters.get("listing_status"),
        price_min=filters.get("price_min"),
        price_max=filters.get("price_max"),
    )


def fetch_marketplace_filter_options(
    db: Session,
    *,
    report_date: date | None,
    view: str,
    report_key: str | None,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    condition: str | None,
    category_name: str | None,
    buying_options: str | None,
    listing_status: str | None,
    seller: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
) -> dict:
    if view not in {"all_listings", "report"}:
        raise ValueError("Invalid view")

    if price_min is not None and price_max is not None and price_min > price_max:
        raise ValueError("price_min must be <= price_max")

    filters = {
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
    }

    field_config = {
        "brands": ("brand", "brand"),
        "models": ("model", "model"),
        "categories": ("category", "category"),
        "listing_locations": ("listing_location", "listing_location"),
        "conditions": ("condition", "condition"),
        "category_names": ("category_name", "category_name"),
    }

    options_payload: dict[str, dict] = {}
    for response_key, (filter_key, column_expr) in field_config.items():
        scoped_filters = _scope_filters_without(filters, filter_key)
        scoped_statement = _build_scope_statement(
            view=view,
            report_key=report_key,
            report_date=report_date,
            filters=scoped_filters,
        )
        items, truncated = _collect_text_options(db, scoped_statement, column_expr)
        options_payload[response_key] = {
            "items": items,
            "truncated": truncated,
        }

    scoped_for_buying = _build_scope_statement(
        view=view,
        report_key=report_key,
        report_date=report_date,
        filters=_scope_filters_without(filters, "buying_options"),
    )
    buying_items, buying_truncated = _collect_buying_options(db, scoped_for_buying)
    options_payload["buying_options"] = {
        "items": buying_items,
        "truncated": buying_truncated,
    }

    report_date_key = report_date.isoformat() if report_date else "all_dates"

    return {
        "report_date": report_date.isoformat() if report_date else None,
        "report_date_key": report_date_key,
        "view": view,
        "report_key": report_key,
        "cache_key": _filter_options_cache_key(
            view=view,
            report_key=report_key,
            report_date=report_date,
            filters=filters,
        ),
        "options": options_payload,
    }


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


def _normalize_status_value(value: str | None) -> str:
    normalized = _normalize_filter_value(value)
    if normalized in KNOWN_LISTING_STATUSES:
        return normalized
    return "unknown"


def _monthly_key(value: date | None) -> str:
    if value is None:
        return "unknown"
    return value.strftime("%Y-%m")


def _build_dashboard_scope_statement(
    *,
    keyword: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    category_name: str | None,
    listing_location: str | None,
    condition: str | None,
    buying_options: str | None,
    seller: str | None,
    date_from: date | None,
    date_to: date | None,
):
    statement = _listing_base_select()
    if date_from:
        statement = statement.where(listing_table.c.research_date >= date_from)
    if date_to:
        statement = statement.where(listing_table.c.research_date <= date_to)
    return _apply_common_ui_filters(
        statement,
        q=keyword,
        marketplace=marketplace,
        brand=brand,
        model=model,
        category=category,
        listing_location=listing_location,
        category_name=category_name,
        seller=seller,
        condition=condition,
        buying_options=buying_options,
        listing_status=None,
        price_min=None,
        price_max=None,
    )


def _fetch_dashboard_scope_rows(
    db: Session,
    *,
    keyword: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    category_name: str | None,
    listing_location: str | None,
    condition: str | None,
    buying_options: str | None,
    seller: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    statement = _build_dashboard_scope_statement(
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
    rows = db.execute(
        statement.order_by(
            listing_table.c.research_date.is_(None),
            listing_table.c.research_date.asc(),
            listing_table.c.id.asc(),
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def fetch_marketplace_dashboard_summary(
    db: Session,
    *,
    keyword: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    category_name: str | None,
    listing_location: str | None,
    condition: str | None,
    buying_options: str | None,
    seller: str | None,
    date_from: date | None,
    date_to: date | None,
) -> dict:
    rows = _fetch_dashboard_scope_rows(
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

    prices = [float(row["price"]) for row in rows if row.get("price") is not None]
    total_listings = len(rows)
    unique_listings = len({(row.get("listing_id") or "").strip().lower() for row in rows if (row.get("listing_id") or "").strip()})
    sellers = {(row.get("seller_or_shop") or "").strip().lower() for row in rows if (row.get("seller_or_shop") or "").strip()}

    previous_sellers: set[str] = set()
    if date_from:
        previous_statement = _build_dashboard_scope_statement(
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
            date_from=None,
            date_to=None,
        ).where(listing_table.c.research_date < date_from)
        previous_rows = db.execute(previous_statement.with_only_columns(listing_table.c.seller_or_shop)).all()
        previous_sellers = {
            (row[0] or "").strip().lower()
            for row in previous_rows
            if (row[0] or "").strip()
        }

    new_sellers = sorted(sellers - previous_sellers)
    status_counts = {"active": 0, "ended": 0, "out_of_stock": 0, "new_listing": 0, "unknown": 0}
    for row in rows:
        status_counts[_normalize_status_value(row.get("listing_status"))] += 1

    return {
        "total_listings": total_listings,
        "unique_listings": unique_listings,
        "total_sellers": len(sellers),
        "new_sellers": len(new_sellers),
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
        "min_price": round(min(prices), 2) if prices else 0,
        "max_price": round(max(prices), 2) if prices else 0,
        "active": status_counts["active"],
        "ended": status_counts["ended"],
        "out_of_stock": status_counts["out_of_stock"],
        "new_listing": status_counts["new_listing"],
    }


def fetch_marketplace_dashboard_price_trend(
    db: Session,
    **filters,
) -> dict:
    rows = _fetch_dashboard_scope_rows(db, **filters)
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("price") is None:
            continue
        buckets[_monthly_key(row.get("research_date"))].append(float(row["price"]))

    points = []
    for month in sorted(buckets.keys()):
        values = buckets[month]
        points.append(
            {
                "month": month,
                "avg_price": round(sum(values) / len(values), 2),
                "min_price": round(min(values), 2),
                "max_price": round(max(values), 2),
            }
        )
    return {"points": points}


def fetch_marketplace_dashboard_seller_trend(
    db: Session,
    **filters,
) -> dict:
    rows = _fetch_dashboard_scope_rows(db, **filters)
    buckets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        seller_name = (row.get("seller_or_shop") or "").strip().lower()
        if not seller_name:
            continue
        buckets[_monthly_key(row.get("research_date"))].add(seller_name)

    points = []
    for month in sorted(buckets.keys()):
        points.append({"month": month, "seller_count": len(buckets[month])})
    return {"points": points}


def fetch_marketplace_dashboard_status_trend(
    db: Session,
    **filters,
) -> dict:
    rows = _fetch_dashboard_scope_rows(db, **filters)
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"active": 0, "ended": 0, "out_of_stock": 0, "new_listing": 0, "unknown": 0})
    for row in rows:
        month = _monthly_key(row.get("research_date"))
        status = _normalize_status_value(row.get("listing_status"))
        buckets[month][status] += 1

    points = []
    for month in sorted(buckets.keys()):
        payload = {"month": month, **buckets[month]}
        points.append(payload)
    return {"points": points}


def fetch_marketplace_dashboard_keyword_summary(
    db: Session,
    **filters,
) -> dict:
    rows = _fetch_dashboard_scope_rows(db, **filters)
    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "new", "used", "sale", "audio",
        "ebay", "reverb", "etsy", "vintage", "speaker", "speakers", "receiver",
    }
    counter: dict[str, int] = defaultdict(int)
    for row in rows:
        title = (row.get("listing_title") or "").lower()
        for token in re.findall(r"[a-z0-9]{3,}", title):
            if token in stop_words:
                continue
            counter[token] += 1

    total_hits = sum(counter.values())
    top_items = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:30]
    items = [
        {
            "keyword": keyword,
            "count": count,
            "share_pct": round((count / total_hits) * 100, 2) if total_hits else 0,
        }
        for keyword, count in top_items
    ]
    return {"items": items, "total_hits": total_hits}


def fetch_marketplace_dashboard_alerts(
    db: Session,
    *,
    price_drop_threshold_pct: float,
    out_of_stock_spike_threshold_pct: float,
    new_seller_min_count: int,
    **filters,
) -> dict:
    price_trend = fetch_marketplace_dashboard_price_trend(db, **filters)["points"]
    status_trend = fetch_marketplace_dashboard_status_trend(db, **filters)["points"]
    rows = _fetch_dashboard_scope_rows(db, **filters)

    alerts: list[dict] = []

    for index in range(1, len(price_trend)):
        previous = price_trend[index - 1]
        current = price_trend[index]
        prev_avg = previous.get("avg_price") or 0
        curr_avg = current.get("avg_price") or 0
        if prev_avg <= 0:
            continue
        drop_pct = ((prev_avg - curr_avg) / prev_avg) * 100
        if drop_pct >= price_drop_threshold_pct:
            alerts.append(
                {
                    "type": "price_drop",
                    "severity": "high",
                    "month": current["month"],
                    "message": f"Average price dropped {drop_pct:.2f}% compared to previous month",
                    "drop_pct": round(drop_pct, 2),
                }
            )

    if len(status_trend) >= 2:
        previous = status_trend[-2]
        current = status_trend[-1]
        previous_out = previous.get("out_of_stock") or 0
        current_out = current.get("out_of_stock") or 0
        if previous_out == 0 and current_out > 0:
            spike_pct = 100.0
        elif previous_out > 0:
            spike_pct = ((current_out - previous_out) / previous_out) * 100
        else:
            spike_pct = 0.0
        if spike_pct >= out_of_stock_spike_threshold_pct:
            alerts.append(
                {
                    "type": "out_of_stock_spike",
                    "severity": "high",
                    "month": current["month"],
                    "message": f"Out-of-stock listings increased {spike_pct:.2f}% month over month",
                    "increase_pct": round(spike_pct, 2),
                }
            )

    seller_first_seen: dict[str, str] = {}
    for row in rows:
        seller_name = (row.get("seller_or_shop") or "").strip().lower()
        if not seller_name:
            continue
        month = _monthly_key(row.get("research_date"))
        if seller_name not in seller_first_seen or month < seller_first_seen[seller_name]:
            seller_first_seen[seller_name] = month
    if seller_first_seen:
        newest_month = max(seller_first_seen.values())
        newest_sellers = sorted(name for name, month in seller_first_seen.items() if month == newest_month)
        if len(newest_sellers) >= new_seller_min_count:
            alerts.append(
                {
                    "type": "new_seller",
                    "severity": "medium",
                    "month": newest_month,
                    "message": f"{len(newest_sellers)} new sellers appeared in {newest_month}",
                    "sellers": newest_sellers[:20],
                }
            )

    return {"alerts": alerts}


def fetch_marketplace_raw_listings_export(
    db: Session,
    *,
    report_date: date | None,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
    sort: str,
) -> list[dict]:
    statement = _build_raw_listings_statement(
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
    )
    rows = db.execute(_apply_raw_sort(statement, sort)).mappings().all()
    return [dict(row) for row in rows]


def fetch_marketplace_report_listings_export(
    db: Session,
    *,
    report_key: str,
    report_date: date | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    category: str | None,
    listing_location: str | None,
    category_name: str | None,
    seller: str | None,
    condition: str | None,
    buying_options: str | None,
    listing_status: str | None,
    price_min: Decimal | float | None,
    price_max: Decimal | float | None,
    sort: str,
) -> list[dict]:
    statement = _build_report_statement(
        report_key,
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
    )
    rows = db.execute(_apply_report_sort(statement, sort)).mappings().all()
    return [dict(row) for row in rows]


def _normalize_text_value(value: str | None) -> str:
    return (value or "").strip()


def _normalized_raw_status_expression():
    return func.lower(func.trim(func.coalesce(listing_table.c.listing_status, "")))


def _normalized_buying_options_compact_expression():
    normalized = _normalized_value_expression(listing_table.c.buying_options)
    cleaned = func.replace(func.replace(func.replace(func.replace(func.replace(func.replace(normalized, "[", ""), "]", ""), '"', ""), "'", ""), ";", ","), "|", ",")
    return func.replace(cleaned, " ", "")


def _buying_option_all_listings_match_expression(value: str):
    normalized = _normalize_filter_value(value)
    token = normalized.replace(" ", "")
    delimited = literal(",") + _normalized_buying_options_compact_expression() + literal(",")
    return delimited.contains(f",{token},")


def _normalize_filter_values(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        candidate = _normalize_filter_value(value)
        if candidate:
            normalized.append(candidate)
    # Preserve first-seen order while deduplicating.
    return list(dict.fromkeys(normalized))


def _build_all_listings_base_statement(
    *,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    search: str | None,
):
    if from_date and to_date and from_date > to_date:
        raise ValueError("from_date must be <= to_date")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price must be <= max_price")

    statement = _listing_base_select()

    if from_date:
        statement = statement.where(listing_table.c.research_date >= from_date)
    if to_date:
        statement = statement.where(listing_table.c.research_date <= to_date)

    statement = _apply_normalized_text_filter(statement, listing_table.c.marketplace, marketplace)
    statement = _apply_normalized_text_filter(statement, listing_table.c.brand, brand)
    statement = _apply_normalized_text_filter(statement, listing_table.c.model, model)

    normalized_conditions = _normalize_filter_values(conditions)
    if normalized_conditions:
        statement = statement.where(_normalized_value_expression(listing_table.c["condition"]).in_(normalized_conditions))

    normalized_statuses = _normalize_filter_values(statuses)
    if normalized_statuses:
        statement = statement.where(_normalized_raw_status_expression().in_(normalized_statuses))

    normalized_category_names = [value.rstrip(".") for value in _normalize_filter_values(category_names)]
    if normalized_category_names:
        statement = statement.where(_normalize_category_name(listing_table.c.category_name).in_(normalized_category_names))

    normalized_buying_options = _normalize_filter_values(buying_options)
    if normalized_buying_options:
        statement = statement.where(or_(*[_buying_option_all_listings_match_expression(value) for value in normalized_buying_options]))

    if min_price is not None:
        statement = statement.where(listing_table.c.price >= min_price)
    if max_price is not None:
        statement = statement.where(listing_table.c.price <= max_price)

    if search:
        keyword = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                listing_table.c.listing_title.ilike(keyword),
                listing_table.c.listing_id.ilike(keyword),
                listing_table.c.seller_or_shop.ilike(keyword),
            )
        )

    return statement


def _apply_all_listings_sort(statement, sort_collected: str, sort_by: str | None = None, sort_order: str | None = None):
    if sort_by == "price":
        normalized_order = (sort_order or "asc").lower()
        if normalized_order == "asc":
            return statement.order_by(
                listing_table.c.price.is_(None),
                func.coalesce(listing_table.c.price, 0).asc(),
                listing_table.c.id.desc(),
            )
        if normalized_order == "desc":
            return statement.order_by(
                listing_table.c.price.is_(None),
                func.coalesce(listing_table.c.price, 0).desc(),
                listing_table.c.id.desc(),
            )
        raise ValueError("Invalid sort_order")
    if sort_collected == "oldest":
        return statement.order_by(
            listing_table.c.collected_at.is_(None),
            listing_table.c.collected_at.asc(),
            listing_table.c.id.asc(),
        )
    if sort_collected != "newest":
        raise ValueError("Invalid sort_collected")
    return statement.order_by(
        listing_table.c.collected_at.is_(None),
        listing_table.c.collected_at.desc(),
        listing_table.c.id.desc(),
    )


def fetch_all_listings(
    db: Session,
    *,
    page: int,
    page_size: int,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    sort_collected: str,
    search: str | None,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> tuple[list[dict], dict]:
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be between 1 and 200")

    statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=model,
        conditions=conditions,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )
    total = int(db.execute(select(func.count()).select_from(statement.order_by(None).subquery())).scalar_one() or 0)
    offset = (page - 1) * page_size
    rows = db.execute(_apply_all_listings_sort(statement, sort_collected, sort_by=sort_by, sort_order=sort_order).offset(offset).limit(page_size)).mappings().all()
    total_pages = (total + page_size - 1) // page_size if total else 0
    return [dict(row) for row in rows], {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def _parse_buying_options(raw_value: str | None) -> list[str]:
    text = (raw_value or "").strip()
    if not text:
        return []

    parsed_tokens: list[str] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            parsed_tokens = [str(token) for token in parsed]
        elif isinstance(parsed, str):
            parsed_tokens = [parsed]
    except Exception:
        parsed_tokens = re.split(r"[,;|]+", text)

    normalized = []
    for token in parsed_tokens:
        value = token.strip().strip('"').strip("'")
        if value:
            normalized.append(value)
    if not normalized and text:
        fallback = text.strip().strip('"').strip("'")
        if fallback:
            normalized.append(fallback)
    return normalized


def _distinct_non_empty_values(db: Session, statement, column_name: str) -> list[str]:
    scoped = statement.order_by(None).subquery("all_scope")
    expression = func.trim(func.coalesce(scoped.c[column_name], literal_column("''")))
    normalized_expression = func.lower(expression)
    rows = db.execute(
        select(func.min(expression).label("label"))
        .where(normalized_expression != "")
        .group_by(normalized_expression)
        .order_by(normalized_expression.asc())
    ).all()
    return [row[0] for row in rows if row[0]]


def fetch_all_listings_filter_options(
    db: Session,
    *,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    search: str | None,
) -> dict:
    base_statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=None,
        model=model,
        conditions=conditions,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )
    brands = _distinct_non_empty_values(db, base_statement, "brand")

    model_scope_statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=None,
        conditions=conditions,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )
    models = _distinct_non_empty_values(db, model_scope_statement, "model")

    shared_statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=model,
        conditions=None,
        statuses=None,
        category_names=None,
        buying_options=None,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )
    marketplaces = _distinct_non_empty_values(db, shared_statement, "marketplace")
    conditions = _distinct_non_empty_values(db, shared_statement, "condition")
    statuses = _distinct_non_empty_values(db, shared_statement, "listing_status")
    category_names = _distinct_non_empty_values(db, shared_statement, "category_name")

    buying_scope = shared_statement.order_by(None).subquery("buying_scope")
    buying_rows = db.execute(select(buying_scope.c.buying_options)).all()
    buying_map: dict[str, str] = {}
    for row in buying_rows:
        for token in _parse_buying_options(row[0]):
            normalized_token = token.strip().lower()
            if normalized_token and normalized_token not in buying_map:
                buying_map[normalized_token] = token.strip()
    buying_options = [buying_map[key] for key in sorted(buying_map.keys())]

    return {
        "marketplaces": marketplaces,
        "brands": brands,
        "models": models,
        "conditions": conditions,
        "statuses": statuses,
        "category_names": category_names,
        "buying_options": buying_options,
    }


def _normalize_option_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    normalized: list[dict] = []
    for item in items:
        raw_value = (item.get("value") or "").strip()
        raw_label = (item.get("label") or "").strip()
        if not raw_value and not raw_label:
            continue
        value = raw_value or raw_label
        key = value.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append({"value": value, "label": raw_label or value})
    normalized.sort(key=lambda row: row["label"].lower())
    return normalized


def _build_filter_option_scope_statement(
    *,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
):
    return _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=None,
        conditions=None,
        statuses=None,
        category_names=None,
        buying_options=None,
        min_price=None,
        max_price=None,
        search=None,
    )


def _fetch_distinct_text_option_page(
    db: Session,
    *,
    scope_statement,
    column_name: str,
    page: int,
    page_size: int,
    search: str | None,
) -> dict:
    scope = scope_statement.order_by(None).subquery("option_scope")
    column_expr = func.trim(func.coalesce(scope.c[column_name], literal_column("''")))
    normalized_expr = func.lower(column_expr)

    query = (
        select(
            normalized_expr.label("value_key"),
            func.min(column_expr).label("label"),
        )
        .where(normalized_expr != "")
        .group_by(normalized_expr)
        .order_by(normalized_expr.asc())
    )
    if search:
        normalized_search = f"%{search.strip().lower()}%"
        query = query.where(normalized_expr.like(normalized_search))

    offset = (page - 1) * page_size
    rows = db.execute(query.offset(offset).limit(page_size + 1)).mappings().all()
    has_more = len(rows) > page_size
    sliced_rows = rows[:page_size]
    items = _normalize_option_items(
        [
            {
                "value": row.get("label"),
                "label": row.get("label"),
            }
            for row in sliced_rows
        ]
    )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def _fetch_buying_option_page(
    db: Session,
    *,
    scope_statement,
    page: int,
    page_size: int,
    search: str | None,
) -> dict:
    scope = scope_statement.order_by(None).subquery("option_scope_buying")
    buying_expr = func.trim(func.coalesce(scope.c.buying_options, literal_column("''")))
    normalized_expr = func.lower(buying_expr)

    base_query = (
        select(buying_expr.label("raw_value"))
        .where(normalized_expr != "")
        .group_by(normalized_expr, buying_expr)
        .order_by(normalized_expr.asc())
    )

    option_offset = (page - 1) * page_size
    scan_offset = option_offset
    collected: list[dict] = []
    seen: set[str] = set()
    normalized_search = (search or "").strip().lower()
    has_more_rows = True

    while len(collected) < page_size + 1 and has_more_rows:
        rows = db.execute(base_query.offset(scan_offset).limit(page_size + 1)).all()
        if not rows:
            has_more_rows = False
            break
        scan_offset += len(rows)
        if len(rows) <= page_size:
            has_more_rows = False

        for row in rows:
            for token in _parse_buying_options(row[0]):
                normalized_token = token.strip().lower()
                if not normalized_token:
                    continue
                if normalized_search and normalized_search not in normalized_token:
                    continue
                if normalized_token in seen:
                    continue
                seen.add(normalized_token)
                collected.append({"value": normalized_token, "label": token.strip()})
                if len(collected) >= page_size + 1:
                    break
            if len(collected) >= page_size + 1:
                break

    has_more = len(collected) > page_size
    items = _normalize_option_items(collected[:page_size])
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


def fetch_all_listings_filter_option_page(
    db: Session,
    *,
    field: str,
    page: int,
    page_size: int,
    search: str | None,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
) -> dict:
    normalized_field = (field or "").strip().lower()
    if normalized_field not in ALLOWED_FILTER_FIELDS:
        raise ValueError("Invalid field")
    if page < 1:
        raise ValueError("page must be >= 1")

    resolved_page_size = page_size or DEFAULT_FILTER_OPTION_PAGE_SIZE
    if resolved_page_size < 1 or resolved_page_size > MAX_FILTER_OPTION_PAGE_SIZE:
        raise ValueError("page_size must be between 1 and 100")

    normalized_search = (search or "").strip()
    scope_statement = _build_filter_option_scope_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
    )

    if normalized_field == "buying_option":
        payload = _fetch_buying_option_page(
            db,
            scope_statement=scope_statement,
            page=page,
            page_size=resolved_page_size,
            search=normalized_search,
        )
    else:
        column_name = ALLOWED_FILTER_FIELDS[normalized_field]
        payload = _fetch_distinct_text_option_page(
            db,
            scope_statement=scope_statement,
            column_name=column_name,
            page=page,
            page_size=resolved_page_size,
            search=normalized_search,
        )

    return {
        "field": normalized_field,
        "items": payload["items"],
        "page": payload["page"],
        "page_size": payload["page_size"],
        "has_more": payload["has_more"],
    }


def fetch_all_listings_summary(
    db: Session,
    *,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    search: str | None,
) -> dict:
    statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=model,
        conditions=conditions,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        min_price=min_price,
        max_price=max_price,
        search=search,
    ).order_by(None)
    scope = statement.subquery("summary_scope")

    status_expr = func.lower(func.trim(func.coalesce(scope.c.listing_status, "")))
    category_expr = func.rtrim(func.lower(func.trim(func.coalesce(scope.c.category_name, ""))), ".")
    row = db.execute(
        select(
            func.count().label("filtered_records"),
            func.count(func.distinct(func.nullif(func.trim(scope.c.listing_id), literal_column("''")))).label("unique_listing_ids"),
            func.coalesce(func.sum(case((status_expr == "active", 1), else_=0)), 0).label("active"),
            func.coalesce(func.sum(case((status_expr.in_(["ended", "end"]), 1), else_=0)), 0).label("ended"),
            func.coalesce(func.sum(case((status_expr == "out_of_stock", 1), else_=0)), 0).label("out_of_stock"),
            func.coalesce(func.sum(case((category_expr.in_(ACCESSORIES_CATEGORY_NAMES), 1), else_=0)), 0).label("accessories"),
        )
    ).mappings().one()

    total_records_stored = int(db.execute(select(func.count()).select_from(listing_table)).scalar_one() or 0)
    unique_listing_ids_stored = int(
        db.execute(
            select(
                func.count(
                    func.distinct(
                        func.nullif(func.trim(listing_table.c.listing_id), literal_column("''"))
                    )
                )
            )
        ).scalar_one()
        or 0
    )

    return {
        "total_records_stored": total_records_stored,
        "unique_listing_ids": unique_listing_ids_stored,
        "filtered_records": int(row["filtered_records"] or 0),
        "active": int(row["active"] or 0),
        "ended": int(row["ended"] or 0),
        "out_of_stock": int(row["out_of_stock"] or 0),
        "accessories": int(row["accessories"] or 0),
    }


def fetch_all_listings_export_rows(
    db: Session,
    *,
    from_date: date | None,
    to_date: date | None,
    marketplace: str | None,
    brand: str | None,
    model: str | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    sort_collected: str,
    search: str | None,
) -> list[dict]:
    statement = _build_all_listings_base_statement(
        from_date=from_date,
        to_date=to_date,
        marketplace=marketplace,
        brand=brand,
        model=model,
        conditions=conditions,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        min_price=min_price,
        max_price=max_price,
        search=search,
    )
    rows = db.execute(_apply_all_listings_sort(statement, sort_collected)).mappings().all()
    return [dict(row) for row in rows]


def _normalized_marketplace_expression():
    return func.lower(func.trim(func.coalesce(listing_table.c.marketplace, "")))


def _normalized_listing_id_expression():
    return func.lower(func.trim(func.coalesce(listing_table.c.listing_id, "")))


def _normalized_listing_status_expression():
    return func.lower(func.trim(func.coalesce(listing_table.c.listing_status, "")))


def _duplicate_listing_ordering():
    status_priority = case(
        (
            _normalized_listing_status_expression().in_(["ended", "out_of_stock"]),
            0,
        ),
        else_=1,
    )
    return [
        status_priority,
        listing_table.c.last_status_checked_at.desc().nulls_last(),
        listing_table.c.updated_at.desc().nulls_last(),
        listing_table.c.collected_at.desc().nulls_last(),
        listing_table.c.listing_published_at.desc().nulls_last(),
        listing_table.c.id.desc(),
    ]


def _duplicate_ranked_scope_statement():
    normalized_marketplace = _normalized_marketplace_expression()
    normalized_listing_id = _normalized_listing_id_expression()
    return (
        select(
            listing_table.c.id,
            listing_table.c.marketplace,
            listing_table.c.listing_id,
            listing_table.c.listing_title,
            listing_table.c.listing_status,
            listing_table.c.quantity,
            listing_table.c.collected_at,
            listing_table.c.updated_at,
            listing_table.c.listing_published_at,
            listing_table.c.last_status_checked_at,
            normalized_marketplace.label("normalized_marketplace"),
            normalized_listing_id.label("normalized_listing_id"),
            func.row_number()
            .over(
                partition_by=[normalized_marketplace, normalized_listing_id],
                order_by=_duplicate_listing_ordering(),
            )
            .label("row_number"),
        )
        .where(normalized_listing_id != "")
    )


def _duplicate_group_base_query(ranked_scope):
    return (
        select(
            ranked_scope.c.normalized_marketplace,
            ranked_scope.c.normalized_listing_id,
            func.count().label("record_count"),
            func.coalesce(
                func.sum(case((ranked_scope.c.row_number > 1, 1), else_=0)),
                0,
            ).label("delete_count"),
        )
        .where(ranked_scope.c.normalized_listing_id != "")
        .group_by(
            ranked_scope.c.normalized_marketplace,
            ranked_scope.c.normalized_listing_id,
        )
        .having(func.count() > 1)
    )


def fetch_duplicate_listing_summary(db: Session) -> dict:
    normalized_marketplace = _normalized_marketplace_expression()
    normalized_listing_id = _normalized_listing_id_expression()

    total_records = int(db.execute(select(func.count()).select_from(listing_table)).scalar_one() or 0)

    unique_listing_keys = int(
        db.execute(
            select(func.count(func.distinct(normalized_marketplace + literal("|") + normalized_listing_id)))
            .select_from(listing_table)
            .where(normalized_listing_id != "")
        ).scalar_one()
        or 0
    )

    missing_listing_id = int(
        db.execute(
            select(func.count())
            .select_from(listing_table)
            .where(normalized_listing_id == "")
        ).scalar_one()
        or 0
    )

    grouped = (
        select(func.count().label("record_count"))
        .select_from(listing_table)
        .where(normalized_listing_id != "")
        .group_by(normalized_marketplace, normalized_listing_id)
        .having(func.count() > 1)
    ).subquery("duplicate_grouped")

    duplicate_groups = int(db.execute(select(func.count()).select_from(grouped)).scalar_one() or 0)
    duplicate_records = int(
        db.execute(select(func.coalesce(func.sum(grouped.c.record_count), 0)).select_from(grouped)).scalar_one() or 0
    )
    records_to_delete = int(
        db.execute(select(func.coalesce(func.sum(grouped.c.record_count - 1), 0)).select_from(grouped)).scalar_one() or 0
    )

    return {
        "total_records": total_records,
        "unique_listing_keys": unique_listing_keys,
        "duplicate_groups": duplicate_groups,
        "duplicate_records": duplicate_records,
        "records_to_delete": records_to_delete,
        "missing_listing_id": missing_listing_id,
    }


def fetch_duplicate_listing_groups(
    db: Session,
    *,
    page: int,
    page_size: int,
    marketplace: str | None,
    listing_id: str | None,
    status: str | None,
) -> dict:
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 200:
        raise ValueError("page_size must be between 1 and 200")

    ranked_scope = _duplicate_ranked_scope_statement().subquery("duplicate_ranked")
    groups = _duplicate_group_base_query(ranked_scope).subquery("duplicate_groups")
    keep_rows = select(ranked_scope).where(ranked_scope.c.row_number == 1).subquery("keep_rows")

    query = (
        select(
            groups.c.normalized_marketplace,
            groups.c.normalized_listing_id,
            groups.c.record_count,
            groups.c.delete_count,
            keep_rows.c.id.label("keep_id"),
            keep_rows.c.marketplace.label("keep_marketplace"),
            keep_rows.c.listing_id.label("keep_listing_id"),
            keep_rows.c.listing_title.label("keep_listing_title"),
            keep_rows.c.listing_status.label("keep_listing_status"),
            keep_rows.c.quantity.label("keep_quantity"),
            keep_rows.c.collected_at.label("keep_collected_at"),
            keep_rows.c.updated_at.label("keep_updated_at"),
            keep_rows.c.listing_published_at.label("keep_listing_published_at"),
            keep_rows.c.last_status_checked_at.label("keep_last_status_checked_at"),
        )
        .select_from(
            groups.join(
                keep_rows,
                and_(
                    groups.c.normalized_marketplace == keep_rows.c.normalized_marketplace,
                    groups.c.normalized_listing_id == keep_rows.c.normalized_listing_id,
                ),
            )
        )
    )

    normalized_marketplace_filter = _normalize_filter_value(marketplace)
    if normalized_marketplace_filter:
        query = query.where(groups.c.normalized_marketplace == normalized_marketplace_filter)

    normalized_listing_id_filter = _normalize_filter_value(listing_id)
    if normalized_listing_id_filter:
        query = query.where(groups.c.normalized_listing_id == normalized_listing_id_filter)

    normalized_status_filter = _normalize_filter_value(status)
    if normalized_status_filter:
        query = query.where(func.lower(func.trim(func.coalesce(keep_rows.c.listing_status, ""))) == normalized_status_filter)

    total_groups = int(db.execute(select(func.count()).select_from(query.order_by(None).subquery())).scalar_one() or 0)

    paged_rows = db.execute(
        query.order_by(
            groups.c.delete_count.desc(),
            groups.c.record_count.desc(),
            groups.c.normalized_marketplace.asc(),
            groups.c.normalized_listing_id.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()

    if not paged_rows:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "total_groups": total_groups,
        }

    grouped_payload: dict[tuple[str, str], dict] = {}
    selected_keys: list[tuple[str, str]] = []

    for row in paged_rows:
        key = (row["normalized_marketplace"], row["normalized_listing_id"])
        selected_keys.append(key)
        grouped_payload[key] = {
            "marketplace": row["keep_marketplace"] or row["normalized_marketplace"],
            "listing_id": row["keep_listing_id"] or row["normalized_listing_id"],
            "record_count": int(row["record_count"] or 0),
            "keep_record": {
                "id": row["keep_id"],
                "marketplace": row["keep_marketplace"],
                "listing_id": row["keep_listing_id"],
                "listing_title": row["keep_listing_title"],
                "listing_status": row["keep_listing_status"],
                "quantity": row["keep_quantity"],
                "collected_at": row["keep_collected_at"],
                "updated_at": row["keep_updated_at"],
                "listing_published_at": row["keep_listing_published_at"],
                "last_status_checked_at": row["keep_last_status_checked_at"],
            },
            "delete_records": [],
        }

    ranked_rows = db.execute(
        select(
            ranked_scope.c.id,
            ranked_scope.c.marketplace,
            ranked_scope.c.listing_id,
            ranked_scope.c.listing_title,
            ranked_scope.c.listing_status,
            ranked_scope.c.quantity,
            ranked_scope.c.collected_at,
            ranked_scope.c.updated_at,
            ranked_scope.c.listing_published_at,
            ranked_scope.c.last_status_checked_at,
            ranked_scope.c.normalized_marketplace,
            ranked_scope.c.normalized_listing_id,
            ranked_scope.c.row_number,
        )
        .where(
            tuple_(
                ranked_scope.c.normalized_marketplace,
                ranked_scope.c.normalized_listing_id,
            ).in_(selected_keys)
        )
        .order_by(
            ranked_scope.c.normalized_marketplace.asc(),
            ranked_scope.c.normalized_listing_id.asc(),
            ranked_scope.c.row_number.asc(),
            ranked_scope.c.id.desc(),
        )
    ).mappings().all()

    for row in ranked_rows:
        key = (row["normalized_marketplace"], row["normalized_listing_id"])
        if row["row_number"] <= 1:
            continue
        grouped_payload[key]["delete_records"].append(
            {
                "id": row["id"],
                "marketplace": row["marketplace"],
                "listing_id": row["listing_id"],
                "listing_title": row["listing_title"],
                "listing_status": row["listing_status"],
                "quantity": row["quantity"],
                "collected_at": row["collected_at"],
                "updated_at": row["updated_at"],
                "listing_published_at": row["listing_published_at"],
                "last_status_checked_at": row["last_status_checked_at"],
            }
        )

    items = [
        grouped_payload[(row["normalized_marketplace"], row["normalized_listing_id"])]
        for row in paged_rows
    ]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total_groups": total_groups,
    }


def cleanup_duplicate_listings(db: Session) -> dict:
    pre_summary = fetch_duplicate_listing_summary(db)
    records_to_delete = int(pre_summary.get("records_to_delete") or 0)
    duplicate_groups = int(pre_summary.get("duplicate_groups") or 0)

    if records_to_delete <= 0:
        logger.info("Duplicate cleanup skipped: no duplicate records found")
        return {
            "duplicate_groups_processed": 0,
            "records_deleted": 0,
            "records_remaining": int(pre_summary.get("total_records") or 0),
        }

    ranked_scope = _duplicate_ranked_scope_statement().subquery("ranked_cleanup")
    delete_ids = select(ranked_scope.c.id).where(ranked_scope.c.row_number > 1)

    try:
        delete_result = db.execute(delete(listing_table).where(listing_table.c.id.in_(delete_ids)))
        deleted_count = int(delete_result.rowcount or 0)

        post_summary = fetch_duplicate_listing_summary(db)
        remaining_to_delete = int(post_summary.get("records_to_delete") or 0)
        if remaining_to_delete != 0:
            raise RuntimeError(
                "Duplicate cleanup verification failed: records_to_delete is not zero after cleanup"
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    records_remaining = int(post_summary.get("total_records") or 0)
    records_kept = records_remaining
    logger.info(
        "Duplicate cleanup completed: groups_processed=%s records_kept=%s records_deleted=%s",
        duplicate_groups,
        records_kept,
        deleted_count,
    )

    return {
        "duplicate_groups_processed": duplicate_groups,
        "records_deleted": deleted_count,
        "records_remaining": records_remaining,
    }


def _parse_dashboard_granularity(granularity: str | None) -> str:
    value = (granularity or "month").strip().lower()
    if value not in {"day", "week", "month"}:
        raise ValueError("granularity must be one of: day, week, month")
    return value


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = quantile * (len(ordered) - 1)
    lower_index = int(position)
    fraction = position - lower_index
    upper_index = min(lower_index + 1, len(ordered) - 1)
    return float(ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction)


def _normalized_text_in_values_filter(statement, column_expr, values: list[str] | None):
    normalized_values = _normalize_filter_values(values)
    if not normalized_values:
        return statement
    return statement.where(_normalized_value_expression(column_expr).in_(normalized_values))


def _status_in_values_filter(statement, values: list[str] | None):
    normalized_values = _normalize_filter_values(values)
    if not normalized_values:
        return statement
    allowed = KNOWN_LISTING_STATUSES.union({"unknown"})
    invalid = [value for value in normalized_values if value not in allowed]
    if invalid:
        raise ValueError("Invalid status filter")
    return statement.where(_status_expression().in_(normalized_values))


def _buying_options_any_filter(statement, values: list[str] | None):
    normalized_values = _normalize_filter_values(values)
    if not normalized_values:
        return statement
    expressions = []
    for normalized in normalized_values:
        if normalized == UNKNOWN_FILTER_VALUE:
            expressions.append(_normalized_buying_options_expression() == "")
            continue
        expressions.append(_buying_options_token_match_expression(normalized))
    return statement.where(or_(*expressions))


def _apply_dashboard_date_and_numeric_filters(
    statement,
    *,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price must be <= max_price")
    if date_from:
        statement = statement.where(listing_table.c.research_date >= date_from)
    if date_to:
        statement = statement.where(listing_table.c.research_date <= date_to)
    if min_price is not None:
        statement = statement.where(listing_table.c.price >= min_price)
    if max_price is not None:
        statement = statement.where(listing_table.c.price <= max_price)
    return statement


def _apply_dashboard_base_filters(
    statement,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
):
    if keyword:
        pattern = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                listing_table.c.listing_title.ilike(pattern),
                listing_table.c.listing_id.ilike(pattern),
                listing_table.c.seller_or_shop.ilike(pattern),
            )
        )
    statement = _normalized_text_in_values_filter(statement, listing_table.c.marketplace, marketplaces)
    statement = _normalized_text_in_values_filter(statement, listing_table.c.brand, brands)
    statement = _normalized_text_in_values_filter(statement, listing_table.c.model, models)
    statement = _status_in_values_filter(statement, statuses)

    normalized_category_names = [value.rstrip(".") for value in _normalize_filter_values(category_names)]
    if normalized_category_names:
        statement = statement.where(_normalize_category_name(listing_table.c.category_name).in_(normalized_category_names))

    statement = _buying_options_any_filter(statement, buying_options)
    statement = _normalized_text_in_values_filter(statement, listing_table.c.seller_or_shop, sellers)
    statement = _apply_normalized_text_filter(statement, listing_table.c.currency, currency)
    return statement


def _build_dashboard_rows_statement(
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    statement = _listing_base_select()
    statement = _apply_dashboard_date_and_numeric_filters(
        statement,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    statement = _apply_dashboard_base_filters(
        statement,
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
    )
    return statement


def _dashboard_bucket_expression(db: Session, granularity: str, date_column):
    dialect = (db.bind.dialect.name if db.bind is not None else "").lower()
    if dialect == "postgresql":
        if granularity == "day":
            return func.to_char(date_column, "YYYY-MM-DD")
        if granularity == "week":
            return func.to_char(date_column, "IYYY-\"W\"IW")
        return func.to_char(date_column, "YYYY-MM")

    if granularity == "day":
        return func.strftime("%Y-%m-%d", date_column)
    if granularity == "week":
        return func.strftime("%Y-W%W", date_column)
    return func.strftime("%Y-%m", date_column)


def _collect_dashboard_option_values(db: Session, statement, column_name: str) -> list[str]:
    scoped = statement.order_by(None).subquery("dashboard_scope_opt")
    expression = func.trim(func.coalesce(scoped.c[column_name], literal_column("''")))
    normalized_expression = func.lower(expression)
    rows = db.execute(
        select(func.min(expression).label("value"))
        .where(normalized_expression != "")
        .group_by(normalized_expression)
        .order_by(normalized_expression.asc())
        .limit(FILTER_OPTIONS_LIMIT)
    ).all()
    return [row[0] for row in rows if row[0]]


def fetch_hqa_dashboard_analysis(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    conditions: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    group_by: str = "model",
    granularity: str = "month",
    price_drop_warning_pct: float = 20.0,
    price_drop_critical_pct: float = 30.0,
    out_of_stock_warning_points: float = 30.0,
    out_of_stock_critical_points: float = 50.0,
):
    """Build the dashboard payload from real marketplace_research_results rows.

    The endpoint intentionally returns group x period statistics in one response so the
    vanilla-JS dashboard can render KPI cards, alerts, multi-series charts and drill-downs
    without issuing one request per model/period.
    """
    normalized_group = (group_by or "model").strip().lower()
    if normalized_group not in {"model", "brand", "category"}:
        raise ValueError("group_by must be one of: model, brand, category")
    normalized_granularity = _parse_dashboard_granularity(granularity)
    if normalized_granularity not in {"month", "week"}:
        raise ValueError("granularity must be one of: month, week")

    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=None,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    statement = _normalized_text_in_values_filter(statement, listing_table.c["condition"], conditions)

    rows = db.execute(
        statement.with_only_columns(
            listing_table.c.listing_id,
            listing_table.c.model,
            listing_table.c.brand,
            listing_table.c.category_name,
            listing_table.c.seller_or_shop,
            listing_table.c.price,
            listing_table.c.currency,
            listing_table.c.listing_status,
            listing_table.c.research_date,
        ).order_by(listing_table.c.research_date.asc(), listing_table.c.id.asc())
    ).mappings().all()

    def period_key(value: date) -> str:
        if normalized_granularity == "week":
            iso_year, iso_week, _ = value.isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
        return value.strftime("%Y-%m")

    group_field = {
        "model": "model",
        "brand": "brand",
        "category": "category_name",
    }[normalized_group]

    def empty_bucket() -> dict:
        return {
            "listing_count": 0,
            "unique_ids": set(),
            "sellers": set(),
            "prices": [],
            "out_of_stock_count": 0,
            "currencies": set(),
            "seller_rows": defaultdict(lambda: {"listing_count": 0, "prices": []}),
        }

    grouped: dict[tuple[str, str], dict] = defaultdict(empty_bucket)
    global_periods: dict[str, dict] = defaultdict(empty_bucket)
    groups_seen: set[str] = set()
    models_by_period: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        research_date = row.get("research_date")
        if not research_date:
            continue
        period = period_key(research_date)
        global_bucket = global_periods[period]
        global_bucket["listing_count"] += 1

        listing_id = (row.get("listing_id") or "").strip()
        if listing_id:
            global_bucket["unique_ids"].add(listing_id)

        model_value = (row.get("model") or "").strip()
        if model_value:
            models_by_period[period].add(model_value)

        seller = (row.get("seller_or_shop") or "").strip()
        if seller:
            global_bucket["sellers"].add(seller)

        status = (row.get("listing_status") or "").strip().lower()
        if status == "out_of_stock":
            global_bucket["out_of_stock_count"] += 1

        numeric_price = _safe_float(row.get("price"))
        if numeric_price is not None:
            global_bucket["prices"].append(numeric_price)

        currency_value = (row.get("currency") or "").strip().upper()
        if currency_value:
            global_bucket["currencies"].add(currency_value)

        group_name = (row.get(group_field) or "").strip()
        if not group_name:
            continue
        groups_seen.add(group_name)
        bucket = grouped[(group_name, period)]
        bucket["listing_count"] += 1
        if listing_id:
            bucket["unique_ids"].add(listing_id)
        if seller:
            bucket["sellers"].add(seller)
            seller_bucket = bucket["seller_rows"][seller]
            seller_bucket["listing_count"] += 1
            if numeric_price is not None:
                seller_bucket["prices"].append(numeric_price)
        if numeric_price is not None:
            bucket["prices"].append(numeric_price)
        if currency_value:
            bucket["currencies"].add(currency_value)
        if status == "out_of_stock":
            bucket["out_of_stock_count"] += 1

    periods = sorted(global_periods.keys())

    def currency_label(values: set[str]) -> str:
        if not values:
            return (currency or "USD").strip().upper() or "USD"
        if len(values) == 1:
            return next(iter(values))
        return "MIXED"

    def finalize(bucket: dict) -> dict:
        prices = [float(value) for value in bucket["prices"] if value is not None]
        average = (sum(prices) / len(prices)) if prices else None
        if prices and len(prices) > 1 and average is not None:
            variance = sum((value - average) ** 2 for value in prices) / len(prices)
            std = variance ** 0.5
        else:
            std = 0.0 if prices else None
        listing_count = int(bucket["listing_count"])
        out_of_stock_count = int(bucket["out_of_stock_count"])
        top_sellers: list[dict] = []
        for seller, seller_bucket in bucket["seller_rows"].items():
            seller_prices = [float(value) for value in seller_bucket["prices"] if value is not None]
            top_sellers.append(
                {
                    "seller": seller,
                    "listing_count": int(seller_bucket["listing_count"]),
                    "avg_price": round(sum(seller_prices) / len(seller_prices), 2) if seller_prices else None,
                    "min_price": round(min(seller_prices), 2) if seller_prices else None,
                }
            )
        top_sellers.sort(
            key=lambda item: (
                -item["listing_count"],
                item["avg_price"] if item["avg_price"] is not None else float("inf"),
                item["seller"].lower(),
            )
        )
        return {
            "listing_count": listing_count,
            "unique_ids": len(bucket["unique_ids"]),
            "seller_count": len(bucket["sellers"]),
            "seller_names": sorted(bucket["sellers"], key=str.lower),
            "price_sample": len(prices),
            "min_price": round(min(prices), 2) if prices else None,
            "max_price": round(max(prices), 2) if prices else None,
            "avg_price": round(average, 2) if average is not None else None,
            "median_price": round(_median(prices), 2) if prices else None,
            "p25": round(_percentile(prices, 0.25), 2) if prices else None,
            "p75": round(_percentile(prices, 0.75), 2) if prices else None,
            "std": round(std, 2) if std is not None else None,
            "cv": round((std / average) * 100, 2) if std is not None and average else None,
            "out_of_stock_count": out_of_stock_count,
            "out_of_stock_pct": round((out_of_stock_count / listing_count) * 100, 2) if listing_count else 0.0,
            "currency": currency_label(bucket["currencies"]),
            "top_sellers": top_sellers[:10],
        }

    group_period_rows: list[dict] = []
    internal_stats: dict[tuple[str, str], dict] = {}
    seller_history: dict[str, set[str]] = defaultdict(set)

    for group_name in sorted(groups_seen, key=str.lower):
        prior_sellers: set[str] = set()
        for period in periods:
            bucket = grouped.get((group_name, period))
            if not bucket:
                continue
            stats = finalize(bucket)
            current_sellers = set(stats.pop("seller_names"))
            new_sellers = sorted(current_sellers - prior_sellers, key=str.lower)
            stats["new_seller_count"] = len(new_sellers)
            stats["new_sellers"] = new_sellers[:10]
            stats["group"] = group_name
            stats["period"] = period
            internal_stats[(group_name, period)] = {**stats, "seller_names": current_sellers}
            group_period_rows.append(stats)
            prior_sellers.update(current_sellers)
            seller_history[group_name].update(current_sellers)

    latest_period = periods[-1] if periods else None
    previous_period = periods[-2] if len(periods) >= 2 else None
    latest_summary = None
    if latest_period:
        latest_summary = finalize(global_periods[latest_period])
        latest_summary.pop("seller_names", None)
        latest_summary["model_count"] = len(models_by_period.get(latest_period, set()))
        latest_summary["period"] = latest_period

    alerts: list[dict] = []
    severity_rank = {"critical": 3, "warning": 2, "info": 1}
    for group_name in sorted(groups_seen, key=str.lower):
        current = internal_stats.get((group_name, latest_period)) if latest_period else None
        previous = internal_stats.get((group_name, previous_period)) if previous_period else None
        if not current:
            continue

        current_avg = current.get("avg_price")
        previous_avg = previous.get("avg_price") if previous else None
        if current_avg is not None and previous_avg not in {None, 0}:
            drop_pct = ((previous_avg - current_avg) / previous_avg) * 100
            if drop_pct >= price_drop_warning_pct:
                severity = "critical" if drop_pct >= price_drop_critical_pct else "warning"
                alerts.append(
                    {
                        "type": "price_drop",
                        "severity": severity,
                        "severity_rank": severity_rank[severity],
                        "group": group_name,
                        "period": latest_period,
                        "currency": current.get("currency", "USD"),
                        "title": "Giá giảm mạnh",
                        "previous_avg_price": previous_avg,
                        "current_avg_price": current_avg,
                        "change_percent": round(-drop_pct, 2),
                        "message": f"Giá TB giảm {drop_pct:.1f}% so với kỳ liền trước.",
                    }
                )

        current_min = current.get("min_price")
        historical_mins = [
            internal_stats[(group_name, period)].get("min_price")
            for period in periods
            if period != latest_period and (group_name, period) in internal_stats
        ]
        historical_mins = [value for value in historical_mins if value is not None]
        if current_min is not None and historical_mins and current_min < min(historical_mins):
            alerts.append(
                {
                    "type": "new_low",
                    "severity": "warning",
                    "severity_rank": severity_rank["warning"],
                    "group": group_name,
                    "period": latest_period,
                    "currency": current.get("currency", "USD"),
                    "title": "Đáy giá mới",
                    "current_min_price": current_min,
                    "previous_floor_price": round(min(historical_mins), 2),
                    "message": "Giá thấp nhất kỳ này thấp hơn mọi kỳ trước trong phạm vi dữ liệu.",
                }
            )

        has_prior_group_period = any(
            period != latest_period and (group_name, period) in internal_stats
            for period in periods
        )
        if has_prior_group_period and current.get("new_seller_count", 0) > 0:
            alerts.append(
                {
                    "type": "new_seller",
                    "severity": "info",
                    "severity_rank": severity_rank["info"],
                    "group": group_name,
                    "period": latest_period,
                    "currency": current.get("currency", "USD"),
                    "title": "Người bán mới",
                    "new_seller_count": current.get("new_seller_count", 0),
                    "new_sellers": current.get("new_sellers", []),
                    "message": f"Có {current.get('new_seller_count', 0)} người bán mới xuất hiện trong kỳ này.",
                }
            )

        if previous:
            jump_points = float(current.get("out_of_stock_pct") or 0) - float(previous.get("out_of_stock_pct") or 0)
            if jump_points >= out_of_stock_warning_points:
                severity = "critical" if jump_points >= out_of_stock_critical_points else "warning"
                alerts.append(
                    {
                        "type": "out_of_stock_spike",
                        "severity": severity,
                        "severity_rank": severity_rank[severity],
                        "group": group_name,
                        "period": latest_period,
                        "currency": current.get("currency", "USD"),
                        "title": "Hết hàng hàng loạt",
                        "previous_out_of_stock_pct": previous.get("out_of_stock_pct", 0),
                        "current_out_of_stock_pct": current.get("out_of_stock_pct", 0),
                        "change_points": round(jump_points, 2),
                        "message": f"Tỷ lệ hết hàng tăng {jump_points:.1f} điểm % so với kỳ liền trước.",
                    }
                )

    alerts.sort(key=lambda item: (-int(item.get("severity_rank") or 0), item.get("group") or "", item.get("type") or ""))

    latest_group_counts: dict[str, int] = {}
    if latest_period:
        for group_name in groups_seen:
            stats = internal_stats.get((group_name, latest_period))
            latest_group_counts[group_name] = int(stats.get("listing_count") or 0) if stats else 0
    groups = sorted(groups_seen, key=lambda name: (-latest_group_counts.get(name, 0), name.lower()))

    for item in group_period_rows:
        item.pop("seller_names", None)

    return {
        "group_by": normalized_group,
        "granularity": normalized_granularity,
        "periods": periods,
        "groups": groups,
        "latest_period": latest_summary,
        "previous_period": previous_period,
        "group_periods": group_period_rows,
        "alerts": alerts,
        "meta": {
            "source_table": "public.marketplace_research_results",
            "time_field": "research_date",
            "group_field": group_field,
            "row_count": len(rows),
            "price_drop_warning_pct": price_drop_warning_pct,
            "price_drop_critical_pct": price_drop_critical_pct,
            "out_of_stock_warning_points": out_of_stock_warning_points,
            "out_of_stock_critical_points": out_of_stock_critical_points,
        },
    }


def fetch_hqa_dashboard_filter_options(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
    )

    options = {
        "marketplaces": _collect_dashboard_option_values(db, statement, "marketplace"),
        "brands": _collect_dashboard_option_values(db, statement, "brand"),
        "models": _collect_dashboard_option_values(db, statement, "model"),
        "statuses": _collect_dashboard_option_values(db, statement, "listing_status"),
        "category_names": _collect_dashboard_option_values(db, statement, "category_name"),
        "sellers": _collect_dashboard_option_values(db, statement, "seller_or_shop"),
        "currencies": _collect_dashboard_option_values(db, statement, "currency"),
    }

    buying_scope = statement.order_by(None).subquery("dashboard_buying_scope")
    buying_rows = db.execute(select(buying_scope.c.buying_options)).all()
    buying_map: dict[str, str] = {}
    for row in buying_rows:
        for token in _parse_buying_options(row[0]):
            normalized = token.strip().lower()
            if normalized and normalized not in buying_map:
                buying_map[normalized] = token.strip()
    options["buying_options"] = [buying_map[key] for key in sorted(buying_map.keys())]

    return {
        "options": options,
        "meta": {
            "filter_limit": FILTER_OPTIONS_LIMIT,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
    }


def fetch_hqa_dashboard_total_sellers(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
):
    statement = select(listing_table.c.seller_or_shop, listing_table.c.research_date)
    statement = _apply_dashboard_date_and_numeric_filters(
        statement,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
    )
    scope = statement.order_by(None).subquery("dashboard_total_sellers_scope")
    seller_expr = func.trim(func.coalesce(scope.c.seller_or_shop, ""))
    row = db.execute(
        select(
            func.count(func.distinct(func.nullif(seller_expr, ""))).label("total_sellers"),
        )
    ).mappings().one()
    return {
        "title": "Total Sellers",
        "description": "Nguoi ban trong database",
        "total_sellers": _safe_int(row.get("total_sellers")),
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "seller_column": "seller_or_shop",
        "date_column": "research_date",
    }


def fetch_hqa_dashboard_sellers_summary(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
    )
    scope = statement.order_by(None).subquery("seller_scope")

    seller_expr = func.trim(func.coalesce(scope.c.seller_or_shop, ""))
    status_expr = func.lower(func.trim(func.coalesce(scope.c.listing_status, "")))
    active_seller_case = case((status_expr == "active", func.nullif(seller_expr, "")), else_=None)
    row = db.execute(
        select(
            func.count(func.distinct(func.nullif(seller_expr, ""))).label("total_sellers"),
            func.count(func.distinct(active_seller_case)).label("active_sellers"),
            func.count().label("total_rows"),
        )
    ).mappings().one()

    new_sellers = 0
    if date_from:
        historical_statement = _build_dashboard_rows_statement(
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=None,
            date_to=date_from - timedelta(days=1),
            min_price=None,
            max_price=None,
        )
        historical_scope = historical_statement.order_by(None).subquery("seller_history")
        historical_values = {
            (item[0] or "").strip().lower()
            for item in db.execute(select(historical_scope.c.seller_or_shop)).all()
            if (item[0] or "").strip()
        }
        current_values = {
            (item[0] or "").strip().lower()
            for item in db.execute(select(scope.c.seller_or_shop)).all()
            if (item[0] or "").strip()
        }
        new_sellers = len(current_values - historical_values)

    return {
        "total_sellers": _safe_int(row.get("total_sellers")),
        "new_sellers": new_sellers,
        "active_sellers": _safe_int(row.get("active_sellers")),
        "total_listings": _safe_int(row.get("total_rows")),
    }


def fetch_hqa_dashboard_sellers_trend(
    db: Session,
    *,
    granularity: str,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    normalized_granularity = _parse_dashboard_granularity(granularity)
    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
    )
    scope = statement.order_by(None).subquery("seller_trend_scope")
    period_expr = _dashboard_bucket_expression(db, normalized_granularity, scope.c.research_date)
    seller_expr = func.trim(func.coalesce(scope.c.seller_or_shop, ""))
    query = (
        select(
            period_expr.label("period"),
            func.count(func.distinct(func.nullif(seller_expr, ""))).label("seller_count"),
            func.count().label("listing_count"),
        )
        .select_from(scope)
        .where(scope.c.research_date.is_not(None))
        .group_by(period_expr)
        .order_by(period_expr.asc())
    )
    rows = db.execute(query).mappings().all()

    first_seen_scope = (
        select(
            seller_expr.label("seller"),
            func.min(scope.c.research_date).label("first_seen_date"),
        )
        .where(scope.c.research_date.is_not(None))
        .where(seller_expr != "")
        .group_by(seller_expr)
    ).subquery("seller_first_seen_scope")

    first_seen_period_expr = _dashboard_bucket_expression(db, normalized_granularity, first_seen_scope.c.first_seen_date)
    new_seller_rows = db.execute(
        select(
            first_seen_period_expr.label("period"),
            func.count().label("new_sellers"),
        )
        .select_from(first_seen_scope)
        .group_by(first_seen_period_expr)
        .order_by(first_seen_period_expr.asc())
    ).mappings().all()
    new_sellers_by_period = {
        str(row.get("period") or "unknown"): _safe_int(row.get("new_sellers"))
        for row in new_seller_rows
    }

    return {
        "granularity": normalized_granularity,
        "points": [
            {
                "period": row.get("period") or "unknown",
                "total_sellers": _safe_int(row.get("seller_count")),
                "seller_count": _safe_int(row.get("seller_count")),
                "new_sellers": new_sellers_by_period.get(str(row.get("period") or "unknown"), 0),
                "listing_count": _safe_int(row.get("listing_count")),
            }
            for row in rows
        ],
    }


def fetch_hqa_dashboard_top_sellers(
    db: Session,
    *,
    limit: int,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=None,
        max_price=None,
    )
    scope = statement.order_by(None).subquery("top_seller_scope")

    seller_expr = func.trim(func.coalesce(scope.c.seller_or_shop, ""))
    query = (
        select(
            seller_expr.label("seller"),
            func.count().label("listing_count"),
            func.count(func.distinct(func.nullif(func.trim(scope.c.listing_id), ""))).label("unique_listings"),
            func.avg(scope.c.price).label("avg_price"),
            func.min(scope.c.price).label("min_price"),
            func.max(scope.c.price).label("max_price"),
        )
        .where(seller_expr != "")
        .group_by(seller_expr)
        .order_by(func.count().desc(), seller_expr.asc())
        .limit(limit)
    )
    rows = db.execute(query).mappings().all()
    return {
        "items": [
            {
                "seller": row.get("seller") or "",
                "listing_count": _safe_int(row.get("listing_count")),
                "unique_listings": _safe_int(row.get("unique_listings")),
                "avg_price": round(_safe_float(row.get("avg_price")) or 0.0, 2),
                "min_price": round(_safe_float(row.get("min_price")) or 0.0, 2),
                "max_price": round(_safe_float(row.get("max_price")) or 0.0, 2),
            }
            for row in rows
        ]
    }


def _build_price_scope_statement(
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    return _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    ).where(listing_table.c.price.is_not(None))


def _currency_label(rows: list[dict]) -> str:
    values = {
        (row.get("currency") or "").strip().upper()
        for row in rows
        if (row.get("currency") or "").strip()
    }
    if not values:
        return "unknown"
    if len(values) == 1:
        return next(iter(values))
    return "mixed"


def fetch_hqa_dashboard_prices_summary(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    statement = _build_price_scope_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    scope = statement.order_by(None).subquery("price_summary_scope")
    row = db.execute(
        select(
            func.count().label("sample_size"),
            func.avg(scope.c.price).label("avg_price"),
            func.min(scope.c.price).label("min_price"),
            func.max(scope.c.price).label("max_price"),
        )
    ).mappings().one()
    prices = [float(item[0]) for item in db.execute(select(scope.c.price)).all() if item[0] is not None]
    currency_rows = db.execute(select(scope.c.currency)).mappings().all()
    return {
        "sample_size": _safe_int(row.get("sample_size")),
        "price_sample": _safe_int(row.get("sample_size")),
        "avg_price": round(_safe_float(row.get("avg_price")) or 0.0, 2),
        "median_price": round(_median(prices), 2),
        "min_price": round(_safe_float(row.get("min_price")) or 0.0, 2),
        "max_price": round(_safe_float(row.get("max_price")) or 0.0, 2),
        "currency": _currency_label(currency_rows),
    }


def fetch_hqa_dashboard_prices_trend(
    db: Session,
    *,
    granularity: str,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    normalized_granularity = _parse_dashboard_granularity(granularity)
    statement = _build_price_scope_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    scope = statement.order_by(None).subquery("price_trend_scope")
    period_expr = _dashboard_bucket_expression(db, normalized_granularity, scope.c.research_date)
    rows = db.execute(
        select(
            period_expr.label("period"),
            func.count().label("sample_size"),
            func.avg(scope.c.price).label("avg_price"),
            func.min(scope.c.price).label("min_price"),
            func.max(scope.c.price).label("max_price"),
        )
        .select_from(scope)
        .where(scope.c.research_date.is_not(None))
        .group_by(period_expr)
        .order_by(period_expr.asc())
    ).mappings().all()

    by_period_prices: dict[str, list[float]] = defaultdict(list)
    for period, price in db.execute(
        select(period_expr.label("period"), scope.c.price)
        .select_from(scope)
        .where(scope.c.research_date.is_not(None))
        .order_by(period_expr.asc())
    ).all():
        if period and price is not None:
            by_period_prices[str(period)].append(float(price))

    return {
        "granularity": normalized_granularity,
        "points": [
            {
                "period": row.get("period") or "unknown",
                "sample_size": _safe_int(row.get("sample_size")),
                "avg_price": round(_safe_float(row.get("avg_price")) or 0.0, 2),
                "median_price": round(_median(by_period_prices.get(str(row.get("period") or ""), [])), 2),
                "min_price": round(_safe_float(row.get("min_price")) or 0.0, 2),
                "max_price": round(_safe_float(row.get("max_price")) or 0.0, 2),
            }
            for row in rows
        ],
    }


def fetch_hqa_dashboard_prices_by_keyword(
    db: Session,
    *,
    limit: int,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    statement = _build_price_scope_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    rows = db.execute(
        statement.with_only_columns(
            listing_table.c.listing_title,
            listing_table.c.price,
            listing_table.c.currency,
        )
    ).all()

    stop_words = {
        "the", "and", "for", "with", "from", "this", "that", "new", "used", "sale", "audio",
        "ebay", "reverb", "etsy", "vintage", "speaker", "speakers", "receiver", "listing",
    }
    bucket: dict[str, dict[str, object]] = {}
    total_hits = 0
    for title, price, _ in rows:
        numeric_price = _safe_float(price)
        if numeric_price is None:
            continue
        tokens = [token for token in re.findall(r"[a-z0-9]{3,}", (title or "").lower()) if token not in stop_words]
        for token in tokens[:8]:
            total_hits += 1
            payload = bucket.setdefault(token, {"count": 0, "prices": []})
            payload["count"] = int(payload["count"]) + 1
            payload["prices"].append(numeric_price)

    ranked = sorted(bucket.items(), key=lambda item: (-int(item[1]["count"]), item[0]))[:limit]
    items = []
    for token, payload in ranked:
        prices = [float(value) for value in payload["prices"]]
        count = int(payload["count"])
        items.append(
            {
                "keyword": token,
                "count": count,
                "share_pct": round((count / total_hits) * 100, 2) if total_hits else 0,
                "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
                "min_price": round(min(prices), 2) if prices else 0,
                "max_price": round(max(prices), 2) if prices else 0,
            }
        )

    return {
        "items": items,
        "total_hits": total_hits,
    }


def fetch_hqa_dashboard_alerts(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    price_drop_threshold_pct: float,
    price_drop_warning_threshold_pct: float,
    price_drop_critical_threshold_pct: float,
    min_sample_for_price_alert: int,
    new_seller_lookback_days: int,
    out_of_stock_min_count: int,
    out_of_stock_alert_percent: float,
):
    price_trend = fetch_hqa_dashboard_prices_trend(
        db,
        granularity="month",
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    seller_trend = fetch_hqa_dashboard_sellers_trend(
        db,
        granularity="month",
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )

    statement = _build_dashboard_rows_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    scope = statement.order_by(None).subquery("alerts_scope")

    alerts: list[dict] = []

    points = price_trend.get("points") or []
    if len(points) >= 2:
        previous = points[-2]
        current = points[-1]
        prev_avg = _safe_float(previous.get("avg_price")) or 0
        curr_avg = _safe_float(current.get("avg_price")) or 0
        prev_sample = _safe_int(previous.get("sample_size"))
        curr_sample = _safe_int(current.get("sample_size"))
        if prev_avg > 0 and prev_sample >= min_sample_for_price_alert and curr_sample >= min_sample_for_price_alert:
            drop_pct = ((prev_avg - curr_avg) / prev_avg) * 100
            warning_threshold = max(0.0, float(price_drop_warning_threshold_pct or 0.0))
            critical_threshold = max(warning_threshold, float(price_drop_critical_threshold_pct or 0.0))
            fallback_threshold = max(0.0, float(price_drop_threshold_pct or 0.0))
            if warning_threshold <= 0:
                warning_threshold = fallback_threshold
            if critical_threshold <= 0:
                critical_threshold = max(warning_threshold, fallback_threshold)

            severity = None
            if drop_pct >= critical_threshold:
                severity = "critical"
            elif drop_pct >= warning_threshold:
                severity = "warning"

            if severity:
                alerts.append(
                    {
                        "type": "price_drop",
                        "severity": severity,
                        "brand": (brands or [None])[0],
                        "model": (models or [None])[0],
                        "period": current.get("period"),
                        "previous_avg_price": round(prev_avg, 2),
                        "current_avg_price": round(curr_avg, 2),
                        "change_percent": round(((curr_avg - prev_avg) / prev_avg) * 100, 2),
                        "value": round(drop_pct, 2),
                        "message": f"Average price decreased {drop_pct:.2f}% compared with previous period",
                    }
                )

    status_period_expr = _dashboard_bucket_expression(db, "month", scope.c.research_date)
    scope_status_expr = func.lower(func.trim(func.coalesce(scope.c.listing_status, "")))
    status_rows = db.execute(
        select(
            status_period_expr.label("period"),
            func.coalesce(func.sum(case((scope_status_expr == "out_of_stock", 1), else_=0)), 0).label("out_of_stock_count"),
        )
        .select_from(scope)
        .where(scope.c.research_date.is_not(None))
        .group_by(status_period_expr)
        .order_by(status_period_expr.asc())
    ).mappings().all()

    if len(status_rows) >= 2:
        current = status_rows[-1]
        baseline_values = [_safe_int(item.get("out_of_stock_count")) for item in status_rows[:-1]]
        baseline_avg = (sum(baseline_values) / len(baseline_values)) if baseline_values else 0
        current_count = _safe_int(current.get("out_of_stock_count"))
        if current_count >= out_of_stock_min_count and baseline_avg > 0:
            growth_pct = ((current_count - baseline_avg) / baseline_avg) * 100
            if growth_pct >= out_of_stock_alert_percent:
                alerts.append(
                    {
                        "type": "out_of_stock_spike",
                        "severity": "high",
                        "period": current.get("period"),
                        "value": round(growth_pct, 2),
                        "message": f"Out-of-stock count increased {growth_pct:.2f}% versus baseline",
                    }
                )

    if date_to:
        lookback_start = date_to - timedelta(days=max(new_seller_lookback_days, 1))
        current_sellers = {
            (row[0] or "").strip().lower()
            for row in db.execute(
                select(scope.c.seller_or_shop).where(scope.c.research_date >= lookback_start)
            ).all()
            if (row[0] or "").strip()
        }
        previous_statement = _build_dashboard_rows_statement(
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=None,
            date_to=lookback_start - timedelta(days=1),
            min_price=min_price,
            max_price=max_price,
        ).order_by(None)
        previous_scope = previous_statement.subquery("alerts_previous_sellers")
        previous_sellers = {
            (row[0] or "").strip().lower()
            for row in db.execute(select(previous_scope.c.seller_or_shop)).all()
            if (row[0] or "").strip()
        }
        new_sellers = sorted(current_sellers - previous_sellers)
        if new_sellers:
            alerts.append(
                {
                    "type": "new_seller_detected",
                    "severity": "medium",
                    "period": lookback_start.isoformat(),
                    "value": len(new_sellers),
                    "message": f"Detected {len(new_sellers)} new sellers in the last {new_seller_lookback_days} days",
                    "sample": new_sellers[:10],
                }
            )

    return {
        "alerts": alerts,
        "trend_points": {
            "price": len(points),
            "seller": len(seller_trend.get("points") or []),
        },
    }


def fetch_hqa_dashboard_summary(
    db: Session,
    *,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    return {
        "seller_analytics": fetch_hqa_dashboard_sellers_summary(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=None,
            max_price=None,
        ),
        "price_analytics": fetch_hqa_dashboard_prices_summary(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        ),
    }


def fetch_hqa_dashboard_price_comparison(
    db: Session,
    *,
    limit: int,
    compare_by: str | None,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
):
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    mode = (compare_by or "").strip().lower()
    if not mode:
        if brands and not models:
            mode = "model"
        elif models:
            mode = "model"
        elif keyword:
            mode = "keyword"
        else:
            mode = "brand"

    if mode == "keyword":
        payload = fetch_hqa_dashboard_prices_by_keyword(
            db,
            limit=limit,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )
        return {"compare_by": "keyword", "items": payload.get("items") or []}

    if mode not in {"brand", "model"}:
        raise ValueError("compare_by must be one of: brand, model, keyword")

    statement = _build_price_scope_statement(
        keyword=keyword,
        marketplaces=marketplaces,
        brands=brands,
        models=models,
        statuses=statuses,
        category_names=category_names,
        buying_options=buying_options,
        sellers=sellers,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
    )
    scope = statement.order_by(None).subquery("price_comparison_scope")
    group_column = scope.c.brand if mode == "brand" else scope.c.model
    name_expr = func.trim(func.coalesce(group_column, ""))
    detail_rows = db.execute(
        select(
            name_expr.label("name"),
            scope.c.price.label("price"),
            func.coalesce(scope.c.seller_or_shop, "").label("seller"),
            func.coalesce(scope.c.listing_status, "").label("status"),
        ).where(name_expr != "")
    ).mappings().all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for detail in detail_rows:
        grouped[detail.get("name") or ""].append(detail)

    previous_grouped: dict[str, list[dict]] = {}
    if date_from and date_to and date_to >= date_from:
        window_days = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=window_days - 1)
        previous_statement = _build_price_scope_statement(
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=previous_from,
            date_to=previous_to,
            min_price=min_price,
            max_price=max_price,
        )
        previous_scope = previous_statement.order_by(None).subquery("price_comparison_previous_scope")
        previous_group_column = previous_scope.c.brand if mode == "brand" else previous_scope.c.model
        previous_name_expr = func.trim(func.coalesce(previous_group_column, ""))
        previous_rows = db.execute(
            select(
                previous_name_expr.label("name"),
                previous_scope.c.price.label("price"),
                func.coalesce(previous_scope.c.seller_or_shop, "").label("seller"),
                func.coalesce(previous_scope.c.listing_status, "").label("status"),
            ).where(previous_name_expr != "")
        ).mappings().all()
        previous_grouped = defaultdict(list)
        for detail in previous_rows:
            previous_grouped[detail.get("name") or ""].append(detail)

    def _group_price_stats(entries: list[dict]) -> dict:
        prices = [float(entry["price"]) for entry in entries if entry.get("price") is not None]
        seller_names = {
            (entry.get("seller") or "").strip()
            for entry in entries
            if (entry.get("seller") or "").strip()
        }
        out_of_stock = sum(1 for entry in entries if (entry.get("status") or "") == "out_of_stock")
        total_rows = len(entries)
        average = sum(prices) / len(prices) if prices else 0.0
        if len(prices) > 1:
            variance = sum((value - average) ** 2 for value in prices) / len(prices)
            deviation = variance ** 0.5
        else:
            deviation = 0.0
        return {
            "sample_size": len(prices),
            "seller_count": len(seller_names),
            "sellers": seller_names,
            "avg_price": round(average, 2),
            "min_price": round(min(prices), 2) if prices else 0.0,
            "max_price": round(max(prices), 2) if prices else 0.0,
            "median_price": round(_median(prices), 2),
            "p25": round(_percentile(prices, 0.25), 2),
            "p75": round(_percentile(prices, 0.75), 2),
            "cv": round((deviation / average) * 100, 1) if average else 0.0,
            "out_of_stock_pct": round((out_of_stock / total_rows) * 100, 1) if total_rows else 0.0,
        }

    def _group_top_sellers(entries: list[dict]) -> list[dict]:
        per_seller: dict[str, list[float]] = defaultdict(list)
        for entry in entries:
            seller = (entry.get("seller") or "").strip()
            if not seller or entry.get("price") is None:
                continue
            per_seller[seller].append(float(entry["price"]))
        summaries = [
            {
                "seller": seller,
                "listing_count": len(values),
                "avg_price": round(sum(values) / len(values), 2),
                "min_price": round(min(values), 2),
            }
            for seller, values in per_seller.items()
        ]
        summaries.sort(key=lambda summary: (-summary["listing_count"], summary["avg_price"]))
        return summaries[:10]

    items: list[dict] = []
    for name, entries in grouped.items():
        stats = _group_price_stats(entries)
        previous_entries = previous_grouped.get(name, [])
        previous_stats = _group_price_stats(previous_entries) if previous_entries else None
        new_sellers = sorted(stats["sellers"] - (previous_stats["sellers"] if previous_stats else set()))
        item = {
            "name": name,
            "sample_size": stats["sample_size"],
            "seller_count": stats["seller_count"],
            "avg_price": stats["avg_price"],
            "min_price": stats["min_price"],
            "max_price": stats["max_price"],
            "median_price": stats["median_price"],
            "p25": stats["p25"],
            "p75": stats["p75"],
            "cv": stats["cv"],
            "out_of_stock_pct": stats["out_of_stock_pct"],
            "top_sellers": _group_top_sellers(entries),
            "new_seller_count": len(new_sellers),
            "new_sellers": new_sellers[:10],
        }
        if previous_stats is not None:
            item["previous_avg_price"] = previous_stats["avg_price"]
            item["previous_min_price"] = previous_stats["min_price"]
            item["previous_max_price"] = previous_stats["max_price"]
            item["previous_median_price"] = previous_stats["median_price"]
            item["previous_seller_count"] = previous_stats["seller_count"]
            item["previous_out_of_stock_pct"] = previous_stats["out_of_stock_pct"]
        items.append(item)

    items.sort(key=lambda entry: (-entry["avg_price"], entry["name"]))
    items = items[:limit]

    return {"compare_by": mode, "items": items}


def fetch_hqa_dashboard_export_rows(
    db: Session,
    *,
    dataset: str,
    granularity: str,
    top_limit: int,
    keyword: str | None,
    marketplaces: list[str] | None,
    brands: list[str] | None,
    models: list[str] | None,
    statuses: list[str] | None,
    category_names: list[str] | None,
    buying_options: list[str] | None,
    sellers: list[str] | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    min_price: Decimal | float | None,
    max_price: Decimal | float | None,
    price_drop_threshold_pct: float,
    price_drop_warning_threshold_pct: float,
    price_drop_critical_threshold_pct: float,
    min_sample_for_price_alert: int,
    new_seller_lookback_days: int,
    out_of_stock_min_count: int,
    out_of_stock_alert_percent: float,
) -> list[dict]:
    if dataset == "summary":
        summary = fetch_hqa_dashboard_summary(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )
        row = {}
        row.update({f"seller_{key}": value for key, value in (summary.get("seller_analytics") or {}).items()})
        row.update({f"price_{key}": value for key, value in (summary.get("price_analytics") or {}).items()})
        return [row]
    if dataset == "sellers_summary":
        return [
            fetch_hqa_dashboard_sellers_summary(
                db,
                keyword=keyword,
                marketplaces=marketplaces,
                brands=brands,
                models=models,
                statuses=statuses,
                category_names=category_names,
                buying_options=buying_options,
                sellers=sellers,
                currency=currency,
                date_from=date_from,
                date_to=date_to,
                min_price=None,
                max_price=None,
            )
        ]
    if dataset == "seller_trend":
        return fetch_hqa_dashboard_sellers_trend(
            db,
            granularity=granularity,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=None,
            max_price=None,
        )["points"]
    if dataset == "sellers_trend":
        return fetch_hqa_dashboard_sellers_trend(
            db,
            granularity=granularity,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=None,
            max_price=None,
        )["points"]
    if dataset == "sellers_top":
        return fetch_hqa_dashboard_top_sellers(
            db,
            limit=top_limit,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=None,
            max_price=None,
        )["items"]
    if dataset == "prices_summary":
        return [
            fetch_hqa_dashboard_prices_summary(
                db,
                keyword=keyword,
                marketplaces=marketplaces,
                brands=brands,
                models=models,
                statuses=statuses,
                category_names=category_names,
                buying_options=buying_options,
                sellers=sellers,
                currency=currency,
                date_from=date_from,
                date_to=date_to,
                min_price=min_price,
                max_price=max_price,
            )
        ]
    if dataset == "prices_trend":
        return fetch_hqa_dashboard_prices_trend(
            db,
            granularity=granularity,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )["points"]
    if dataset == "price_trend":
        return fetch_hqa_dashboard_prices_trend(
            db,
            granularity=granularity,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )["points"]
    if dataset == "prices_by_keyword":
        return fetch_hqa_dashboard_prices_by_keyword(
            db,
            limit=top_limit,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )["items"]
    if dataset == "price_comparison":
        return fetch_hqa_dashboard_price_comparison(
            db,
            limit=top_limit,
            compare_by="",
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
        )["items"]
    if dataset == "alerts":
        return fetch_hqa_dashboard_alerts(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            brands=brands,
            models=models,
            statuses=statuses,
            category_names=category_names,
            buying_options=buying_options,
            sellers=sellers,
            currency=currency,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            max_price=max_price,
            price_drop_threshold_pct=price_drop_threshold_pct,
            price_drop_warning_threshold_pct=price_drop_warning_threshold_pct,
            price_drop_critical_threshold_pct=price_drop_critical_threshold_pct,
            min_sample_for_price_alert=min_sample_for_price_alert,
            new_seller_lookback_days=new_seller_lookback_days,
            out_of_stock_min_count=out_of_stock_min_count,
            out_of_stock_alert_percent=out_of_stock_alert_percent,
        )["alerts"]
    raise ValueError("Invalid dataset")

# --- HQA Dashboard Product Analytics v5 (integrated) ---
# HQA product-first dashboard analytics. Integrated in service.py.
_PD_ROLE_WHOLE = "whole_product"
_PD_ROLE_COMPONENT = "component_part"
_PD_ROLE_ACCESSORY = "accessory"
_PD_ROLE_DOC = "documentation_media"
_PD_ROLE_IRRELEVANT = "irrelevant"
_PD_ROLE_UNCERTAIN = "uncertain"
_PD_CATALOG_CACHE = None
_PD_COMPONENT_WORDS = ("woofer", "driver", "tweeter", "crossover", "terminal", "foam", "surround", "cone", "diaphragm", "board", "pcb", "module", "transformer", "knob", "switch", "jack", "frame", "voice coil", "dust cap", "repair kit", "edge ring", "replacement", "enclosure only", "cabinet only", "speaker part", "parts only")
_PD_ACCESSORY_WORDS = ("grill", "grille", "cover", "stand", "mount", "case", "skin", "badge", "cable", "remote", "bracket", "dust cover")
_PD_DOC_WORDS = ("service manual", "owner manual", "owners manual", "manual", "brochure", "catalog", "catalogue", "schematic", "book", "service guide", "repair manual", "dealer literature")
_PD_WHOLE_WORDS = ("pair speakers", "speakers pair", "speaker pair", "stereo receiver", "integrated amplifier", "power amplifier", "acoustic guitar", "electric guitar", "turntable", "complete", "fully working", "tested working", "restored")


def _pd_text(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _pd_hits(text_value, words):
    return [word for word in words if word in text_value]


def _pd_catalog():
    global _PD_CATALOG_CACHE
    if _PD_CATALOG_CACHE is None:
        _PD_CATALOG_CACHE = tuple(load_keyword_catalog()["usable_entries"])
    return _PD_CATALOG_CACHE


def _pd_product_label(entry):
    keyword = str(entry.keyword or "").strip()
    tokens = keyword.split()
    if len(tokens) >= 2 and keyword.lower() not in {str(entry.brand or "").strip().lower(), str(entry.model or "").strip().lower()}:
        return keyword
    return " ".join(part for part in (str(entry.brand or "").strip(), str(entry.model or "").strip(), str(entry.category or "").strip()) if part) or entry.product_id


def _pd_identity(row):
    title = normalize_match_text(row.get("listing_title"))
    brand = normalize_match_text(row.get("brand"))
    model = normalize_match_text(row.get("model"))
    ranked = []
    for entry in _pd_catalog():
        score = 0
        reasons = []
        if brand and entry.normalized_brand:
            score += 3 if brand == entry.normalized_brand else -3
            if brand == entry.normalized_brand:
                reasons.append("brand matches catalog")
        if model and entry.normalized_model:
            score += 8 if model == entry.normalized_model else -7
            if model == entry.normalized_model:
                reasons.append("model matches catalog")
        if entry.normalized_brand and entry.normalized_brand in title:
            score += 2
        if entry.normalized_model and entry.normalized_model in title:
            score += 7
            reasons.append("title contains catalog model")
        if entry.normalized_keyword and entry.normalized_keyword in title:
            score += 4
            reasons.append("title matches catalog keyword")
        if (entry.normalized_model and entry.normalized_model in title) or (model and model == entry.normalized_model) or (entry.normalized_keyword and entry.normalized_keyword in title):
            if score >= 7:
                ranked.append((score, entry, reasons))
    if ranked:
        ranked.sort(key=lambda item: (-item[0], item[1].product_id, item[1].keyword.lower()))
        score, entry, reasons = ranked[0]
        if len(ranked) > 1 and ranked[1][1].product_id != entry.product_id and score - ranked[1][0] < 2 and score < 14:
            return None
        return {
            "product_key": str(entry.product_id or "").strip() or f"fallback:{entry.normalized_brand}:{entry.normalized_model}:{entry.normalized_keyword}",
            "product_id": str(entry.product_id or "").strip() or None,
            "product_label": _pd_product_label(entry),
            "keyword": str(entry.keyword or "").strip(),
            "brand": str(entry.brand or "").strip(),
            "model": str(entry.model or "").strip(),
            "product_type": str(entry.category or "").strip(),
            "identity_confidence": max(55, min(99, 58 + score * 3)),
            "identity_reasons": reasons,
        }
    raw_brand = str(row.get("brand") or "").strip()
    raw_model = str(row.get("model") or "").strip()
    raw_category = str(row.get("category") or row.get("category_name") or "").strip()
    if raw_brand and raw_model:
        return {
            "product_key": f"fallback:{normalize_match_text(raw_brand)}:{normalize_match_text(raw_model)}:{normalize_match_text(raw_category)}",
            "product_id": None,
            "product_label": f"{raw_brand} {raw_model}".strip(),
            "keyword": "",
            "brand": raw_brand,
            "model": raw_model,
            "product_type": raw_category,
            "identity_confidence": 68,
            "identity_reasons": ["fallback brand + model + category"],
        }
    return None


def _pd_classify(row, product, reference_median=None):
    title = _pd_text(row.get("listing_title"))
    category = _pd_text(f"{row.get('category') or ''} {row.get('category_name') or ''}")
    condition = _pd_text(row.get("condition"))
    scores = {_PD_ROLE_WHOLE: 0, _PD_ROLE_COMPONENT: 0, _PD_ROLE_ACCESSORY: 0, _PD_ROLE_DOC: 0, _PD_ROLE_IRRELEVANT: 0}
    reasons = defaultdict(list)
    component = _pd_hits(title, _PD_COMPONENT_WORDS)
    accessory = _pd_hits(title, _PD_ACCESSORY_WORDS)
    docs = _pd_hits(title, _PD_DOC_WORDS)
    whole = _pd_hits(title, _PD_WHOLE_WORDS)
    if component:
        scores[_PD_ROLE_COMPONENT] += 7 + min(3, len(component) - 1); reasons[_PD_ROLE_COMPONENT].append("title: " + ", ".join(component[:3]))
    if accessory:
        scores[_PD_ROLE_ACCESSORY] += 6 + min(2, len(accessory) - 1); reasons[_PD_ROLE_ACCESSORY].append("title: " + ", ".join(accessory[:3]))
    if docs:
        scores[_PD_ROLE_DOC] += 8; reasons[_PD_ROLE_DOC].append("documentation title: " + ", ".join(docs[:2]))
    if whole:
        scores[_PD_ROLE_WHOLE] += 4 + min(2, len(whole) - 1); reasons[_PD_ROLE_WHOLE].append("whole-product title: " + ", ".join(whole[:2]))
    if any(word in category for word in ("parts", "components", "woofers", "drivers", "tweeters")):
        scores[_PD_ROLE_COMPONENT] += 5; reasons[_PD_ROLE_COMPONENT].append("category suggests component")
    if any(word in category for word in ("accessories", "covers", "mounts", "cases")):
        scores[_PD_ROLE_ACCESSORY] += 4; reasons[_PD_ROLE_ACCESSORY].append("category suggests accessory")
    if any(word in category for word in ("manual", "books", "catalog")):
        scores[_PD_ROLE_DOC] += 5; reasons[_PD_ROLE_DOC].append("category suggests documentation")
    if any(word in category for word in ("speakers", "receiver", "amplifier", "turntable", "guitar", "home audio")):
        scores[_PD_ROLE_WHOLE] += 2; reasons[_PD_ROLE_WHOLE].append("category supports whole product")
    if int(product.get("identity_confidence") or 0) >= 80:
        scores[_PD_ROLE_WHOLE] += 2; reasons[_PD_ROLE_WHOLE].append("strong product linkage")
    if normalize_match_text(product.get("model")) and normalize_match_text(product.get("model")) in normalize_match_text(row.get("listing_title")):
        scores[_PD_ROLE_WHOLE] += 1
    if "for parts" in condition or "not working" in condition:
        reasons[_PD_ROLE_WHOLE].append("for-parts/not-working is condition only")
    if bool(row.get("exclude_flag")):
        scores[_PD_ROLE_IRRELEVANT] += 2; reasons[_PD_ROLE_IRRELEVANT].append("exclude_flag caution")
    price = _safe_float(row.get("price"))
    if reference_median and reference_median > 0 and price is not None:
        ratio = price / reference_median
        if ratio < .18 and scores[_PD_ROLE_COMPONENT] >= 4:
            scores[_PD_ROLE_COMPONENT] += 2; reasons[_PD_ROLE_COMPONENT].append(f"price {ratio:.0%} of whole reference")
        elif ratio < .30 and scores[_PD_ROLE_ACCESSORY] >= 4:
            scores[_PD_ROLE_ACCESSORY] += 1; reasons[_PD_ROLE_ACCESSORY].append(f"price {ratio:.0%} of whole reference")
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    role, top = ranked[0]
    second = ranked[1][1]
    if top < 3 or (top - second <= 1 and second >= 3):
        role = _PD_ROLE_UNCERTAIN
        role_reasons = ["conflicting or insufficient role evidence"]
        confidence = 55
    else:
        role_reasons = reasons[role] or ["deterministic multi-signal score"]
        confidence = max(60, min(99, 55 + top * 5 - max(0, second) * 2))
    return {"listing_role": role, "role_confidence": confidence, "role_reasons": role_reasons[:4], "eligible_for_market_analytics": role == _PD_ROLE_WHOLE and confidence >= 65}


def _pd_finalize(items, currency):
    eligible = [item for item in items if item["classification"]["eligible_for_market_analytics"]]
    prices = [float(item["row"]["price"]) for item in eligible if item["row"].get("price") is not None]
    sellers = {str(item["row"].get("seller_or_shop") or "").strip() for item in eligible if str(item["row"].get("seller_or_shop") or "").strip()}
    listing_ids = {str(item["row"].get("listing_id") or "").strip() for item in eligible if str(item["row"].get("listing_id") or "").strip()}
    roles = defaultdict(int)
    for item in items: roles[item["classification"]["listing_role"]] += 1
    average = sum(prices) / len(prices) if prices else None
    std = (sum((value-average)**2 for value in prices)/len(prices))**.5 if prices and average is not None else None
    oos = sum(1 for item in eligible if str(item["row"].get("listing_status") or "").strip().lower() == "out_of_stock")
    seller_rows = defaultdict(list)
    for item in eligible:
        seller = str(item["row"].get("seller_or_shop") or "").strip()
        price = _safe_float(item["row"].get("price"))
        if seller: seller_rows[seller].append(price)
    top_sellers = []
    for seller, vals in seller_rows.items():
        priced = [v for v in vals if v is not None]
        top_sellers.append({"seller": seller, "listing_count": len(vals), "avg_price": round(sum(priced)/len(priced),2) if priced else None, "min_price": round(min(priced),2) if priced else None})
    top_sellers.sort(key=lambda x: (-x["listing_count"], x["avg_price"] if x["avg_price"] is not None else float("inf"), x["seller"].lower()))
    currencies = {str(item["row"].get("currency") or "").strip().upper() for item in eligible if str(item["row"].get("currency") or "").strip()}
    return {
        "listing_count": len(eligible), "unique_ids": len(listing_ids), "seller_count": len(sellers), "seller_names": sellers,
        "price_sample": len(prices), "min_price": round(min(prices),2) if prices else None, "max_price": round(max(prices),2) if prices else None,
        "avg_price": round(average,2) if average is not None else None, "median_price": round(_median(prices),2) if prices else None,
        "p25": round(_percentile(prices,.25),2) if prices else None, "p75": round(_percentile(prices,.75),2) if prices else None,
        "std": round(std,2) if std is not None else None, "cv": round((std/average)*100,2) if std is not None and average else None,
        "out_of_stock_count": oos, "out_of_stock_pct": round((oos/len(eligible))*100,2) if eligible else 0.0,
        "related_listing_count": len(items), "whole_product_count": roles[_PD_ROLE_WHOLE], "component_count": roles[_PD_ROLE_COMPONENT],
        "accessory_count": roles[_PD_ROLE_ACCESSORY], "documentation_count": roles[_PD_ROLE_DOC], "irrelevant_count": roles[_PD_ROLE_IRRELEVANT],
        "uncertain_count": roles[_PD_ROLE_UNCERTAIN], "excluded_from_market_analytics_count": len(items)-len(eligible),
        "currency": next(iter(currencies)) if len(currencies)==1 else ("MIXED" if currencies else (currency or "USD")), "top_sellers": top_sellers[:10],
    }


def _pd_audit(item):
    row, cls = item["row"], item["classification"]
    return {"listing_id": row.get("listing_id"), "listing_title": row.get("listing_title"), "listing_url": row.get("listing_url"), "marketplace": row.get("marketplace"), "seller": row.get("seller_or_shop"), "price": row.get("price"), "currency": row.get("currency"), "condition": row.get("condition"), "category": row.get("category_name") or row.get("category"), "status": row.get("listing_status"), "listing_role": cls["listing_role"], "role_confidence": cls["role_confidence"], "role_reasons": cls["role_reasons"], "eligible_for_market_analytics": cls["eligible_for_market_analytics"]}


def _fetch_hqa_dashboard_analysis_product(db, *, keyword, marketplaces, brands, models, conditions, statuses, category_names, buying_options, currency, date_from, date_to, min_price, max_price, group_by="product", granularity="month", price_drop_warning_pct=20.0, price_drop_critical_pct=30.0, out_of_stock_warning_points=30.0, out_of_stock_critical_points=50.0):
    if str(granularity or "month").lower() != "month": raise ValueError("product dashboard currently supports granularity=month")
    statement = _build_dashboard_rows_statement(keyword=None, marketplaces=marketplaces, brands=brands, models=models, statuses=statuses, category_names=category_names, buying_options=buying_options, sellers=None, currency=currency, date_from=date_from, date_to=date_to, min_price=min_price, max_price=max_price)
    statement = _normalized_text_in_values_filter(statement, listing_table.c["condition"], conditions)
    rows = [dict(row) for row in db.execute(statement.with_only_columns(listing_table.c.id, listing_table.c.research_date, listing_table.c.marketplace, listing_table.c.listing_id, listing_table.c.listing_title, listing_table.c.listing_url, listing_table.c.seller_or_shop, listing_table.c.price, listing_table.c.currency, listing_table.c.quantity, listing_table.c.listing_status, listing_table.c.brand, listing_table.c.model, listing_table.c["condition"], listing_table.c.category, listing_table.c.category_name, listing_table.c.buying_options, listing_table.c.exclude_flag).order_by(listing_table.c.research_date.asc(), listing_table.c.id.asc())).mappings().all()]
    linked=[]; products={}
    for row in rows:
        if not row.get("research_date"): continue
        product=_pd_identity(row)
        if not product: continue
        hay=" ".join(str(product.get(k) or "") for k in ("product_key","product_id","product_label","keyword","brand","model","product_type")).casefold()
        if keyword and str(keyword).strip().casefold() not in hay: continue
        products.setdefault(product["product_key"], product); linked.append({"row":row,"product":product})
    by_product=defaultdict(list)
    for item in linked: by_product[item["product"]["product_key"]].append(item)
    classified=[]
    for key, items in by_product.items():
        provisional=[]
        for item in items:
            c=_pd_classify(item["row"], item["product"])
            p=_safe_float(item["row"].get("price"))
            if c["listing_role"]==_PD_ROLE_WHOLE and c["role_confidence"]>=75 and p is not None: provisional.append(p)
        ref=_median(provisional) if provisional else None
        for item in items: classified.append({**item,"classification":_pd_classify(item["row"],item["product"],ref)})
    buckets=defaultdict(list); global_buckets=defaultdict(list)
    for item in classified:
        period=item["row"]["research_date"].strftime("%Y-%m"); key=item["product"]["product_key"]
        buckets[(key,period)].append(item); global_buckets[period].append(item)
    periods=sorted(global_buckets); internal={}; group_periods=[]
    for key, product in products.items():
        prior=set()
        for period in periods:
            items=buckets.get((key,period));
            if not items: continue
            stats=_pd_finalize(items,currency); sellers=set(stats.pop("seller_names")); new=sorted(sellers-prior,key=str.lower); prior|=sellers
            stats.update(product); stats.update({"group":key,"period":period,"new_seller_count":len(new),"new_sellers":new[:10]}); internal[(key,period)]={**stats,"seller_names":sellers}; group_periods.append(stats)
    latest=periods[-1] if periods else None; previous=periods[-2] if len(periods)>1 else None
    latest_summary=None
    if latest:
        latest_summary=_pd_finalize(global_buckets[latest],currency); latest_summary.pop("seller_names",None); latest_summary["period"]=latest
        latest_summary["product_count"]=sum(1 for key in products if internal.get((key,latest),{}).get("listing_count",0)>0)
        latest_summary["uncertain_pct"]=round((latest_summary["uncertain_count"]/max(latest_summary["related_listing_count"],1))*100,2)
    options=[]
    for key,p in products.items():
        own=[period for period in periods if (key,period) in internal]; current=internal.get((key,latest),{}) if latest else {}
        if not current and own: current=internal[(key,own[-1])]
        options.append({**p,"listing_count":int(current.get("listing_count") or 0),"seller_count":int(current.get("seller_count") or 0),"related_listing_count":int(current.get("related_listing_count") or 0),"excluded_count":int(current.get("excluded_from_market_analytics_count") or 0)})
    options.sort(key=lambda x:(-x["listing_count"],x["product_label"].lower(),x["product_key"]))
    alerts=[]; rank={"critical":3,"warning":2,"info":1}
    for key,p in products.items():
        cur=internal.get((key,latest)) if latest else None; prev=internal.get((key,previous)) if previous else None
        if not cur or not cur.get("listing_count"): continue
        base={"group":key,"product_key":key,"product_label":p["product_label"],"period":latest,"currency":cur.get("currency","USD")}
        if prev and cur.get("avg_price") is not None and prev.get("avg_price") not in (None,0):
            drop=((prev["avg_price"]-cur["avg_price"])/prev["avg_price"])*100
            if drop>=price_drop_warning_pct:
                sev="critical" if drop>=price_drop_critical_pct else "warning"; alerts.append({**base,"type":"price_drop","severity":sev,"severity_rank":rank[sev],"title":"Giá giảm mạnh","previous_avg_price":prev["avg_price"],"current_avg_price":cur["avg_price"],"change_percent":round(-drop,2),"message":f"Giá TB giảm {drop:.1f}% so với kỳ trước."})
        hist=[internal[(key,per)].get("min_price") for per in periods if per!=latest and (key,per) in internal and internal[(key,per)].get("min_price") is not None]
        if cur.get("min_price") is not None and hist and cur["min_price"]<min(hist): alerts.append({**base,"type":"new_low","severity":"warning","severity_rank":2,"title":"Đáy giá mới","current_min_price":cur["min_price"],"previous_floor_price":min(hist),"message":"Giá thấp nhất thấp hơn các kỳ trước."})
        if prev and cur.get("new_seller_count",0)>0: alerts.append({**base,"type":"new_seller","severity":"info","severity_rank":1,"title":"Người bán mới","new_seller_count":cur["new_seller_count"],"new_sellers":cur["new_sellers"],"message":f"Có {cur['new_seller_count']} người bán mới."})
        if prev:
            jump=float(cur.get("out_of_stock_pct") or 0)-float(prev.get("out_of_stock_pct") or 0)
            if jump>=out_of_stock_warning_points:
                sev="critical" if jump>=out_of_stock_critical_points else "warning"; alerts.append({**base,"type":"out_of_stock_spike","severity":sev,"severity_rank":rank[sev],"title":"Hết hàng tăng mạnh","previous_out_of_stock_pct":prev.get("out_of_stock_pct",0),"current_out_of_stock_pct":cur.get("out_of_stock_pct",0),"change_points":round(jump,2),"message":f"Tỷ lệ hết hàng tăng {jump:.1f} điểm %."})
    alerts.sort(key=lambda x:(-x["severity_rank"],str(x.get("product_label") or "").lower()))
    drilldown=None
    keys={item["product"]["product_key"] for item in classified}
    if len(keys)==1 and latest:
        key=next(iter(keys)); cur=internal.get((key,latest));
        if cur:
            current={k:v for k,v in cur.items() if k!="seller_names"}; prev=internal.get((key,previous)); prev_public={k:v for k,v in prev.items() if k!="seller_names"} if prev else None
            period_items=[item for item in classified if item["product"]["product_key"]==key and item["row"]["research_date"].strftime("%Y-%m")==latest]
            audit=sorted((_pd_audit(item) for item in period_items),key=lambda x:(x["listing_role"],-x["role_confidence"],str(x.get("listing_title") or "")))
            drilldown={"product":products[key],"period":latest,"current":current,"previous":prev_public,"role_breakdown":{role:sum(1 for item in period_items if item["classification"]["listing_role"]==role) for role in (_PD_ROLE_WHOLE,_PD_ROLE_COMPONENT,_PD_ROLE_ACCESSORY,_PD_ROLE_DOC,_PD_ROLE_IRRELEVANT,_PD_ROLE_UNCERTAIN)},"related_listings_total":len(audit),"related_listings":audit[:250],"related_listings_truncated":len(audit)>250}
    return {"version":"v5-product-analytics","group_by":"product","granularity":"month","periods":periods,"groups":[p["product_key"] for p in options],"products":options,"latest_period":latest_summary,"previous_period":previous,"group_periods":group_periods,"alerts":alerts,"drilldown":drilldown,"meta":{"source_table":"public.marketplace_research_results","classifier_version":"hqa-dashboard-role-v1","market_analytics_scope":"whole_product eligible only","raw_rows_examined":len(rows),"linked_rows":len(linked)}}


_fetch_hqa_dashboard_analysis_legacy = fetch_hqa_dashboard_analysis


def fetch_hqa_dashboard_analysis(*args, **kwargs):
    if str(kwargs.get("group_by") or "model").strip().lower() == "product":
        return _fetch_hqa_dashboard_analysis_product(*args, **kwargs)
    return _fetch_hqa_dashboard_analysis_legacy(*args, **kwargs)
# --- end HQA Dashboard Product Analytics v5 ---
