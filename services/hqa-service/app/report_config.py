from __future__ import annotations

from dataclasses import dataclass
from app.keyword_catalog import KeywordEntry, load_keyword_catalog


BLOCKED_CONDITION = "for parts or not working"
ALLOWED_ORIGINAL_CATEGORIES = ["speaker", "speakers", "speaker frame"]
MIN_PRICE_FOR_GROUPED_TABLES = 500

KEYWORD_CATEGORY_MAPPING = {
    "main_repeated": ["speakers", "receiver"],
    "amplifier_receiver": ["receiver", "amplifier", "preamplifier", "processor"],
    "speaker_parts": ["speakers", "subwoofer", "center speaker", "speaker frame", "grille"],
    "other_home_audio": ["subwoofer", "center speaker", "eq", "processor"],
    "vintage_accessories": ["wood case", "wood side panels", "grille"],
    "non_audio_irrelevant": [],
}


@dataclass(frozen=True)
class ReportGroup:
    key: str
    title: str
    table_number: int
    category_names: list[str]
    keyword_categories: list[str]
    title_keywords: list[str]
    keyword_filter_enabled: bool
    keyword_entries: list[KeywordEntry]
    usable_keyword_entries: int
    skipped_broad_entries: int


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


def get_entries_for_categories(categories: list[str], catalog: dict) -> tuple[list[KeywordEntry], int]:
    by_category: dict[str, list[KeywordEntry]] = catalog["usable_entries_by_category"]
    skipped_by_category: dict[str, list[KeywordEntry]] = catalog["skipped_entries_by_category"]

    entries: list[KeywordEntry] = []
    skipped = 0
    seen_ids: set[str] = set()

    for category in categories:
        normalized_category = category.strip().lower()
        skipped += len(skipped_by_category.get(normalized_category, []))
        for entry in by_category.get(normalized_category, []):
            dedupe_key = entry.product_id or f"{entry.category}:{entry.normalized_keyword}"
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            entries.append(entry)
    return entries, skipped


def get_keywords_for_entries(entries: list[KeywordEntry]) -> list[str]:
    return _dedupe_preserve([entry.keyword for entry in entries])


def _build_group(
    *,
    key: str,
    title: str,
    table_number: int,
    category_names: list[str],
    keyword_categories: list[str],
    keyword_filter_enabled: bool,
    catalog: dict,
) -> ReportGroup:
    entries, skipped = get_entries_for_categories(keyword_categories, catalog)
    title_keywords = get_keywords_for_entries(entries)

    if keyword_filter_enabled and not entries:
        raise RuntimeError(f"Keyword entries are required for report group: {key}")

    return ReportGroup(
        key=key,
        title=title,
        table_number=table_number,
        category_names=category_names,
        keyword_categories=keyword_categories,
        title_keywords=title_keywords,
        keyword_filter_enabled=keyword_filter_enabled,
        keyword_entries=entries,
        usable_keyword_entries=len(entries),
        skipped_broad_entries=skipped,
    )


def _build_groups() -> list[ReportGroup]:
    catalog = load_keyword_catalog()

    groups = [
        _build_group(
            key="main_repeated",
            title="Nhóm sản phẩm xuất hiện nhiều",
            table_number=1,
            category_names=[
                "Vintage Speakers",
                "Home Speakers & Subwoofers",
                "Speakers",
                "Vintage Stereo Receivers",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["main_repeated"],
            keyword_filter_enabled=True,
            catalog=catalog,
        ),
        _build_group(
            key="amplifier_receiver",
            title="Nhóm ampli và receiver",
            table_number=2,
            category_names=[
                "Amplifiers & Preamps",
                "Amplifiers & Pre-Amps",
                "Amplificateurs",
                "Vintage Amplifiers & Tube Amps",
                "Receivers",
                "Receiver",
                "Amplifier Parts & Components",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["amplifier_receiver"],
            keyword_filter_enabled=True,
            catalog=catalog,
        ),
        _build_group(
            key="speaker_parts",
            title="Nhóm loa và linh kiện loa",
            table_number=3,
            category_names=[
                "Vintage Speaker & Horn Drivers",
                "Car Speakers & Speaker Systems",
                "Woofers",
                "Speaker Boxes",
                "Speaker Mounts & Stands",
                "Other Speaker Parts & Comp",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["speaker_parts"],
            keyword_filter_enabled=True,
            catalog=catalog,
        ),
        _build_group(
            key="other_home_audio",
            title="Nhóm âm thanh gia đình khác",
            table_number=4,
            category_names=[
                "Home Theater Systems",
                "Equalizers",
                "Other Home Stereo Components",
                "Other TV, Video & Home Audio",
                "Marine Audio",
                "Audio Cables & Interconnects",
                "Headphones",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["other_home_audio"],
            keyword_filter_enabled=True,
            catalog=catalog,
        ),
        _build_group(
            key="vintage_accessories",
            title="Nhóm vintage và phụ kiện khác",
            table_number=5,
            category_names=[
                "Other Vintage Audio & Video",
                "Other Vintage A/V Parts & Accs",
                "Knobs, Jacks & Switches",
                "Cases, Covers & Skins",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["vintage_accessories"],
            keyword_filter_enabled=True,
            catalog=catalog,
        ),
        _build_group(
            key="non_audio_irrelevant",
            title="Nhóm sản phẩm không liên quan trực tiếp đến audio",
            table_number=6,
            category_names=[
                "Television Parts",
                "Camera & Photo Accessories",
                "Computer Cables & Connectors",
                "Cell Phones & Accessories",
                "Video Games & Consoles",
                "Others",
            ],
            keyword_categories=KEYWORD_CATEGORY_MAPPING["non_audio_irrelevant"],
            keyword_filter_enabled=False,
            catalog=catalog,
        ),
        ReportGroup(
            key="ended",
            title="Ended",
            table_number=7,
            category_names=[],
            keyword_categories=[],
            title_keywords=[],
            keyword_filter_enabled=False,
            keyword_entries=[],
            usable_keyword_entries=0,
            skipped_broad_entries=0,
        ),
        ReportGroup(
            key="out_of_stock",
            title="Out of stock",
            table_number=8,
            category_names=[],
            keyword_categories=[],
            title_keywords=[],
            keyword_filter_enabled=False,
            keyword_entries=[],
            usable_keyword_entries=0,
            skipped_broad_entries=0,
        ),
    ]

    return groups


REPORT_GROUPS = _build_groups()
REPORT_GROUPS_BY_KEY = {group.key: group for group in REPORT_GROUPS}


def get_keyword_metadata() -> dict:
    catalog = load_keyword_catalog()
    groups = {
        group.key: {
            "keyword_count": len(group.title_keywords),
            "keyword_filter_enabled": group.keyword_filter_enabled,
            "usable_keyword_entries": group.usable_keyword_entries,
            "skipped_broad_entries": group.skipped_broad_entries,
        }
        for group in REPORT_GROUPS
    }
    return {
        "source": catalog["source"],
        "raw_rows_count": catalog["raw_rows_count"],
        "total_keywords": len(catalog["all_keywords"]),
        "usable_keyword_entries": len(catalog["usable_entries"]),
        "skipped_broad_entries": len(catalog["skipped_broad_entries"]),
        "last_loaded_at": catalog["last_loaded_at"],
        "groups": groups,
    }
