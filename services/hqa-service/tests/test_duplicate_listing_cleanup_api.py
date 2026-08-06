import datetime as dt

import pytest
from sqlalchemy import func, select

from app import service as hqa_service
from app.models import marketplace_research_results


BASE_RESEARCH_DATE = dt.date(2026, 8, 1)


def _insert_listing(
    db_session,
    *,
    row_id: str,
    marketplace: str,
    listing_id: str,
    listing_status: str | None,
    listing_title: str = "Duplicate Listing",
    last_status_checked_at: dt.datetime | None = None,
    updated_at: dt.datetime | None = None,
    collected_at: dt.datetime | None = None,
    listing_published_at: dt.datetime | None = None,
):
    db_session.execute(
        marketplace_research_results.insert(),
        {
            "id": row_id,
            "research_date": BASE_RESEARCH_DATE,
            "collected_at": collected_at or dt.datetime(2026, 8, 1, 10, 0, 0),
            "marketplace": marketplace,
            "listing_id": listing_id,
            "listing_title": listing_title,
            "listing_url": f"https://example.test/{row_id}",
            "image_url": None,
            "seller_or_shop": "Duplicate Seller",
            "price": 100.0,
            "currency": "USD",
            "condition": "used",
            "category": "speaker",
            "category_name": "Vintage Speakers",
            "listing_status": listing_status,
            "listing_location": "US",
            "listing_views": 1,
            "quantity": 1,
            "count": None,
            "updated_at": updated_at or dt.datetime(2026, 8, 1, 11, 0, 0),
            "listing_published_at": listing_published_at or dt.datetime(2026, 7, 30, 9, 0, 0),
            "last_status_checked_at": last_status_checked_at,
            "shipping_price": None,
            "total_price": None,
            "exclude_flag": False,
        },
    )


def _count_rows_by_listing(db_session, marketplace: str, listing_id: str) -> int:
    return int(
        db_session.execute(
            select(func.count())
            .select_from(marketplace_research_results)
            .where(func.lower(func.trim(marketplace_research_results.c.marketplace)) == marketplace.lower())
            .where(func.lower(func.trim(marketplace_research_results.c.listing_id)) == listing_id.lower())
        ).scalar_one()
        or 0
    )


def test_duplicate_group_keeps_ended_and_deletes_active(client, db_session):
    _insert_listing(db_session, row_id="DUP-T1-A", marketplace="ebay", listing_id="T1-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T1-B", marketplace="ebay", listing_id="T1-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T1-C", marketplace="ebay", listing_id="T1-KEY", listing_status="ended")
    db_session.commit()

    response = client.get("/internal/v1/hqa/data-check/duplicates?listing_id=t1-key")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_groups"] == 1

    item = payload["items"][0]
    assert item["keep_record"]["id"] == "DUP-T1-C"
    assert len(item["delete_records"]) == 2
    assert sorted(record["id"] for record in item["delete_records"]) == ["DUP-T1-A", "DUP-T1-B"]


def test_duplicate_group_prefers_latest_in_ended_out_of_stock(client, db_session):
    _insert_listing(
        db_session,
        row_id="DUP-T2-A",
        marketplace="ebay",
        listing_id="T2-KEY",
        listing_status="active",
        last_status_checked_at=dt.datetime(2026, 8, 1, 9, 0, 0),
    )
    _insert_listing(
        db_session,
        row_id="DUP-T2-B",
        marketplace="ebay",
        listing_id="T2-KEY",
        listing_status="out_of_stock",
        last_status_checked_at=dt.datetime(2026, 8, 5, 9, 0, 0),
    )
    _insert_listing(
        db_session,
        row_id="DUP-T2-C",
        marketplace="ebay",
        listing_id="T2-KEY",
        listing_status="ended",
        last_status_checked_at=dt.datetime(2026, 8, 6, 9, 0, 0),
    )
    db_session.commit()

    response = client.get("/internal/v1/hqa/data-check/duplicates?listing_id=t2-key")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["keep_record"]["id"] == "DUP-T2-C"
    assert len(item["delete_records"]) == 2


def test_all_active_keeps_latest_status_checked(client, db_session):
    _insert_listing(
        db_session,
        row_id="DUP-T3-A",
        marketplace="ebay",
        listing_id="T3-KEY",
        listing_status="active",
        last_status_checked_at=dt.datetime(2026, 8, 5, 9, 0, 0),
    )
    _insert_listing(
        db_session,
        row_id="DUP-T3-B",
        marketplace="ebay",
        listing_id="T3-KEY",
        listing_status="active",
        last_status_checked_at=dt.datetime(2026, 8, 6, 9, 0, 0),
    )
    db_session.commit()

    response = client.get("/internal/v1/hqa/data-check/duplicates?listing_id=t3-key")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["keep_record"]["id"] == "DUP-T3-B"
    assert len(item["delete_records"]) == 1


def test_marketplace_case_insensitive_grouping_and_cross_marketplace_split(client, db_session):
    _insert_listing(db_session, row_id="DUP-T4-A", marketplace="eBay", listing_id="T4-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T4-B", marketplace="EBAY", listing_id="T4-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T4-C", marketplace="reverb", listing_id="T4-KEY", listing_status="active")
    db_session.commit()

    ebay_response = client.get("/internal/v1/hqa/data-check/duplicates?marketplace=ebay&listing_id=t4-key")
    assert ebay_response.status_code == 200
    assert ebay_response.json()["total_groups"] == 1

    reverb_response = client.get("/internal/v1/hqa/data-check/duplicates?marketplace=reverb&listing_id=t4-key")
    assert reverb_response.status_code == 200
    assert reverb_response.json()["total_groups"] == 0


def test_empty_listing_id_not_deleted_by_cleanup(client, db_session):
    _insert_listing(db_session, row_id="DUP-T5-A", marketplace="ebay", listing_id="", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T5-B", marketplace="ebay", listing_id="", listing_status="ended")
    _insert_listing(db_session, row_id="DUP-T5-C", marketplace="ebay", listing_id="", listing_status="out_of_stock")

    _insert_listing(db_session, row_id="DUP-T5-D", marketplace="ebay", listing_id="T5-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T5-E", marketplace="ebay", listing_id="T5-KEY", listing_status="ended")
    db_session.commit()

    response = client.post(
        "/internal/v1/hqa/data-check/duplicates/cleanup",
        json={"confirmation": "DELETE_DUPLICATE_LISTINGS"},
    )
    assert response.status_code == 200
    assert _count_rows_by_listing(db_session, "ebay", "T5-KEY") == 1

    empty_count = int(
        db_session.execute(
            select(func.count())
            .select_from(marketplace_research_results)
            .where(func.trim(marketplace_research_results.c.listing_id) == "")
        ).scalar_one()
        or 0
    )
    assert empty_count == 3


def test_cleanup_second_run_returns_zero_deleted(client, db_session):
    _insert_listing(db_session, row_id="DUP-T6-A", marketplace="ebay", listing_id="T6-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T6-B", marketplace="ebay", listing_id="T6-KEY", listing_status="ended")
    db_session.commit()

    first_cleanup = client.post(
        "/internal/v1/hqa/data-check/duplicates/cleanup",
        json={"confirmation": "DELETE_DUPLICATE_LISTINGS"},
    )
    assert first_cleanup.status_code == 200
    assert first_cleanup.json()["records_deleted"] >= 1

    second_cleanup = client.post(
        "/internal/v1/hqa/data-check/duplicates/cleanup",
        json={"confirmation": "DELETE_DUPLICATE_LISTINGS"},
    )
    assert second_cleanup.status_code == 200
    assert second_cleanup.json()["records_deleted"] == 0


def test_cleanup_requires_exact_confirmation_token(client):
    response = client.post(
        "/internal/v1/hqa/data-check/duplicates/cleanup",
        json={"confirmation": "WRONG_TOKEN"},
    )
    assert response.status_code == 400


def test_cleanup_rolls_back_when_post_cleanup_verification_fails(db_session, monkeypatch):
    _insert_listing(db_session, row_id="DUP-T7-A", marketplace="ebay", listing_id="T7-KEY", listing_status="active")
    _insert_listing(db_session, row_id="DUP-T7-B", marketplace="ebay", listing_id="T7-KEY", listing_status="ended")
    db_session.commit()

    original_summary = hqa_service.fetch_duplicate_listing_summary
    call_count = {"value": 0}

    def failing_summary(session):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("forced post-delete verification error")
        return original_summary(session)

    monkeypatch.setattr(hqa_service, "fetch_duplicate_listing_summary", failing_summary)

    with pytest.raises(RuntimeError):
        hqa_service.cleanup_duplicate_listings(db_session)

    assert _count_rows_by_listing(db_session, "ebay", "T7-KEY") == 2
