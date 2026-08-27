from datetime import date

from app.keyword_seller_analytics import build_analytics_payload
from app.listing_matcher import (
    FILTER_MODE_BRAND_MODEL,
    FILTER_MODE_KEYWORD,
    match_brand_model_title,
)


def _marantz_manual_observation():
    return {
        "marketplace": "ebay",
        "seller": "seller-example",
        "listing_id": "v1|147507245562|0",
        "listing_title": (
            "Vintage Marantz 2216B Stereo Receiver With Owner's Manual"
        ),
        "listing_url": "https://www.ebay.com/itm/147507245562",
        "image_url": "",
        "published_at": date(2026, 8, 1),
        "first_seen": date(2026, 8, 17),
        "observed_date": date(2026, 8, 27),
        "price": 675.0,
        "currency": "USD",
        "listing_status": "ACTIVE",
        "quantity": 1,
        "listing_views": 0,
        "condition": "Used",
        "category_name": "Vintage Stereo Receivers",
        "brand": "Marantz",
        "model": "2216B",
        "exclude_flag": False,
        "keyword": "Marantz 2216B",
    }


def test_mode_a_requires_exact_adjacent_brand_model_phrase():
    assert match_brand_model_title(
        "ABC Vintage Marantz 2216B Stereo Receiver XYZ",
        brand="Marantz",
        model="2216B",
    )

    # A token inserted between Brand and Model is not accepted.
    assert not match_brand_model_title(
        "Vintage Marantz Model 2216B Stereo Receiver",
        brand="Marantz",
        model="2216B",
    )

    # Partial / longer model values are not accepted.
    assert not match_brand_model_title(
        "Vintage Marantz 2216BA Stereo Receiver",
        brand="Marantz",
        model="2216B",
    )
    assert not match_brand_model_title(
        "Vintage Marantz 2216B2 Stereo Receiver",
        brand="Marantz",
        model="2216B",
    )


def test_mode_a_keeps_exact_brand_model_even_if_classifier_calls_it_documentation():
    payload = build_analytics_payload(
        [_marantz_manual_observation()],
        filter_mode=FILTER_MODE_BRAND_MODEL,
        brand="Marantz",
        model="2216B",
        min_price=500,
    )

    assert payload["summary"]["seller_count"] == 1
    assert payload["summary"]["listing_count"] == 1
    assert payload["summary"]["matched_observation_count"] == 1

    listing = payload["sellers"][0]["listings"][0]
    assert listing["listing_id"] == "v1|147507245562|0"
    assert listing["eligible"] is True
    # The classifier may still describe the role for audit/UI, but it no longer
    # removes the listing in Mode A.
    assert listing["role"] == "documentation_media"


def test_mode_a_keeps_exact_brand_model_even_when_upstream_exclude_flag_is_true():
    observation = _marantz_manual_observation()
    observation["seller"] = "horsetrdr2pej"
    observation["price"] = 745.99
    observation["listing_status"] = "UNKNOWN"
    observation["exclude_flag"] = True

    payload = build_analytics_payload(
        [observation],
        filter_mode=FILTER_MODE_BRAND_MODEL,
        brand="Marantz",
        model="2216B",
        min_price=500,
    )

    assert payload["summary"]["matched_observation_count"] == 1
    assert payload["summary"]["seller_count"] == 1
    assert payload["summary"]["listing_count"] == 1
    assert payload["sellers"][0]["seller"] == "horsetrdr2pej"
    assert payload["sellers"][0]["representative_price"] == 745.99
    assert payload["sellers"][0]["listings"][0]["status"] == "UNKNOWN"
    assert payload["sellers"][0]["listings"][0]["eligible"] is True


def test_mode_b_still_keeps_whole_product_role_filter():
    payload = build_analytics_payload(
        [_marantz_manual_observation()],
        filter_mode=FILTER_MODE_KEYWORD,
        keyword="Marantz 2216B",
        min_price=500,
    )

    assert payload["summary"]["matched_observation_count"] == 1
    assert payload["summary"]["seller_count"] == 0
