import datetime as dt
import socket
from sqlalchemy import event
from app.keyword_catalog import KeywordEntry, normalize_match_text
from app.models import marketplace_research_results
from app.report_config import REPORT_GROUPS_BY_KEY, ReportGroup


REPORT_DATE = dt.date(2026, 7, 30)


def _get_ids(payload):
    return [item["listing_id"] for item in payload["items"]]


def _raw_ids(payload):
    return [item["listing_id"] for item in payload["items"]]


def _insert_listing(db_session, row_id: str, listing_id: str, listing_title: str, price: float | int | None = None):
    db_session.execute(
        marketplace_research_results.insert(),
        {
            "id": row_id,
            "research_date": REPORT_DATE,
            "collected_at": dt.datetime(2026, 7, 30, 10, 0, 0),
            "marketplace": "ebay",
            "listing_id": listing_id,
            "listing_title": listing_title,
            "listing_url": f"https://example.test/{listing_id}",
            "image_url": None,
            "seller_or_shop": "Pioneer Store",
            "price": 1200 if price is None else price,
            "currency": "USD",
            "condition": "used",
            "category": "speaker",
            "category_name": "Vintage Speakers",
            "listing_status": "active",
            "listing_location": "US",
            "listing_views": 10,
            "quantity": 1,
            "count": None,
            "updated_at": dt.datetime(2026, 7, 30, 12, 0, 0),
            "shipping_price": None,
            "total_price": None,
            "exclude_flag": False,
        },
    )
    db_session.commit()


def _patch_main_group(monkeypatch, entries: list[KeywordEntry]):
    from app import report_config

    current = report_config.REPORT_GROUPS_BY_KEY["main_repeated"]
    updated = ReportGroup(
        key=current.key,
        title=current.title,
        table_number=current.table_number,
        category_names=current.category_names,
        keyword_categories=current.keyword_categories,
        title_keywords=[entry.keyword for entry in entries],
        keyword_filter_enabled=True,
        keyword_entries=entries,
        usable_keyword_entries=len(entries),
        skipped_broad_entries=current.skipped_broad_entries,
    )
    monkeypatch.setitem(report_config.REPORT_GROUPS_BY_KEY, "main_repeated", updated)


def _pioneer_entry() -> KeywordEntry:
    return KeywordEntry(
        product_id="X001",
        brand="Pioneer",
        model="SX1080",
        category="receiver",
        keyword="Pioneer SX-1080 receiver",
        normalized_brand=normalize_match_text("Pioneer"),
        normalized_model=normalize_match_text("SX1080"),
        normalized_keyword=normalize_match_text("Pioneer SX-1080 receiver"),
        match_strategy="brand_model",
        broad_only=False,
        usable=True,
    )


def _kef_entry() -> KeywordEntry:
    return KeywordEntry(
        product_id="X002",
        brand="KEF",
        model="104/2",
        category="speakers",
        keyword="KEF 104/2 speakers",
        normalized_brand=normalize_match_text("KEF"),
        normalized_model=normalize_match_text("104/2"),
        normalized_keyword=normalize_match_text("KEF 104/2 speakers"),
        match_strategy="brand_model",
        broad_only=False,
        usable=True,
    )


def test_groups_1_6_use_exact_report_date(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    ids = _get_ids(response.json())
    assert ids == ["G1-OK"]
    assert "NO-MATCH-TITLE" not in ids


def test_groups_1_6_exclude_price_500(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "G1-500" not in _get_ids(response.json())


def test_groups_1_6_only_price_gt_500(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=amplifier_receiver&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G2-OK"]


def test_blocked_condition_case_insensitive(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "COND-BLOCK" not in _get_ids(response.json())


def test_allowed_original_categories_only(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "CAT-BLOCK" not in _get_ids(response.json())


def test_category_name_matches_group_with_trailing_dot_normalization(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=speaker_parts&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G3-OK"]


def test_groups_1_6_exclude_ended_and_out_of_stock(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    ids = _get_ids(response.json())
    assert "ENDED-TODAY" not in ids
    assert "OOS-TODAY" not in ids


def test_ended_report_only_ended(client):
    response = client.get("/internal/v1/reports/marketplace/listings?report_key=ended")
    assert response.status_code == 200
    assert set(_get_ids(response.json())) == {"ENDED-TODAY", "ENDED-OLD", "ENDED-NULL-PRICE"}


def test_out_of_stock_report_only_out_of_stock(client):
    response = client.get("/internal/v1/reports/marketplace/listings?report_key=out_of_stock")
    assert response.status_code == 200
    assert set(_get_ids(response.json())) == {"OOS-TODAY", "OOS-OLD"}


def test_ended_and_out_of_stock_do_not_apply_price_gt_500(client):
    ended = client.get("/internal/v1/reports/marketplace/listings?report_key=ended")
    out_stock = client.get("/internal/v1/reports/marketplace/listings?report_key=out_of_stock")
    assert ended.status_code == 200 and out_stock.status_code == 200
    assert "ENDED-TODAY" in _get_ids(ended.json())
    assert "OOS-TODAY" in _get_ids(out_stock.json())


def test_sort_price_desc_then_id_desc(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=non_audio_irrelevant&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G6-OK"]


def test_search_title(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/listings?report_key=speaker_parts&report_date={REPORT_DATE.isoformat()}&q=horn"
    )
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G3-OK"]


def test_search_listing_id(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/listings?report_key=other_home_audio&report_date={REPORT_DATE.isoformat()}&q=G4-OK"
    )
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G4-OK"]


def test_marketplace_filter(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}&marketplace=EBAY"
    )
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G1-OK"]


def test_pagination(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=ended&page=1&page_size=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 2


def test_summary_counts(client):
    response = client.get(f"/internal/v1/reports/marketplace/summary?report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database_total_rows"] == 26
    assert payload["database_unique_listings"] == 26
    assert payload["total_listings_on_date"] == 13
    assert payload["total_new_today"] == 6
    assert payload["total_ended"] == 3
    assert payload["total_out_of_stock"] == 2
    assert payload["total_matched"] == 11


def test_null_price_does_not_crash_api(client):
    response = client.get("/internal/v1/reports/marketplace/listings?report_key=ended&q=null")
    assert response.status_code == 200


def test_no_sql_injection(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}&q=' OR 1=1 --"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_exclude_keywords_applied_to_groups_1_6(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "EXCLUDE-TITLE" not in _get_ids(response.json())


def test_summary_contains_keyword_catalog_metadata(client):
    response = client.get(f"/internal/v1/reports/marketplace/summary?report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["keyword_catalog"]["source"] == "hqa_keywords.csv"
    assert payload["keyword_catalog"]["raw_rows_count"] == 179
    assert payload["keyword_catalog"]["total_keywords"] >= 1
    assert payload["keyword_catalog"]["usable_keyword_entries"] >= 1
    assert "groups" in payload["keyword_catalog"]


def test_no_database_write(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=ended")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    forbidden = ("insert ", "update ", "delete ", "create ", "alter ", "drop ")
    assert all(not any(statement.startswith(keyword) for keyword in forbidden) for statement in statements)


def test_request_does_not_call_network(client, monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("Network call should not happen during report request")

    monkeypatch.setattr(socket, "create_connection", blocked_connect)
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=ended")
    assert response.status_code == 200


def test_pioneer_sx1080_hyphen_match(client, db_session, monkeypatch):
    _insert_listing(db_session, "200", "PIONEER-HYPHEN", "Pioneer SX-1080 Stereo Receiver")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "PIONEER-HYPHEN" in _get_ids(response.json())


def test_pioneer_sx1080_no_hyphen_match(client, db_session, monkeypatch):
    _insert_listing(db_session, "201", "PIONEER-NO-HYPHEN", "Pioneer SX1080 Receiver")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "PIONEER-NO-HYPHEN" in _get_ids(response.json())


def test_pioneer_sx1080_with_space_match(client, db_session, monkeypatch):
    _insert_listing(db_session, "202", "PIONEER-WITH-SPACE", "Pioneer SX 1080 Receiver")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "PIONEER-WITH-SPACE" in _get_ids(response.json())


def test_matching_case_insensitive(client, db_session, monkeypatch):
    _insert_listing(db_session, "203", "PIONEER-UPPER", "PIONEER sX 1080 RECEIVER")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "PIONEER-UPPER" in _get_ids(response.json())


def test_slash_model_match(client, db_session, monkeypatch):
    _insert_listing(db_session, "204", "KEF-1042", "KEF 1042 bookshelf speakers")
    _patch_main_group(monkeypatch, [_kef_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "KEF-1042" in _get_ids(response.json())


def test_brand_and_model_both_required_when_entry_has_both(client, db_session, monkeypatch):
    _insert_listing(db_session, "205", "ONLY-MODEL", "SX1080 receiver no brand")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "ONLY-MODEL" not in _get_ids(response.json())


def test_brand_only_wrong_model_not_match(client, db_session, monkeypatch):
    _insert_listing(db_session, "206", "WRONG-MODEL", "Pioneer SX980 receiver")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert "WRONG-MODEL" not in _get_ids(response.json())


def test_single_token_brand_not_used_as_independent_filter(client):
    response = client.get(f"/internal/v1/reports/marketplace/summary?report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["keyword_catalog"]["skipped_broad_entries"] >= 1


def test_count_query_matches_item_query(client):
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}&page_size=100")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(payload["items"])


def test_table_1_not_zero_when_hyphen_format_differs(client, db_session, monkeypatch):
    _insert_listing(db_session, "207", "T1-HYPHEN-DIFF", "Vintage Receiver Pioneer SX 1080 Tested")
    _patch_main_group(monkeypatch, [_pioneer_entry()])
    response = client.get(f"/internal/v1/reports/marketplace/listings?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert payload_total_non_zero(response.json())


def payload_total_non_zero(payload):
    return payload["total"] > 0


def test_raw_listings_default_filter_is_report_date_only(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert set(_raw_ids(payload)) == {"RAW-23-A", "RAW-23-B", "RAW-23-C"}


def test_raw_listings_selected_date_returns_full_date_dataset(client):
    response = client.get(f"/internal/v1/reports/marketplace/raw-listings?report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    assert response.json()["total"] == 13


def test_raw_listings_do_not_apply_price_gt_500_rule(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
    assert response.status_code == 200
    assert "RAW-23-A" in _raw_ids(response.json())


def test_raw_listings_do_not_apply_keyword_filtering(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
    assert response.status_code == 200
    assert "RAW-23-A" in _raw_ids(response.json())


def test_raw_listings_do_not_apply_allowed_source_category_filter(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
    assert response.status_code == 200
    assert "RAW-23-A" in _raw_ids(response.json())


def test_raw_listings_return_new_listing_status(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
    assert response.status_code == 200
    statuses = {item["listing_status"] for item in response.json()["items"]}
    assert statuses == {"new_listing"}


def test_raw_listings_search_title(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&q=acoustic")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-A"]


def test_raw_listings_search_listing_id(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&q=RAW-23-B")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-B"]


def test_raw_listings_search_seller(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&q=Seller C")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-C"]


def test_raw_listings_filter_marketplace(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&marketplace=reverb")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-B"]


def test_raw_listings_filter_category(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&category=other")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-A"]


def test_raw_listings_filter_category_name(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&category_name=collector parts")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-C"]


def test_raw_listings_filter_listing_status(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&listing_status=new_listing")
    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_raw_listings_filter_active(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=active")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-24-ACTIVE"]


def test_raw_listings_filter_ended(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-30&listing_status=ended")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["ENDED-TODAY"]


def test_raw_listings_filter_new_listing(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=new_listing")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-24-NEW"]


def test_raw_listings_filter_out_of_stock(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-30&listing_status=out_of_stock")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["OOS-TODAY"]


def test_raw_listings_filter_unknown_with_null(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=unknown")
    assert response.status_code == 200
    assert "RAW-24-UNKNOWN-NULL" in _raw_ids(response.json())


def test_raw_listings_filter_unknown_with_empty_string(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=unknown")
    assert response.status_code == 200
    assert "RAW-24-UNKNOWN-EMPTY" in _raw_ids(response.json())


def test_raw_listings_filter_unknown_with_invalid_status(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=unknown")
    assert response.status_code == 200
    assert "RAW-24-UNKNOWN-INVALID" in _raw_ids(response.json())


def test_raw_listings_filter_listing_status_case_insensitive(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=AcTiVe")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-24-ACTIVE"]


def test_raw_listings_filter_price_range(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&price_min=250&price_max=400")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-C"]


def test_raw_listings_pagination(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&page=1&page_size=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert len(payload["items"]) == 2


def test_raw_listings_sort(client):
    response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&sort=price_desc")
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-B", "RAW-23-C", "RAW-23-A"]


def test_summary_total_listings_on_date_with_summary_filters(client):
    response = client.get("/internal/v1/reports/marketplace/summary?report_date=2026-07-23&marketplace=reverb&q=reference")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database_total_rows"] == 26
    assert payload["database_unique_listings"] == 26
    assert payload["total_listings_on_date"] == 1


def test_summary_database_totals_count_unique_ids_once_and_skip_blank_listing_ids(client, db_session):
    baseline = client.get(f"/internal/v1/reports/marketplace/summary?report_date={REPORT_DATE.isoformat()}").json()

    db_session.execute(
        marketplace_research_results.insert(),
        [
            {
                "id": "9001",
                "research_date": REPORT_DATE,
                "collected_at": dt.datetime(2026, 7, 30, 11, 0, 0),
                "marketplace": "ebay",
                "listing_id": "DUP-SUMMARY-1",
                "listing_title": "Duplicate summary row 1",
                "listing_url": None,
                "image_url": None,
                "seller_or_shop": "Summary Seller",
                "price": 10,
                "currency": "USD",
                "condition": "used",
                "category": "speaker",
                "category_name": "Vintage Speakers",
                "listing_status": "active",
                "listing_location": "US",
                "listing_views": 1,
                "quantity": 1,
                "count": None,
                "updated_at": dt.datetime(2026, 7, 30, 12, 0, 0),
                "shipping_price": None,
                "total_price": None,
                "exclude_flag": False,
            },
            {
                "id": "9002",
                "research_date": REPORT_DATE,
                "collected_at": dt.datetime(2026, 7, 30, 11, 5, 0),
                "marketplace": "ebay",
                "listing_id": "DUP-SUMMARY-1",
                "listing_title": "Duplicate summary row 2",
                "listing_url": None,
                "image_url": None,
                "seller_or_shop": "Summary Seller",
                "price": 11,
                "currency": "USD",
                "condition": "used",
                "category": "speaker",
                "category_name": "Vintage Speakers",
                "listing_status": "active",
                "listing_location": "US",
                "listing_views": 1,
                "quantity": 1,
                "count": None,
                "updated_at": dt.datetime(2026, 7, 30, 12, 0, 0),
                "shipping_price": None,
                "total_price": None,
                "exclude_flag": False,
            },
            {
                "id": "9003",
                "research_date": REPORT_DATE,
                "collected_at": dt.datetime(2026, 7, 30, 11, 10, 0),
                "marketplace": "ebay",
                "listing_id": "   ",
                "listing_title": "Blank listing id row",
                "listing_url": None,
                "image_url": None,
                "seller_or_shop": "Summary Seller",
                "price": 12,
                "currency": "USD",
                "condition": "used",
                "category": "speaker",
                "category_name": "Vintage Speakers",
                "listing_status": "active",
                "listing_location": "US",
                "listing_views": 1,
                "quantity": 1,
                "count": None,
                "updated_at": dt.datetime(2026, 7, 30, 12, 0, 0),
                "shipping_price": None,
                "total_price": None,
                "exclude_flag": False,
            },
        ],
    )
    db_session.commit()

    response = client.get(f"/internal/v1/reports/marketplace/summary?report_date={REPORT_DATE.isoformat()}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["database_total_rows"] == baseline["database_total_rows"] + 3
    assert payload["database_unique_listings"] == baseline["database_unique_listings"] + 1
    assert payload["total_listings_on_date"] == baseline["total_listings_on_date"] + 3


def test_raw_listings_no_database_write(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    forbidden = ("insert ", "update ", "delete ", "create ", "alter ", "drop ")
    assert all(not any(statement.startswith(keyword) for keyword in forbidden) for statement in statements)


def test_raw_listings_status_filter_no_database_write(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/internal/v1/reports/marketplace/raw-listings?report_date=2026-08-24&listing_status=unknown")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    forbidden = ("insert ", "update ", "delete ", "create ", "alter ", "drop ")
    assert all(not any(statement.startswith(keyword) for keyword in forbidden) for statement in statements)


def test_filter_options_returns_200(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23")
    assert response.status_code == 200
    payload = response.json()
    assert payload["view"] == "all_listings"
    assert "options" in payload


def test_filter_options_all_listings_without_report_date_returns_200(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?view=all_listings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["report_date"] is None
    assert payload["report_date_key"] == "all_dates"
    assert payload["cache_key"][2] == "all_dates"
    assert payload["options"]["brands"]["items"]


def test_filter_options_all_listings_without_report_date_spans_multiple_dates(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?view=all_listings")
    assert response.status_code == 200
    brands = {item["value"] for item in response.json()["options"]["brands"]["items"]}
    assert "jbl" in brands
    assert "testbrand" in brands


def test_filter_options_all_listings_without_report_date_does_not_filter_research_date_is_null(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/internal/v1/reports/marketplace/filter-options?view=all_listings")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    assert all("research_date is null" not in statement for statement in statements)


def test_filter_options_all_listings_with_report_date_limits_to_date(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?view=all_listings&report_date=2026-07-23")
    assert response.status_code == 200
    brands = {item["value"] for item in response.json()["options"]["brands"]["items"]}
    assert "jbl" in brands
    assert "testbrand" not in brands


def test_filter_options_report_view_without_report_date_returns_422(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?view=report&report_key=main_repeated")
    assert response.status_code == 422
    assert "report_date is required for report view" in response.json()["detail"]


def test_filter_options_report_view_with_report_date_still_works(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/filter-options?view=report&report_key=main_repeated&report_date={REPORT_DATE.isoformat()}"
    )
    assert response.status_code == 200
    assert response.json()["report_date_key"] == REPORT_DATE.isoformat()


def test_filter_options_buying_options_no_grouping_error(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23")
    assert response.status_code == 200
    buying = response.json()["options"]["buying_options"]["items"]
    values = {item["value"] for item in buying}
    assert "fixed_price" in values
    assert "best_offer" in values


def test_filter_options_case_insensitive_grouping(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23")
    assert response.status_code == 200
    brands = response.json()["options"]["brands"]["items"]
    brand_map = {item["value"]: item for item in brands}
    assert "jbl" in brand_map
    assert brand_map["jbl"]["count"] == 2


def test_filter_options_empty_null_values_do_not_crash(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-08-24")
    assert response.status_code == 200
    payload = response.json()
    brands = payload["options"]["brands"]["items"]
    buying = payload["options"]["buying_options"]["items"]
    assert any(item["value"] == "__unknown__" for item in brands)
    assert any(item["value"] == "__unknown__" for item in buying)


def test_filter_options_no_database_write(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    forbidden = ("insert ", "update ", "delete ", "create ", "alter ", "drop ")
    assert all(not any(statement.startswith(keyword) for keyword in forbidden) for statement in statements)


def test_filter_options_scoped_by_report_date(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    brands = response.json()["options"]["brands"]["items"]
    values = {item["value"] for item in brands}
    assert "jbl" in values
    assert "testbrand" not in values


def test_filter_options_all_listings_not_using_report_business_rules(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    categories = {item["value"] for item in response.json()["options"]["categories"]["items"]}
    assert "other" in categories


def test_filter_options_report_scope_matches_report_rules(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/filter-options?report_date={REPORT_DATE.isoformat()}&view=report&report_key=main_repeated"
    )
    assert response.status_code == 200
    categories = {item["value"] for item in response.json()["options"]["categories"]["items"]}
    assert "other" not in categories


def test_filter_options_fields_are_loaded_from_db(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    options = response.json()["options"]
    assert options["brands"]["items"]
    assert options["models"]["items"]
    assert options["categories"]["items"]
    assert options["listing_locations"]["items"]
    assert options["conditions"]["items"]
    assert options["category_names"]["items"]
    assert options["buying_options"]["items"]


def test_filter_options_buying_options_normalization(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    buying_items = response.json()["options"]["buying_options"]["items"]
    values = {item["value"] for item in buying_items}
    assert "fixed_price" in values
    assert "best_offer" in values


def test_filter_options_exclude_empty_values_but_include_unknown_when_present(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-08-24&view=all_listings")
    assert response.status_code == 200
    brands = response.json()["options"]["brands"]["items"]
    assert all(item["value"] != "" for item in brands)
    assert any(item["value"] == "__unknown__" for item in brands)


def test_filter_options_case_insensitive_dedup_and_counts(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    brands = response.json()["options"]["brands"]["items"]
    jbl = next(item for item in brands if item["value"] == "jbl")
    assert jbl["count"] == 2


def test_filter_options_sorted_az(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200
    labels = [item["label"] for item in response.json()["options"]["brands"]["items"]]
    assert labels == sorted(labels, key=str.lower)


def test_filter_options_faceted_brand_narrows_models(client):
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings&brand=jbl")
    assert response.status_code == 200
    models = {item["value"] for item in response.json()["options"]["models"]["items"]}
    assert models == {"l100"}


def test_filter_options_ignores_self_filter_for_field(client):
    response = client.get(
        "/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings&brand=jbl&model=l100"
    )
    assert response.status_code == 200
    brands = {item["value"] for item in response.json()["options"]["brands"]["items"]}
    assert "pioneer" in brands


def test_raw_listings_apply_all_new_filters(client):
    response = client.get(
        "/internal/v1/reports/marketplace/raw-listings?report_date=2026-07-23&brand=jbl&model=l100&category=speaker%20frame&listing_location=vn&condition=new&category_name=frame%20components&buying_options=fixed_price"
    )
    assert response.status_code == 200
    assert _raw_ids(response.json()) == ["RAW-23-B"]


def test_report_listings_apply_new_filters_as_additional_conditions(client):
    response = client.get(
        f"/internal/v1/reports/marketplace/listings?report_key=speaker_parts&report_date={REPORT_DATE.isoformat()}&brand=jbl&model=l100&category=speaker%20frame&listing_location=vn&condition=new&category_name=other%20speaker%20parts%20%26%20comp&buying_options=best_offer"
    )
    assert response.status_code == 200
    assert _get_ids(response.json()) == ["G3-OK"]


def test_filter_options_no_sql_injection(client):
    response = client.get(
        "/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings&brand=' OR 1=1 --"
    )
    assert response.status_code == 200


def test_filter_options_no_database_write(client, db_session):
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().lower())

    event.listen(db_session.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
        assert response.status_code == 200
    finally:
        event.remove(db_session.bind, "before_cursor_execute", before_cursor_execute)

    forbidden = ("insert ", "update ", "delete ", "create ", "alter ", "drop ")
    assert all(not any(statement.startswith(keyword) for keyword in forbidden) for statement in statements)


def test_filter_options_request_does_not_call_network(client, monkeypatch):
    def blocked_connect(*args, **kwargs):
        raise AssertionError("Network call should not happen during filter options request")

    monkeypatch.setattr(socket, "create_connection", blocked_connect)
    response = client.get("/internal/v1/reports/marketplace/filter-options?report_date=2026-07-23&view=all_listings")
    assert response.status_code == 200


def test_dashboard_summary_endpoint(client):
    response = client.get("/internal/v1/reports/marketplace/dashboard/summary?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_listings"] >= 1
    assert payload["unique_listings"] >= 1
    assert "avg_price" in payload
    assert "active" in payload


def test_dashboard_trend_endpoints(client):
    price_response = client.get("/internal/v1/reports/marketplace/dashboard/price-trend?date_from=2026-07-01&date_to=2026-08-31")
    seller_response = client.get("/internal/v1/reports/marketplace/dashboard/seller-trend?date_from=2026-07-01&date_to=2026-08-31")
    status_response = client.get("/internal/v1/reports/marketplace/dashboard/status-trend?date_from=2026-07-01&date_to=2026-08-31")
    keyword_response = client.get("/internal/v1/reports/marketplace/dashboard/keyword-summary?date_from=2026-07-01&date_to=2026-08-31")
    alerts_response = client.get("/internal/v1/reports/marketplace/dashboard/alerts?date_from=2026-07-01&date_to=2026-08-31")

    assert price_response.status_code == 200
    assert seller_response.status_code == 200
    assert status_response.status_code == 200
    assert keyword_response.status_code == 200
    assert alerts_response.status_code == 200
    assert isinstance(price_response.json().get("points"), list)
    assert isinstance(seller_response.json().get("points"), list)
    assert isinstance(status_response.json().get("points"), list)
    assert isinstance(keyword_response.json().get("items"), list)
    assert isinstance(alerts_response.json().get("alerts"), list)


def test_raw_and_report_export_csv_endpoints(client):
    raw_response = client.get("/internal/v1/reports/marketplace/raw-listings/export-csv?report_date=2026-07-23")
    report_response = client.get(
        f"/internal/v1/reports/marketplace/listings/export-csv?report_key=main_repeated&report_date={REPORT_DATE.isoformat()}"
    )

    assert raw_response.status_code == 200
    assert report_response.status_code == 200
    assert raw_response.headers["content-type"].startswith("text/csv")
    assert report_response.headers["content-type"].startswith("text/csv")
    assert "listing_id" in raw_response.text
    assert "listing_id" in report_response.text


def test_dashboard_export_csv_endpoint(client):
    response = client.get("/internal/v1/reports/marketplace/dashboard/export-csv?dataset=summary")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "total_listings" in response.text


def test_all_listings_new_endpoint_returns_paginated_rows(client):
    response = client.get("/internal/v1/hqa/listings?page=1&page_size=10&sort_collected=newest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert "items" in payload
    assert "total" in payload


def test_all_listings_supports_price_sorting(client):
    asc_response = client.get("/internal/v1/hqa/listings?page=1&page_size=10&sort_by=price&sort_order=asc")
    assert asc_response.status_code == 200
    asc_payload = asc_response.json()
    assert asc_payload["applied_filters"]["sort_by"] == "price"
    assert asc_payload["applied_filters"]["sort_order"] == "asc"
    asc_prices = [item.get("price") for item in asc_payload["items"] if item.get("price") is not None]
    assert asc_prices == sorted(asc_prices)

    desc_response = client.get("/internal/v1/hqa/listings?page=1&page_size=10&sort_by=price&sort_order=desc")
    assert desc_response.status_code == 200
    desc_payload = desc_response.json()
    assert desc_payload["applied_filters"]["sort_order"] == "desc"
    desc_prices = [item.get("price") for item in desc_payload["items"] if item.get("price") is not None]
    assert desc_prices == sorted(desc_prices, reverse=True)


def test_all_listings_pagination_and_price_sorting_work_across_pages(client, db_session):
    for index in range(63):
        _insert_listing(
            db_session,
            row_id=f"pagination-{index + 1}",
            listing_id=f"PAG-{index + 1:03d}",
            listing_title=f"Pagination row {index + 1}",
            price=10 + index,
        )

    page_one_response = client.get("/internal/v1/hqa/listings?page=1&page_size=50")
    assert page_one_response.status_code == 200
    page_one_payload = page_one_response.json()
    assert page_one_payload["total"] == 89
    assert page_one_payload["page"] == 1
    assert page_one_payload["page_size"] == 50
    assert page_one_payload["total_pages"] == 2
    assert len(page_one_payload["items"]) == 50

    page_two_response = client.get("/internal/v1/hqa/listings?page=2&page_size=50")
    assert page_two_response.status_code == 200
    page_two_payload = page_two_response.json()
    assert page_two_payload["page"] == 2
    assert page_two_payload["page_size"] == 50
    assert page_two_payload["total_pages"] == 2
    assert len(page_two_payload["items"]) == 39

    asc_page_one_response = client.get("/internal/v1/hqa/listings?page=1&page_size=50&sort_by=price&sort_order=asc")
    assert asc_page_one_response.status_code == 200
    asc_page_one_payload = asc_page_one_response.json()
    asc_page_one_prices = [item.get("price") for item in asc_page_one_payload["items"] if item.get("price") is not None]
    assert asc_page_one_payload["applied_filters"]["sort_by"] == "price"
    assert asc_page_one_payload["applied_filters"]["sort_order"] == "asc"
    assert asc_page_one_prices == sorted(asc_page_one_prices)

    asc_page_two_response = client.get("/internal/v1/hqa/listings?page=2&page_size=50&sort_by=price&sort_order=asc")
    assert asc_page_two_response.status_code == 200
    asc_page_two_payload = asc_page_two_response.json()
    asc_page_two_prices = [item.get("price") for item in asc_page_two_payload["items"] if item.get("price") is not None]
    assert asc_page_two_payload["applied_filters"]["sort_by"] == "price"
    assert asc_page_two_payload["applied_filters"]["sort_order"] == "asc"
    assert asc_page_two_prices == sorted(asc_page_two_prices)
    assert asc_page_two_prices[0] >= asc_page_one_prices[-1]

    desc_page_one_response = client.get("/internal/v1/hqa/listings?page=1&page_size=50&sort_by=price&sort_order=desc")
    assert desc_page_one_response.status_code == 200
    desc_page_one_payload = desc_page_one_response.json()
    desc_page_one_prices = [item.get("price") for item in desc_page_one_payload["items"] if item.get("price") is not None]
    assert desc_page_one_payload["applied_filters"]["sort_by"] == "price"
    assert desc_page_one_payload["applied_filters"]["sort_order"] == "desc"
    assert desc_page_one_prices == sorted(desc_page_one_prices, reverse=True)

    desc_page_two_response = client.get("/internal/v1/hqa/listings?page=2&page_size=50&sort_by=price&sort_order=desc")
    assert desc_page_two_response.status_code == 200
    desc_page_two_payload = desc_page_two_response.json()
    desc_page_two_prices = [item.get("price") for item in desc_page_two_payload["items"] if item.get("price") is not None]
    assert desc_page_two_payload["applied_filters"]["sort_by"] == "price"
    assert desc_page_two_payload["applied_filters"]["sort_order"] == "desc"
    assert desc_page_two_prices == sorted(desc_page_two_prices, reverse=True)
    assert desc_page_two_prices[-1] <= desc_page_one_prices[-1]


def test_internal_listings_returns_new_datetime_fields(client):
    response = client.get("/internal/v1/listings?q=G1-OK&page=1&page_size=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    item = payload["items"][0]
    assert "listing_published_at" in item
    assert "last_status_checked_at" in item
    assert item["listing_published_at"] is not None
    assert item["last_status_checked_at"] is not None


def test_all_listings_returns_new_datetime_fields_with_null_fallback(client):
    response = client.get("/internal/v1/hqa/listings?search=RAW-24-UNKNOWN-NULL&page=1&page_size=10&sort_collected=newest")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    item = payload["items"][0]
    assert "listing_published_at" in item
    assert "last_status_checked_at" in item
    assert item["listing_published_at"] is None
    assert item["last_status_checked_at"] is None


def test_all_listings_filter_options_brand_scopes_models(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?brand=jbl")
    assert response.status_code == 200
    payload = response.json()
    assert "marketplaces" in payload
    assert "brands" in payload
    assert "models" in payload
    assert isinstance(payload["models"], list)


def test_all_listings_filter_options_field_mode_rejects_invalid_field(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?field=invalid_field&page=1&page_size=20")
    assert response.status_code == 400
    assert "Invalid field" in response.json()["detail"]


def test_all_listings_filter_options_field_mode_rejects_page_size_over_limit(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?field=brand&page=1&page_size=101")
    assert response.status_code == 422


def test_all_listings_filter_options_field_mode_pagination_has_more(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?field=brand&page=1&page_size=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field"] == "brand"
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) <= 1
    assert isinstance(payload["has_more"], bool)


def test_all_listings_filter_options_field_mode_model_scoped_by_brand(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?field=model&brand=jbl&page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field"] == "model"
    model_values = {item["value"].lower() for item in payload["items"]}
    assert model_values == {"l100"}


def test_all_listings_filter_options_field_mode_search_and_normalization(client):
    response = client.get("/internal/v1/hqa/listings/filter-options?field=buying_option&search= fixed &page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field"] == "buying_option"
    values = [item["value"] for item in payload["items"]]
    assert all(value.strip() for value in values)
    assert len(values) == len({value.lower() for value in values})
    assert all("fixed" in value.lower() for value in values)


def test_all_listings_accepts_multi_value_filters(client):
    response = client.get(
        "/internal/v1/hqa/listings?condition=used&condition=new&status=active&status=ended&category_name=vintage%20speakers&buying_option=fixed_price&page=1&page_size=20"
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)
    assert payload["applied_filters"]["condition"] == ["used", "new"]
    assert payload["applied_filters"]["status"] == ["active", "ended"]
    assert payload["applied_filters"]["category_name"] == ["vintage speakers"]
    assert payload["applied_filters"]["buying_option"] == ["fixed_price"]


def test_all_listings_supports_marketplace_and_price_range_filters(client):
    response = client.get("/internal/v1/hqa/listings?marketplace=ebay&min_price=500&max_price=2500&page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied_filters"]["marketplace"] == "ebay"
    assert payload["applied_filters"]["min_price"] == 500.0
    assert payload["applied_filters"]["max_price"] == 2500.0


def test_all_listings_summary_and_export(client):
    summary = client.get("/internal/v1/hqa/listings/summary?brand=jbl")
    export = client.get("/internal/v1/hqa/listings/export?brand=jbl&sort_collected=newest")

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert "total_records_stored" in summary_payload
    assert "filtered_records" in summary_payload
    assert "active" in summary_payload

    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert export.text.startswith("\ufeff")
    assert "listing_id" in export.text


def test_all_listings_summary_and_export_share_multi_filters(client):
    query = "marketplace=ebay&condition=used&condition=new&status=active&status=ended&min_price=100&max_price=5000&search=pioneer"
    summary = client.get(f"/internal/v1/hqa/listings/summary?{query}")
    export = client.get(f"/internal/v1/hqa/listings/export?{query}&sort_collected=newest")

    assert summary.status_code == 200
    assert export.status_code in (200, 404)
    if export.status_code == 200:
        assert export.headers["content-type"].startswith("text/csv")
        assert "listing_id" in export.text


def test_all_listings_rejects_invalid_price_range(client):
    response = client.get("/internal/v1/hqa/listings?min_price=3000&max_price=1000")
    assert response.status_code == 400
    assert "min_price must be <= max_price" in response.json()["detail"]


def test_all_listings_export_returns_404_when_no_data(client):
    response = client.get("/internal/v1/hqa/listings/export?from_date=1990-01-01&to_date=1990-01-02")
    assert response.status_code == 404


def test_hqa_dashboard_filter_options_returns_db_driven_options(client):
    response = client.get("/internal/v1/hqa/dashboard/filter-options?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert "options" in payload
    assert payload["options"]["marketplaces"]
    assert payload["options"]["brands"]
    assert payload["options"]["sellers"]


def test_hqa_dashboard_total_sellers_endpoint(client):
    response = client.get("/internal/v1/hqa/dashboard/sellers/total")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seller_column"] == "seller_or_shop"
    assert payload["date_column"] == "research_date"
    assert "total_sellers" in payload


def test_hqa_dashboard_total_sellers_endpoint_accepts_date_range(client):
    response = client.get("/internal/v1/hqa/dashboard/sellers/total?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert payload["date_from"] == "2026-07-01"
    assert payload["date_to"] == "2026-08-31"


def test_hqa_dashboard_seller_analytics_endpoints(client):
    summary_response = client.get("/internal/v1/hqa/dashboard/sellers/summary?date_from=2026-07-01&date_to=2026-08-31")
    trend_response = client.get("/internal/v1/hqa/dashboard/sellers/trend?date_from=2026-07-01&date_to=2026-08-31&granularity=month")
    top_response = client.get("/internal/v1/hqa/dashboard/sellers/top?date_from=2026-07-01&date_to=2026-08-31&limit=5")

    assert summary_response.status_code == 200
    assert trend_response.status_code == 200
    assert top_response.status_code == 200

    summary = summary_response.json()
    assert "total_sellers" in summary
    assert "new_sellers" in summary
    assert "total_listings" in summary

    trend = trend_response.json()
    assert trend["granularity"] == "month"
    assert isinstance(trend["points"], list)

    top = top_response.json()
    assert isinstance(top["items"], list)


def test_hqa_dashboard_price_analytics_endpoints(client):
    summary_response = client.get(
        "/internal/v1/hqa/dashboard/prices/summary?date_from=2026-07-01&date_to=2026-08-31&min_price=100&max_price=5000"
    )
    trend_response = client.get(
        "/internal/v1/hqa/dashboard/prices/trend?date_from=2026-07-01&date_to=2026-08-31&granularity=week"
    )
    by_keyword_response = client.get(
        "/internal/v1/hqa/dashboard/prices/by-keyword?date_from=2026-07-01&date_to=2026-08-31&limit=10"
    )

    assert summary_response.status_code == 200
    assert trend_response.status_code == 200
    assert by_keyword_response.status_code == 200

    summary = summary_response.json()
    assert "avg_price" in summary
    assert "median_price" in summary
    assert "sample_size" in summary

    trend = trend_response.json()
    assert trend["granularity"] == "week"
    assert isinstance(trend["points"], list)

    by_keyword = by_keyword_response.json()
    assert isinstance(by_keyword["items"], list)
    assert "total_hits" in by_keyword


def test_hqa_dashboard_alerts_endpoint_uses_threshold_logic(client):
    response = client.get("/internal/v1/hqa/dashboard/alerts?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert "alerts" in payload
    assert "trend_points" in payload
    assert isinstance(payload["alerts"], list)


def test_hqa_dashboard_endpoints_accept_multi_value_filters(client):
    response = client.get(
        "/internal/v1/hqa/dashboard/prices/trend?marketplace=ebay&marketplace=reverb&brand=jbl&status=active&status=ended&granularity=month"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["granularity"] == "month"


def test_hqa_dashboard_export_dataset_routes(client):
    response = client.get(
        "/internal/v1/hqa/dashboard/export?dataset=prices_trend&granularity=month&date_from=2026-07-01&date_to=2026-08-31"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_hqa_dashboard_export_returns_404_when_no_rows(client):
    response = client.get(
        "/internal/v1/hqa/dashboard/export?dataset=prices_by_keyword&date_from=1990-01-01&date_to=1990-01-02"
    )
    assert response.status_code == 404


def test_hqa_dashboard_rejects_invalid_granularity(client):
    response = client.get("/internal/v1/hqa/dashboard/prices/trend?granularity=quarter")
    assert response.status_code == 400
    assert "granularity must be one of" in response.json()["detail"]


def test_hqa_dashboard_unified_summary_endpoint(client):
    response = client.get("/internal/v1/hqa/dashboard/summary?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert "seller_analytics" in payload
    assert "price_analytics" in payload
    assert "total_sellers" in payload["seller_analytics"]
    assert "active_sellers" in payload["seller_analytics"]
    assert "price_sample" in payload["price_analytics"]


def test_hqa_dashboard_unified_trend_endpoints(client):
    seller_response = client.get(
        "/internal/v1/hqa/dashboard/seller-trend?date_from=2026-07-01&date_to=2026-08-31&group_by=month"
    )
    price_response = client.get(
        "/internal/v1/hqa/dashboard/price-trend?date_from=2026-07-01&date_to=2026-08-31&group_by=week"
    )

    assert seller_response.status_code == 200
    assert price_response.status_code == 200

    seller_payload = seller_response.json()
    price_payload = price_response.json()
    assert seller_payload["granularity"] == "month"
    assert price_payload["granularity"] == "week"
    assert isinstance(seller_payload["points"], list)
    assert isinstance(price_payload["points"], list)
    if seller_payload["points"]:
        first_point = seller_payload["points"][0]
        assert "total_sellers" in first_point
        assert "new_sellers" in first_point
    if price_payload["points"]:
        first_point = price_payload["points"][0]
        assert "avg_price" in first_point
        assert "min_price" in first_point
        assert "max_price" in first_point


def test_hqa_dashboard_price_comparison_endpoint(client):
    response = client.get(
        "/internal/v1/hqa/dashboard/price-comparison?date_from=2026-07-01&date_to=2026-08-31&compare_by=brand&limit=10"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["compare_by"] == "brand"
    assert isinstance(payload["items"], list)


def test_hqa_dashboard_alerts_include_structured_price_drop_fields(client):
    response = client.get("/internal/v1/hqa/dashboard/alerts?date_from=2026-07-01&date_to=2026-08-31")
    assert response.status_code == 200
    payload = response.json()
    assert "alerts" in payload
    for alert in payload["alerts"]:
        if alert.get("type") != "price_drop":
            continue
        assert alert.get("severity") in {"warning", "critical"}
        assert "previous_avg_price" in alert
        assert "current_avg_price" in alert
        assert "change_percent" in alert
