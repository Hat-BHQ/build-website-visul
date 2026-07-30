from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

EXPECTED_RAW_KEYWORD_ROWS = 179
KEYWORD_SOURCE_FILE = "hqa_keywords.csv"
REQUIRED_COLUMNS = {"product_id", "category", "keyword", "exclude_keywords"}


@dataclass(frozen=True)
class KeywordEntry:
    product_id: str
    brand: str
    model: str
    category: str
    keyword: str
    normalized_brand: str
    normalized_model: str
    normalized_keyword: str
    match_strategy: str
    broad_only: bool
    usable: bool


def normalize_match_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _tokens(value: str | None) -> list[str]:
    return [part for part in re.split(r"[^a-z0-9]+", (value or "").strip().lower()) if part]


def _dedupe_preserve_case(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


def _entry_from_row(row: dict[str, str]) -> KeywordEntry | None:
    product_id = (row.get("product_id") or "").strip()
    category = _normalize(row.get("category"))
    keyword = (row.get("keyword") or "").strip()
    brand = (row.get("brand") or "").strip()
    model = (row.get("model") or "").strip()

    if not keyword:
        return None

    normalized_brand = normalize_match_text(brand)
    normalized_model = normalize_match_text(model)
    normalized_keyword = normalize_match_text(keyword)
    token_count = len(_tokens(keyword))

    match_strategy = "none"
    broad_only = False
    usable = False

    if normalized_brand and normalized_model:
        match_strategy = "brand_model"
        usable = True
    elif normalized_brand and not normalized_model:
        if token_count >= 2:
            match_strategy = "keyword"
            usable = True
        else:
            broad_only = True
    elif normalized_model and not normalized_brand:
        if len(normalized_model) >= 3:
            match_strategy = "model"
            usable = True
    elif token_count >= 2:
        match_strategy = "keyword"
        usable = True
    else:
        broad_only = True

    return KeywordEntry(
        product_id=product_id,
        brand=brand,
        model=model,
        category=category,
        keyword=keyword,
        normalized_brand=normalized_brand,
        normalized_model=normalized_model,
        normalized_keyword=normalized_keyword,
        match_strategy=match_strategy,
        broad_only=broad_only,
        usable=usable,
    )


@lru_cache(maxsize=1)
def load_keyword_catalog() -> dict:
    csv_path = Path(__file__).resolve().parent / "data" / KEYWORD_SOURCE_FILE
    if not csv_path.exists():
        raise RuntimeError(f"Keyword CSV not found at {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise RuntimeError(f"Keyword CSV missing required columns: {', '.join(sorted(missing))}")
        raw_rows = list(reader)

    if len(raw_rows) != EXPECTED_RAW_KEYWORD_ROWS:
        raise RuntimeError(
            f"Keyword CSV row count mismatch: expected {EXPECTED_RAW_KEYWORD_ROWS}, got {len(raw_rows)}"
        )

    all_keywords_original: list[str] = []
    entries: list[KeywordEntry] = []
    usable_entries: list[KeywordEntry] = []
    skipped_broad_entries: list[KeywordEntry] = []
    keywords_by_category_raw: dict[str, list[str]] = {}
    usable_entries_by_category: dict[str, list[KeywordEntry]] = {}
    skipped_entries_by_category: dict[str, list[KeywordEntry]] = {}
    exclude_keywords_raw: list[str] = []

    for row in raw_rows:
        entry = _entry_from_row(row)
        if entry is None:
            continue

        all_keywords_original.append(entry.keyword)
        entries.append(entry)
        if entry.category:
            keywords_by_category_raw.setdefault(entry.category, []).append(entry.keyword)

        if entry.usable:
            usable_entries.append(entry)
            if entry.category:
                usable_entries_by_category.setdefault(entry.category, []).append(entry)
        else:
            if entry.broad_only:
                skipped_broad_entries.append(entry)
            if entry.category:
                skipped_entries_by_category.setdefault(entry.category, []).append(entry)

        raw_excludes = row.get("exclude_keywords") or ""
        if raw_excludes.strip():
            exclude_keywords_raw.extend(part.strip() for part in raw_excludes.split(",") if part.strip())

    all_keywords = _dedupe_preserve_case(all_keywords_original)
    keywords_by_category = {
        category: _dedupe_preserve_case(values)
        for category, values in keywords_by_category_raw.items()
    }
    exclude_keywords = _dedupe_preserve_case(exclude_keywords_raw)

    if not all_keywords:
        raise RuntimeError("Keyword CSV contains no valid keywords")
    if not usable_entries:
        raise RuntimeError("Keyword CSV contains no usable keyword entries")

    return {
        "source": KEYWORD_SOURCE_FILE,
        "raw_rows_count": len(raw_rows),
        "keyword_rows_count": len(entries),
        "all_keywords": all_keywords,
        "all_keywords_normalized": [normalize_match_text(keyword) for keyword in all_keywords],
        "keywords_by_category": keywords_by_category,
        "entries": entries,
        "usable_entries": usable_entries,
        "usable_entries_by_category": usable_entries_by_category,
        "skipped_broad_entries": skipped_broad_entries,
        "skipped_entries_by_category": skipped_entries_by_category,
        "exclude_keywords": exclude_keywords,
        "exclude_keywords_normalized": [normalize_match_text(keyword) for keyword in exclude_keywords],
        "last_loaded_at": datetime.now(timezone.utc).isoformat(),
    }
