from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
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
    report_date: date,
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
    statement = _listing_base_select().where(listing_table.c.research_date == report_date)

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
    report_date: date,
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
    rows = db.execute(_apply_raw_sort(statement, sort).offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return [dict(row) for row in rows], total


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


def _build_scope_statement(
    *,
    view: str,
    report_key: str | None,
    report_date: date,
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
    report_date: date,
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

    return {
        "report_date": report_date.isoformat(),
        "view": view,
        "report_key": report_key,
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
