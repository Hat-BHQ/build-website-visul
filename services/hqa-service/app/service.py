from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import json
import re
from sqlalchemy import and_, case, func, literal, literal_column, not_, or_, select
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


def _apply_all_listings_sort(statement, sort_collected: str):
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
    rows = db.execute(_apply_all_listings_sort(statement, sort_collected).offset(offset).limit(page_size)).mappings().all()
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
    row = db.execute(
        select(
            func.count().label("filtered_records"),
            func.count(func.distinct(func.nullif(func.trim(scope.c.listing_id), literal_column("''")))).label("unique_listing_ids"),
            func.coalesce(func.sum(case((status_expr == "active", 1), else_=0)), 0).label("active"),
            func.coalesce(func.sum(case((status_expr.in_(["ended", "end"]), 1), else_=0)), 0).label("ended"),
            func.coalesce(func.sum(case((status_expr == "out_of_stock", 1), else_=0)), 0).label("out_of_stock"),
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
    row = db.execute(
        select(
            func.count(func.distinct(func.nullif(seller_expr, ""))).label("total_sellers"),
            func.coalesce(func.sum(case((status_expr == "active", 1), else_=0)), 0).label("active_listings"),
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
        "active_listings": _safe_int(row.get("active_listings")),
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
    return {
        "granularity": normalized_granularity,
        "points": [
            {
                "period": row.get("period") or "unknown",
                "seller_count": _safe_int(row.get("seller_count")),
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
            if drop_pct >= price_drop_threshold_pct:
                alerts.append(
                    {
                        "type": "price_drop",
                        "severity": "high",
                        "period": current.get("period"),
                        "value": round(drop_pct, 2),
                        "message": f"Average price dropped {drop_pct:.2f}% versus previous period",
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
    min_sample_for_price_alert: int,
    new_seller_lookback_days: int,
    out_of_stock_min_count: int,
    out_of_stock_alert_percent: float,
) -> list[dict]:
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
            )
        ]
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
            min_sample_for_price_alert=min_sample_for_price_alert,
            new_seller_lookback_days=new_seller_lookback_days,
            out_of_stock_min_count=out_of_stock_min_count,
            out_of_stock_alert_percent=out_of_stock_alert_percent,
        )["alerts"]
    raise ValueError("Invalid dataset")
