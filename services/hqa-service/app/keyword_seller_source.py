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
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median

from app.listing_matcher import (
    FILTER_MODE_BRAND_MODEL,
    FILTER_MODE_KEYWORD,
    FILTER_MODES,
    PLURALIZABLE_PRODUCT_TERMS,
    alnum_runs,
    keyword_phrase_variants,
    match_keyword_strict,
    match_listing_by_mode,
    normalize_text,
)
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


# ---------------------------------------------------------------------------
# 2b. Filter scope (2 mode loai tru nhau)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilterScope:
    """Pham vi loc cua dashboard tai MOT thoi diem.

    Chi mot trong hai nhom gia tri duoc mang y nghia:
    - ``brand`` / ``model`` khi ``filter_mode == "brand_model"``
    - ``keyword``           khi ``filter_mode == "keyword"``

    ``build_scope`` da xoa sach gia tri cua mode con lai nen khong the co
    "hidden stale filter" ro ri xuong SQL.
    """

    filter_mode: str
    brand: str = ""
    model: str = ""
    keyword: str = ""
    condition: str = ""

    @property
    def is_brand_model(self) -> bool:
        return self.filter_mode == FILTER_MODE_BRAND_MODEL

    @property
    def is_keyword(self) -> bool:
        return self.filter_mode == FILTER_MODE_KEYWORD

    @property
    def label(self) -> str:
        """Nhan hien thi cho card / CSV / tieu de."""
        if self.is_keyword:
            return self.keyword
        return " ".join(part for part in (self.brand, self.model) if part)


def build_scope(
    *,
    filter_mode: str | None,
    brand: str | None = None,
    model: str | None = None,
    keyword: str | None = None,
    condition: str | None = None,
) -> FilterScope:
    """Chuan hoa + validate scope. Raise ``ValueError`` neu khong hop le."""
    mode = _clean(filter_mode).lower() or FILTER_MODE_BRAND_MODEL

    if mode not in FILTER_MODES:
        raise ValueError(
            f"filter_mode phai la mot trong {list(FILTER_MODES)}"
        )

    normalized_condition = _clean(condition)

    if mode == FILTER_MODE_BRAND_MODEL:
        normalized_brand = _clean(brand)
        normalized_model = _clean(model)

        if not normalized_brand and not normalized_model:
            raise ValueError(
                "Mode brand_model yeu cau it nhat mot trong brand hoac model."
            )

        # Keyword cua mode kia bi xoa hoan toan.
        return FilterScope(
            filter_mode=mode,
            brand=normalized_brand,
            model=normalized_model,
            keyword="",
            condition=normalized_condition,
        )

    normalized_keyword = _clean(keyword)

    if not normalized_keyword:
        raise ValueError("Mode keyword yeu cau keyword.")

    # Brand/Model cua mode kia bi xoa hoan toan.
    return FilterScope(
        filter_mode=mode,
        brand="",
        model="",
        keyword=normalized_keyword,
        condition=normalized_condition,
    )


def _row_matches_scope(
    row,
    scope: FilterScope,
) -> bool:
    """Quyet dinh cuoi cung: listing title co thuoc scope hay khong.

    SQL chi lam nhiem vu thu hep candidate. Ham nay moi la nguon su that:
    - Mode A -> ``match_brand_model_title`` (boundary phrase).
    - Mode B -> ``match_keyword_strict``    (equality + plural cho phep).

    ``exclude_flag`` trong DB luon duoc ton trong.
    """
    if bool(row.get("exclude_flag")):
        return False

    title = _clean(row.get("listing_title"))

    if not title:
        return False

    try:
        return bool(
            match_listing_by_mode(
                title=title,
                filter_mode=scope.filter_mode,
                brand=scope.brand or None,
                model=scope.model or None,
                keyword=scope.keyword or None,
            )
        )
    except Exception:
        logger.exception(
            "listing_matcher failed: scope=%r title=%r",
            scope,
            title,
        )
        return False


def _row_matches_keyword(
    row,
    *,
    keyword: str,
) -> bool:
    """Backward-compatible wrapper: mode keyword STRICT."""
    normalized_keyword = _clean(keyword)

    if not normalized_keyword:
        return False

    return _row_matches_scope(
        row,
        FilterScope(
            filter_mode=FILTER_MODE_KEYWORD,
            keyword=normalized_keyword,
        ),
    )


# ---------------------------------------------------------------------------
# 2c. SQL prefilter cua scope
# ---------------------------------------------------------------------------
#
# QUAN TRONG: SQL o day chi de GIAM CANDIDATE.
# Moi predicate phai la SIEU TAP (superset) cua ket qua matcher that su,
# neu khong se loai nham listing hop le truoc khi matcher kip chay.


def _scope_title_tokens(scope: FilterScope) -> list[str]:
    """Token bat buoc xuat hien trong title, dung cho ILIKE prefilter.

    - Mode A: token cua brand + token cua model.
    - Mode B: token cua keyword, final product noun duoc dua ve dang so it
      de ILIKE bat duoc ca "speaker" lan "speakers".
    """
    if scope.is_brand_model:
        source_terms = [scope.brand, scope.model]
    else:
        source_terms = [scope.keyword]

    tokens: list[str] = []

    for term in source_terms:
        normalized = normalize_text(term)

        if not normalized:
            continue

        tokens.extend(normalized.split())

    if not tokens:
        return []

    # Chi ha "s" o token CUOI CUNG va chi khi no la product noun.
    last = tokens[-1]
    singular = last[:-1] if last.endswith("s") else last

    if singular in PLURALIZABLE_PRODUCT_TERMS:
        tokens[-1] = singular

    # QUAN TRONG: tach tiep thanh cac cum chu/so.
    # Keyword "GX4000D" phai bat duoc title "Akai GX-4000D", nen KHONG duoc
    # ILIKE '%gx4000d%' (title co dau gach o giua). Tach thanh 'gx' + '4000'
    # thi predicate van la superset cua matcher va khong loai nham.
    runs: list[str] = []

    for token in tokens:
        # Bo run 1 ky tu: gan nhu khong loc duoc gi ma lai ton chi phi.
        # Bo bot predicate chi lam tap ket qua RONG hon -> van la superset.
        runs.extend(
            run for run in alnum_runs(token) if len(run) >= 2
        )

    # Bo trung lap, giu thu tu.
    return list(dict.fromkeys(run for run in runs if run))


def _scope_sql_filter(
    scope: FilterScope,
    *,
    title_column: str,
    condition_column: str | None,
    params: dict,
) -> str:
    """Sinh doan SQL prefilter cho scope va nap params tuong ung."""
    fragments: list[str] = []

    for index, token in enumerate(_scope_title_tokens(scope)):
        placeholder = f"scope_token_{index}"
        fragments.append(
            f"""
            AND {title_column} ILIKE :{placeholder}
            """
        )
        params[placeholder] = f"%{token}%"

    if scope.condition and condition_column:
        fragments.append(
            f"""
            AND lower(
                btrim(
                    COALESCE({condition_column}, '')
                )
            ) = :scope_condition
            """
        )
        params["scope_condition"] = scope.condition.lower()

    return "".join(fragments)


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


def _keyword_vocabulary(rows) -> list[str]:
    """Danh sach keyword co that tren DB, lay tu chinh cot ``keyword``."""
    vocabulary: list[str] = []
    seen: set[str] = set()

    for row in rows:
        keyword = _clean(row.get("keyword"))

        if not keyword:
            continue

        key = keyword.lower()

        if key in seen:
            continue

        seen.add(key)
        vocabulary.append(keyword)

    return vocabulary


def _keyword_first_token_index(vocabulary: list[str]) -> dict[str, list[str]]:
    """Index keyword theo token DAU TIEN cua tung variant.

    Mot title chi co the chua cum keyword neu no chua token dau tien cua cum,
    nen index nay cho phep bo qua phan lon keyword ma khong doi ket qua.
    Nho vay khong phai chay matcher cho moi cap (row x keyword).
    """
    index: dict[str, list[str]] = {}

    for keyword in vocabulary:
        for variant in keyword_phrase_variants(keyword):
            variant_runs = alnum_runs(variant)

            if not variant_runs:
                continue

            # Index theo RUN dau tien (khong phai tu dau tien), de keyword
            # "GX4000D" va title "GX-4000D" cung roi vao khoa "gx".
            first_run = variant_runs[0]

            bucket = index.setdefault(first_run, [])

            if keyword not in bucket:
                bucket.append(keyword)

    return index


def _build_keyword_option_rows(
    rows,
    *,
    limit: int,
) -> list[dict]:
    """Group candidate rows thanh keyword options sau khi da qua matcher.

    QUAN TRONG (prompt muc XXIV):
    Card KHONG duoc gom theo cot ``keyword`` cua tung row, vi cot do co the
    thieu hoac lech so voi title. Neu gom theo cot, card se dem it hon detail
    (detail match theo title) va sinh ra dung loi "card 6 / detail 7".

    Vi vay:
    - Vocabulary keyword lay tu cot ``keyword`` (nguon keyword co that tren DB).
    - Nhung viec MOT ROW co thuoc keyword nao lai do ``match_keyword_strict``
      tren TITLE quyet dinh, y het detail.

    Seller/listing count dung DISTINCT.
    """
    rows = list(rows)
    vocabulary = _keyword_vocabulary(rows)

    if not vocabulary:
        return []

    index = _keyword_first_token_index(vocabulary)
    grouped: dict[str, dict] = {}

    for row in rows:
        if bool(row.get("exclude_flag")):
            continue

        normalized_title = normalize_text(_clean(row.get("listing_title")))

        if not normalized_title:
            continue

        candidates: list[str] = []
        seen_candidates: set[str] = set()

        for token in set(alnum_runs(normalized_title)):
            for keyword in index.get(token, ()):
                key = keyword.lower()
                if key in seen_candidates:
                    continue
                seen_candidates.add(key)
                candidates.append(keyword)

        matched_keywords = [
            keyword
            for keyword in candidates
            if match_keyword_strict(normalized_title, keyword)
        ]

        if not matched_keywords:
            continue

        seller = _clean(row.get("seller"))
        listing_id = _clean(row.get("listing_id"))
        price = _as_float(row.get("price"))

        for keyword in matched_keywords:
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


def _normalized_observation_sql(
    marketplace: str,
    scope: FilterScope,
    params: dict,
) -> str:
    seller_column = _SELLER_COLUMN.get(
        marketplace,
        "shop_name",
    )

    scope_filter = _scope_sql_filter(
        scope,
        title_column="l.listing_title",
        condition_column="l.condition_name",
        params=params,
    )

    # CO Y KHONG loc theo ``m.keyword``: mapping keyword trong DB co the thieu
    # hoac lech, trong khi title van hop le. Token ILIKE o tren da du hep va
    # chac chan la superset cua ket qua matcher.
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
        WHERE COALESCE(m.exclude_flag, false) = false
        {scope_filter}
    """


def _fetch_normalized(
    db: Session,
    *,
    scope: FilterScope,
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

    params: dict = {}

    union_sql = "\nUNION ALL\n".join(
        _normalized_observation_sql(marketplace, scope, params)
        for marketplace in targets
    )

    sql = f"""
        SELECT *
        FROM (
            {union_sql}
        ) AS observations
        WHERE 1 = 1
    """

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
        if _row_matches_scope(row, scope)
    ]

    logger.debug(
        "normalized scope=%r candidates=%d matched=%d",
        scope,
        len(rows),
        len(matched_rows),
    )

    return [
        _row_to_observation(
            row,
            marketplace=row.get("marketplace"),
            keyword=scope.keyword or None,
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
    condition: str = "",
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
                l.condition_name AS condition_name,
                NULL::text AS brand,
                NULL::text AS model,
                COALESCE(m.exclude_flag, false) AS exclude_flag
            FROM {marketplace}.listings l
            JOIN {marketplace}.listing_matches m
              ON m.listing_id = l.id
            WHERE COALESCE(m.exclude_flag, false) = false
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

    if condition:
        sql += """
            AND lower(
                btrim(
                    COALESCE(condition_name, '')
                )
            ) = :condition
        """
        params["condition"] = condition.strip().lower()

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
    scope: FilterScope,
    marketplaces: list[str] | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    params: dict = {}

    sql = _FLAT_SELECT + """
        WHERE btrim(
                COALESCE(r.seller_or_shop, '')
              ) <> ''
          AND r.research_date IS NOT NULL
          AND COALESCE(r.exclude_flag, false) = false
    """

    # CO Y KHONG loc theo ``r.keyword``: mode A khong co keyword, va o mode B
    # cot keyword co the thieu/lech trong khi title van hop le.
    sql += _scope_sql_filter(
        scope,
        title_column="r.listing_title",
        condition_column='r."condition"',
        params=params,
    )

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

    # Quyet dinh cuoi cung luon do matcher, khong phai SQL.
    matched_rows = [
        row
        for row in rows
        if _row_matches_scope(row, scope)
    ]

    logger.debug(
        "flat scope=%r candidates=%d matched=%d",
        scope,
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
                keyword=scope.keyword or None,
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
    condition: str = "",
) -> list[dict]:
    """Danh sach keyword FLAT cho selector bang CUNG matcher voi detail.

    Day la thay doi quan trong de tranh lech card <-> detail.

    CO Y KHONG dat dieu kien ``r.keyword IS NOT NULL`` trong SQL:
    - Cot ``keyword`` chi dung de sinh VOCABULARY keyword co that tren DB.
    - Con viec mot row co thuoc keyword nao thi do matcher tren TITLE quyet
      dinh, giong het detail. Neu chan row co keyword NULL o SQL thi card se
      dem thieu so voi detail (loi "card 6 / detail 7").

    SQL chi lay candidate theo date/marketplace/price/condition.
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
        WHERE r.price IS NOT NULL
          AND r.price > :min_price
          AND btrim(
                COALESCE(r.seller_or_shop, '')
              ) <> ''
          AND COALESCE(r.exclude_flag, false) = false
    """

    params: dict = {
        "min_price": min_price,
    }

    if condition:
        sql += """
            AND lower(
                btrim(
                    COALESCE(r."condition", '')
                )
            ) = :condition
        """
        params["condition"] = condition.strip().lower()

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


def fetch_scope_observations(
    db: Session,
    *,
    scope: FilterScope,
    source: str,
    marketplaces: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Toan bo observation thuoc scope, da chuan hoa va da qua matcher."""
    if source == SOURCE_NORMALIZED:
        return _fetch_normalized(
            db,
            scope=scope,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
        )

    if source == SOURCE_FLAT:
        return _fetch_flat(
            db,
            scope=scope,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
        )

    return []


def fetch_keyword_observations(
    db: Session,
    *,
    keyword: str,
    source: str,
    marketplaces: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    condition: str | None = None,
) -> list[dict]:
    """Backward-compatible wrapper cho mode keyword."""
    if not keyword or not keyword.strip():
        return []

    return fetch_scope_observations(
        db,
        scope=build_scope(
            filter_mode=FILTER_MODE_KEYWORD,
            keyword=keyword,
            condition=condition,
        ),
        source=source,
        marketplaces=marketplaces,
        date_from=date_from,
        date_to=date_to,
    )


def fetch_keyword_options(
    db: Session,
    *,
    source: str,
    marketplaces: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_price: float = 500.0,
    limit: int = 200,
    condition: str | None = None,
) -> list[dict]:
    """Danh sach keyword cho selector/card, kem seller/listing/median.

    Card keyword va detail deu di qua ``listing_matcher`` (mode keyword) nen
    giu CHUNG mot definition cua "listing hop keyword".
    """
    normalized_condition = _clean(condition)

    if source == SOURCE_NORMALIZED:
        return _fetch_normalized_keywords(
            db,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            limit=limit,
            condition=normalized_condition,
        )

    if source == SOURCE_FLAT:
        return _fetch_flat_keywords(
            db,
            marketplaces=marketplaces,
            date_from=date_from,
            date_to=date_to,
            min_price=min_price,
            limit=limit,
            condition=normalized_condition,
        )

    return []
