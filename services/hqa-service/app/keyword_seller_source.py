"""Data access layer cho module Keyword -> Seller -> Latest listing.

Repo hien tai ton tai HAI hinh thai luu tru listing:

1. ``public.marketplace_research_results`` (FLAT)
   Bang phang, moi dong = 1 lan quan sat listing trong 1 ``research_date``.
   Toan bo ``service.py`` hien tai doc tu day.

2. ``{ebay,etsy,reverb}.listings`` + ``listing_snapshots`` + ``listing_matches``
   (NORMALIZED) Schema chuan hoa, ``listing_snapshots.observed_at`` chinh la
   price/status history that su, ``listing_matches.keyword`` cho biet listing
   thuoc keyword nao.

Module nay chuan hoa ca hai ve CUNG MOT dang "observation row" de tang analytics
phia tren khong can biet du lieu den tu dau:

    {
      marketplace, seller, listing_id, listing_title, listing_url, image_url,
      published_at, first_seen, observed_date,
      price, currency, listing_status, quantity, listing_views,
      condition, category_name, brand, model, exclude_flag, keyword
    }

Nguon duoc chon theo ``settings.hqa_keyword_seller_source``:
``auto`` (mac dinh) | ``flat`` | ``normalized``.

QUAN TRONG VE KEYWORD MATCH:
- SQL chi dung de lay candidate theo keyword da duoc gan trong DB.
- Quyet dinh listing co thuc su hop le voi keyword hay khong phai di qua
  ``app.listing_matcher.match_listing``.
- Card keyword va man hinh analytics detail cung su dung CHUNG logic matcher,
  tranh tinh trang card co listing nhung click vao lai ve 0.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from statistics import median

from app.listing_matcher import match_listing
from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

SOURCE_FLAT = "flat"
SOURCE_NORMALIZED = "normalized"
SOURCE_NONE = "none"

NORMALIZED_MARKETPLACES = ("ebay", "etsy", "reverb")

# Cot chua ten seller khac nhau giua cac marketplace.
_SELLER_COLUMN = {
    "ebay": "seller_name",
    "etsy": "shop_name",
    "reverb": "shop_name",
}

FLAT_TABLE = ("public", "marketplace_research_results")


# ---------------------------------------------------------------------------
# 1. Do nguon du lieu
# ---------------------------------------------------------------------------


def _existing_tables(db: Session) -> set[tuple[str, str]]:
    rows = db.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE (table_schema = :flat_schema AND table_name = :flat_table)
               OR (
                    table_schema = ANY(:schemas)
                    AND table_name IN (
                        'listings',
                        'listing_snapshots',
                        'listing_matches'
                    )
               )
            """
        ),
        {
            "flat_schema": FLAT_TABLE[0],
            "flat_table": FLAT_TABLE[1],
            "schemas": list(NORMALIZED_MARKETPLACES),
        },
    ).all()

    return {(row[0], row[1]) for row in rows}


def available_normalized_marketplaces(db: Session) -> list[str]:
    """Marketplace co du bo 3 bang de chay duong normalized."""
    tables = _existing_tables(db)
    available: list[str] = []

    for marketplace in NORMALIZED_MARKETPLACES:
        needed = {
            (marketplace, "listings"),
            (marketplace, "listing_snapshots"),
            (marketplace, "listing_matches"),
        }

        if needed.issubset(tables):
            available.append(marketplace)

    return available


def resolve_source(db: Session, preference: str = "auto") -> str:
    """Chon nguon du lieu thuc te dang co tren database.

    ``auto`` uu tien NORMALIZED vi no co snapshot history that su; chi roi ve
    FLAT khi schema chuan hoa chua san sang.
    """
    normalized_preference = (preference or "auto").strip().lower()

    tables = _existing_tables(db)
    has_flat = FLAT_TABLE in tables
    normalized = available_normalized_marketplaces(db)

    if normalized_preference == SOURCE_FLAT:
        return SOURCE_FLAT if has_flat else SOURCE_NONE

    if normalized_preference == SOURCE_NORMALIZED:
        return SOURCE_NORMALIZED if normalized else SOURCE_NONE

    if normalized:
        return SOURCE_NORMALIZED

    if has_flat:
        return SOURCE_FLAT

    return SOURCE_NONE


# ---------------------------------------------------------------------------
# 2. Helper chung
# ---------------------------------------------------------------------------


def _clean(value) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def _as_date(value) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def _as_float(value) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_status(value) -> str:
    normalized = _clean(value).lower()

    if normalized in {
        "active",
        "ended",
        "out_of_stock",
        "new_listing",
    }:
        return normalized.upper()

    if not normalized:
        return "UNKNOWN"

    return normalized.upper()


def _row_matches_keyword(
    row,
    *,
    keyword: str,
) -> bool:
    """Kiem tra listing title bang matcher dung chung.

    Luu y:
    - ``role='all'`` duoc dung co chu dich tai tang source.
      Source chi lam nhiem vu keyword matching, KHONG loai component/accessory
      theo role tai day. Role se tiep tuc duoc xu ly o tang classifier/analytics.
    - Neu row co brand/model thi matcher se check exact brand/model.
    - ``exclude_flag`` trong DB luon duoc ton trong.
    """
    if bool(row.get("exclude_flag")):
        return False

    title = _clean(row.get("listing_title"))
    normalized_keyword = _clean(keyword)

    if not title or not normalized_keyword:
        return False

    brand = _clean(row.get("brand")) or None
    model = _clean(row.get("model")) or None

    try:
        result = match_listing(
            title=title,
            keyword=normalized_keyword,
            brand=brand,
            model=model,
            role="all",
            exclude_keywords=None,
        )
    except Exception:
        logger.exception(
            "listing_matcher failed: keyword=%r title=%r brand=%r model=%r",
            normalized_keyword,
            title,
            brand,
            model,
        )
        return False

    return bool(result.matched)


def _row_to_observation(
    row,
    *,
    marketplace: str,
    keyword: str | None,
) -> dict:
    return {
        "marketplace": _clean(marketplace).lower(),
        "seller": _clean(row.get("seller")),
        "listing_id": _clean(row.get("listing_id")),
        "listing_title": _clean(row.get("listing_title")),
        "listing_url": _clean(row.get("listing_url")),
        "image_url": _clean(row.get("image_url")),
        "published_at": _as_date(row.get("published_at")),
        "first_seen": _as_date(row.get("first_seen")),
        "observed_date": _as_date(row.get("observed_date")),
        "price": _as_float(row.get("price")),
        "currency": _clean(row.get("currency")).upper() or "USD",
        "listing_status": _normalize_status(row.get("listing_status")),
        "quantity": row.get("quantity"),
        "listing_views": row.get("listing_views"),
        "condition": _clean(row.get("condition_name")),
        "category_name": _clean(row.get("category_name")),
        "brand": _clean(row.get("brand")),
        "model": _clean(row.get("model")),
        "exclude_flag": bool(row.get("exclude_flag")),
        "keyword": _clean(row.get("keyword")) or _clean(keyword),
    }


def _build_keyword_option_rows(
    rows,
    *,
    limit: int,
) -> list[dict]:
    """Group candidate rows thanh keyword options sau khi da qua matcher.

    Seller/listing count dung DISTINCT.
    Median price giu semantics gan voi SQL cu: tinh tren cac observation
    hop le trong khoang thoi gian duoc chon.
    """
    grouped: dict[str, dict] = {}

    for row in rows:
        keyword = _clean(row.get("keyword"))

        if not keyword:
            continue

        if not _row_matches_keyword(row, keyword=keyword):
            continue

        seller = _clean(row.get("seller"))
        listing_id = _clean(row.get("listing_id"))
        price = _as_float(row.get("price"))

        bucket = grouped.setdefault(
            keyword,
            {
                "sellers": set(),
                "listings": set(),
                "prices": [],
            },
        )

        if seller:
            bucket["sellers"].add(seller)

        if listing_id:
            bucket["listings"].add(listing_id)

        if price is not None:
            bucket["prices"].append(price)

    result: list[dict] = []

    for keyword, bucket in grouped.items():
        listing_count = len(bucket["listings"])

        if listing_count <= 0:
            continue

        prices = bucket["prices"]

        result.append(
            {
                "keyword": keyword,
                "seller_count": len(bucket["sellers"]),
                "listing_count": listing_count,
                "median_price": median(prices) if prices else None,
            }
        )

    result.sort(
        key=lambda item: (
            -item["listing_count"],
            item["keyword"].lower(),
        )
    )

    return result[: max(0, limit)]


# ---------------------------------------------------------------------------
# 3. Duong NORMALIZED:
#    {mp}.listings + listing_snapshots + listing_matches
# ---------------------------------------------------------------------------


def _normalized_observation_sql(marketplace: str) -> str:
    seller_column = _SELLER_COLUMN.get(
        marketplace,
        "shop_name",
    )

    return f"""
        SELECT
            '{marketplace}' AS marketplace,
            l.{seller_column} AS seller,
            l.external_listing_id AS listing_id,
            l.listing_title AS listing_title,
            l.listing_url AS listing_url,
            l.image_url AS image_url,
            l.published_at AS published_at,
            l.first_seen_at AS first_seen,
            COALESCE(
                s.observed_at,
                l.last_seen_at
            ) AS observed_date,
            COALESCE(
                s.price,
                l.current_price
            ) AS price,
            COALESCE(
                s.currency,
                l.currency
            ) AS currency,
            COALESCE(
                s.listing_status,
                l.listing_status
            ) AS listing_status,
            COALESCE(
                s.quantity,
                0
            ) AS quantity,
            COALESCE(
                s.listing_views,
                l.listing_views
            ) AS listing_views,
            l.condition_name AS condition_name,
            l.category_name AS category_name,
            NULL::text AS brand,
            NULL::text AS model,
            m.exclude_flag AS exclude_flag,
            m.keyword AS keyword
        FROM {marketplace}.listings l
        JOIN {marketplace}.listing_matches m
          ON m.listing_id = l.id
        LEFT JOIN {marketplace}.listing_snapshots s
          ON s.listing_id = l.id
        WHERE lower(btrim(m.keyword)) = :keyword
          AND COALESCE(m.exclude_flag, false) = false
    """


def _fetch_normalized(
    db: Session,
    *,
    keyword: str,
    marketplaces: list[str] | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    targets = available_normalized_marketplaces(db)

    if marketplaces:
        wanted = {
            m.strip().lower()
            for m in marketplaces
            if m and m.strip()
        }

        targets = [
            marketplace
            for marketplace in targets
            if marketplace in wanted
        ]

    if not targets:
        return []

    union_sql = "\nUNION ALL\n".join(
        _normalized_observation_sql(marketplace)
        for marketplace in targets
    )

    sql = f"""
        SELECT *
        FROM (
            {union_sql}
        ) AS observations
        WHERE 1 = 1
    """

    params: dict = {
        "keyword": keyword.strip().lower(),
    }

    if date_from:
        sql += """
            AND observed_date >= :date_from
        """
        params["date_from"] = date_from

    if date_to:
        sql += """
            AND observed_date < (
                CAST(:date_to AS date) + INTEGER '1'
            )
        """
        params["date_to"] = date_to

    sql += """
        ORDER BY observed_date ASC
    """

    rows = db.execute(
        text(sql),
        params,
    ).mappings().all()

    matched_rows = [
        row
        for row in rows
        if _row_matches_keyword(
            row,
            keyword=keyword,
        )
    ]

    logger.debug(
        "normalized keyword=%r candidates=%d matched=%d",
        keyword,
        len(rows),
        len(matched_rows),
    )

    return [
        _row_to_observation(
            row,
            marketplace=row.get("marketplace"),
            keyword=keyword,
        )
        for row in matched_rows
    ]


def _fetch_normalized_keywords(
    db: Session,
    *,
    marketplaces: list[str] | None,
    date_from: date | None,
    date_to: date | None,
    min_price: float,
    limit: int,
) -> list[dict]:
    """Danh sach keyword cho selector bang CUNG matcher voi detail.

    Khac ban cu:
    - Ban cu aggregate SQL truc tiep tren ``listing_matches``.
    - Ban nay lay candidate rows, chay ``listing_matcher``, roi moi dem.
    => Card va detail khong con dung hai logic match khac nhau.
    """
    targets = available_normalized_marketplaces(db)

    if marketplaces:
        wanted = {
            m.strip().lower()
            for m in marketplaces
            if m and m.strip()
        }

        targets = [
            marketplace
            for marketplace in targets
            if marketplace in wanted
        ]

    if not targets:
        return []

    parts: list[str] = []

    for marketplace in targets:
        seller_column = _SELLER_COLUMN.get(
            marketplace,
            "shop_name",
        )

        parts.append(
            f"""
            SELECT
                btrim(m.keyword) AS keyword,
                l.{seller_column} AS seller,
                l.external_listing_id AS listing_id,
                l.listing_title AS listing_title,
                l.current_price AS price,
                l.last_seen_at AS observed_date,
                NULL::text AS brand,
                NULL::text AS model,
                COALESCE(m.exclude_flag, false) AS exclude_flag
            FROM {marketplace}.listings l
            JOIN {marketplace}.listing_matches m
              ON m.listing_id = l.id
            WHERE COALESCE(m.exclude_flag, false) = false
              AND btrim(COALESCE(m.keyword, '')) <> ''
            """
        )

    union_sql = "\nUNION ALL\n".join(parts)

    sql = f"""
        SELECT *
        FROM (
            {union_sql}
        ) AS base
        WHERE price IS NOT NULL
          AND price > :min_price
          AND btrim(COALESCE(seller, '')) <> ''
    """

    params: dict = {
        "min_price": min_price,
    }

    if date_from:
        sql += """
            AND observed_date >= :date_from
        """
        params["date_from"] = date_from

    if date_to:
        sql += """
            AND observed_date < (
                CAST(:date_to AS date) + INTEGER '1'
            )
        """
        params["date_to"] = date_to

    rows = db.execute(
        text(sql),
        params,
    ).mappings().all()

    return _build_keyword_option_rows(
        rows,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# 4. Duong FLAT: public.marketplace_research_results
# ---------------------------------------------------------------------------


_FLAT_SELECT = """
    SELECT
        lower(
            btrim(
                COALESCE(r.marketplace, '')
            )
        ) AS marketplace,
        r.seller_or_shop AS seller,
        r.listing_id AS listing_id,
        r.listing_title AS listing_title,
        r.listing_url AS listing_url,
        r.image_url AS image_url,
        r.listing_published_at AS published_at,
        r.research_date AS observed_date,
        r.price AS price,
        r.currency AS currency,
        r.listing_status AS listing_status,
        COALESCE(
            r.quantity,
            r.count,
            0
        ) AS quantity,
        r.listing_views AS listing_views,
        r.condition AS condition_name,
        r.category_name AS category_name,
        r.brand AS brand,
        r.model AS model,
        r.keyword AS keyword,
        COALESCE(
            r.exclude_flag,
            false
        ) AS exclude_flag
    FROM public.marketplace_research_results r
"""


def _fetch_flat(
    db: Session,
    *,
    keyword: str,
    marketplaces: list[str] | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    sql = _FLAT_SELECT + """
        WHERE lower(
            btrim(
                COALESCE(r.keyword, '')
            )
        ) = :keyword
          AND btrim(
                COALESCE(r.seller_or_shop, '')
              ) <> ''
          AND r.research_date IS NOT NULL
          AND COALESCE(r.exclude_flag, false) = false
    """

    # SQL dung :keyword nen params bat buoc co "keyword".
    params: dict = {
        "keyword": keyword.strip().lower(),
    }

    if marketplaces:
        cleaned = [
            marketplace.strip().lower()
            for marketplace in marketplaces
            if marketplace and marketplace.strip()
        ]

        if cleaned:
            sql += """
                AND lower(
                    btrim(
                        COALESCE(r.marketplace, '')
                    )
                ) = ANY(:marketplaces)
            """
            params["marketplaces"] = cleaned

    if date_from:
        sql += """
            AND r.research_date >= :date_from
        """
        params["date_from"] = date_from

    if date_to:
        sql += """
            AND r.research_date <= :date_to
        """
        params["date_to"] = date_to

    sql += """
        ORDER BY
            r.research_date ASC,
            r.collected_at ASC NULLS LAST,
            r.updated_at ASC NULLS LAST
    """

    rows = db.execute(
        text(sql),
        params,
    ).mappings().all()

    # QUAN TRONG:
    # Khong dung strict contiguous phrase nua.
    # VD keyword "JBL 4311 speaker" phai match title "JBL 4311 speakers".
    matched_rows = [
        row
        for row in rows
        if _row_matches_keyword(
            row,
            keyword=keyword,
        )
    ]

    logger.debug(
        "flat keyword=%r candidates=%d matched=%d",
        keyword,
        len(rows),
        len(matched_rows),
    )

    # Suy ra first_seen tu lan xuat hien dau tien cua listing
    # TRONG tap matched rows.
    first_seen: dict[tuple[str, str], date] = {}

    for row in matched_rows:
        key = (
            _clean(row.get("marketplace")).lower(),
            _clean(row.get("listing_id")),
        )

        observed = _as_date(
            row.get("observed_date")
        )

        if observed is None:
            continue

        if (
            key not in first_seen
            or observed < first_seen[key]
        ):
            first_seen[key] = observed

    observations: list[dict] = []

    for row in matched_rows:
        payload = dict(row)

        key = (
            _clean(row.get("marketplace")).lower(),
            _clean(row.get("listing_id")),
        )

        payload["first_seen"] = first_seen.get(key)

        observations.append(
            _row_to_observation(
                payload,
                marketplace=row.get("marketplace"),
                keyword=keyword,
            )
        )

    return observations


def _fetch_flat_keywords(
    db: Session,
    *,
    marketplaces: list[str] | None,
    date_from: date | None,
    date_to: date | None,
    min_price: float,
    limit: int,
) -> list[dict]:
    """Danh sach keyword FLAT cho selector bang CUNG matcher voi detail.

    Day la thay doi quan trong de tranh:
        Card: 3 listings
        Click detail: 0 listings

    SQL chi lay candidate theo date/marketplace/price.
    Python matcher moi quyet dinh listing title co hop keyword hay khong.
    """
    sql = """
        SELECT
            btrim(r.keyword) AS keyword,
            r.seller_or_shop AS seller,
            r.listing_id AS listing_id,
            r.listing_title AS listing_title,
            r.price AS price,
            r.research_date AS observed_date,
            r.brand AS brand,
            r.model AS model,
            COALESCE(
                r.exclude_flag,
                false
            ) AS exclude_flag
        FROM public.marketplace_research_results r
        WHERE r.keyword IS NOT NULL
          AND btrim(r.keyword) <> ''
          AND r.price IS NOT NULL
          AND r.price > :min_price
          AND btrim(
                COALESCE(r.seller_or_shop, '')
              ) <> ''
          AND COALESCE(r.exclude_flag, false) = false
    """

    params: dict = {
        "min_price": min_price,
    }

    if marketplaces:
        cleaned = [
            marketplace.strip().lower()
            for marketplace in marketplaces
            if marketplace and marketplace.strip()
        ]

        if cleaned:
            sql += """
                AND lower(
                    btrim(
                        COALESCE(r.marketplace, '')
                    )
                ) = ANY(:marketplaces)
            """
            params["marketplaces"] = cleaned

    if date_from:
        sql += """
            AND r.research_date >= :date_from
        """
        params["date_from"] = date_from

    if date_to:
        sql += """
            AND r.research_date <= :date_to
        """
        params["date_to"] = date_to

    rows = db.execute(
        text(sql),
        params,
    ).mappings().all()

    return _build_keyword_option_rows(
        rows,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# 5. API cong khai cua module
# ---------------------------------------------------------------------------


def fetch_keyword_observations(
    db: Session,
    *,
    keyword: str,
    source: str,
    marketplaces: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Tra ve toan bo observation cua 1 keyword, da chuan hoa va match title."""
    if not keyword or not keyword.strip():
        return []

    if source == SOURCE_NORMALIZED:
        return _fetch_normalized(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
        )

    if source == SOURCE_FLAT:
        return _fetch_flat(
            db,
            keyword=keyword,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
        )

    return []


def fetch_keyword_options(
    db: Session,
    *,
    source: str,
    marketplaces: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_price: float = 500.0,
    limit: int = 200,
) -> list[dict]:
    """Danh sach keyword cho selector, kem seller/listing/median.

    Card keyword va detail deu di qua ``listing_matcher`` de giu cung mot
    definition cua "listing hop keyword".
    """
    if source == SOURCE_NORMALIZED:
        return _fetch_normalized_keywords(
            db,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            limit=limit,
        )

    if source == SOURCE_FLAT:
        return _fetch_flat_keywords(
            db,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            limit=limit,
        )

    return []
