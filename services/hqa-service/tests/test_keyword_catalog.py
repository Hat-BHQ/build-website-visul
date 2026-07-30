import csv
from pathlib import Path

from app.keyword_catalog import KEYWORD_SOURCE_FILE, load_keyword_catalog, normalize_match_text
from app.report_config import REPORT_GROUPS_BY_KEY


def test_reads_csv_with_dict_reader_and_expected_rows():
    csv_path = Path(__file__).resolve().parents[1] / "app" / "data" / KEYWORD_SOURCE_FILE
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert len(rows) == 179


def test_catalog_has_179_raw_rows_and_non_empty_keyword_rows():
    catalog = load_keyword_catalog()
    assert catalog["raw_rows_count"] == 179
    assert catalog["keyword_rows_count"] == 179


def test_deduplicate_keywords_case_insensitive():
    catalog = load_keyword_catalog()
    normalized = [keyword.strip().lower() for keyword in catalog["all_keywords"]]
    assert len(normalized) == len(set(normalized))


def test_exclude_keywords_are_split_trimmed_and_deduplicated():
    catalog = load_keyword_catalog()
    excludes = catalog["exclude_keywords"]
    normalized = [item.lower().strip() for item in excludes]
    assert len(normalized) == len(set(normalized))
    assert "manual" in normalized
    assert "parts only" in normalized
    assert "for repair" in normalized


def test_mapping_speakers_into_main_repeated():
    group = REPORT_GROUPS_BY_KEY["main_repeated"]
    assert "speakers" in group.keyword_categories
    assert len(group.title_keywords) > 0


def test_mapping_receiver_in_two_reports():
    main_group = REPORT_GROUPS_BY_KEY["main_repeated"]
    amp_group = REPORT_GROUPS_BY_KEY["amplifier_receiver"]
    assert "receiver" in main_group.keyword_categories
    assert "receiver" in amp_group.keyword_categories


def test_mapping_amplifier_into_amplifier_receiver():
    group = REPORT_GROUPS_BY_KEY["amplifier_receiver"]
    assert "amplifier" in group.keyword_categories
    assert group.keyword_filter_enabled is True


def test_mapping_wood_case_into_vintage_accessories():
    group = REPORT_GROUPS_BY_KEY["vintage_accessories"]
    assert "wood case" in group.keyword_categories


def test_non_audio_irrelevant_keyword_not_required():
    group = REPORT_GROUPS_BY_KEY["non_audio_irrelevant"]
    assert group.keyword_filter_enabled is False


def test_ended_keyword_not_required():
    group = REPORT_GROUPS_BY_KEY["ended"]
    assert group.keyword_filter_enabled is False


def test_out_of_stock_keyword_not_required():
    group = REPORT_GROUPS_BY_KEY["out_of_stock"]
    assert group.keyword_filter_enabled is False


def test_normalize_match_text_examples():
    assert normalize_match_text("SX-1080") == "sx1080"
    assert normalize_match_text("SX 1080") == "sx1080"
    assert normalize_match_text("JBL 4312 MKII") == "jbl4312mkii"
    assert normalize_match_text("B&W") == "bw"
    assert normalize_match_text("104/2") == "1042"


def test_single_token_brand_entries_are_skipped_as_broad():
    catalog = load_keyword_catalog()
    jbl_entries = [entry for entry in catalog["entries"] if entry.normalized_keyword == "jbl"]
    assert len(jbl_entries) >= 1
    assert all(entry.broad_only and not entry.usable for entry in jbl_entries)
    assert all(entry.normalized_keyword not in [usable.normalized_keyword for usable in catalog["usable_entries"]] for entry in jbl_entries)
