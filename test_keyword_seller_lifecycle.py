from datetime import date

from app.keyword_seller_analytics import build_lifecycle_axis, build_seller_series
from app.listing_classifier import ROLE_WHOLE


def _whole_listing():
    published_at = date(2026, 7, 7)
    first_seen = date(2026, 8, 10)
    latest = date(2026, 8, 25)

    return {
        "key": "ebay:v1|287443064122|0",
        "marketplace": "ebay",
        "listing_id": "v1|287443064122|0",
        "seller": "classic-bikeworkz",
        "title": "Pioneer CT-F750 Vintage Tape Deck Tested",
        "url": "",
        "published_at": published_at,
        "first_seen": first_seen,
        "appeared_at": published_at,
        "role": ROLE_WHOLE,
        "exclude_flag": False,
        "snapshot_dates": [first_seen, latest],
        "snapshots": {
            first_seen: {
                "date": first_seen,
                "price": 596.0,
                "status": "ACTIVE",
            },
            latest: {
                "date": latest,
                "price": 596.0,
                "status": "ACTIVE",
            },
        },
    }


def test_lifecycle_axis_starts_at_published_at():
    listing = _whole_listing()

    axis = build_lifecycle_axis(
        [listing],
        latest_snapshot=date(2026, 8, 25),
        min_price=500,
        eligible_roles={ROLE_WHOLE},
    )

    assert axis == [
        date(2026, 7, 7),
        date(2026, 8, 10),
        date(2026, 8, 25),
    ]


def test_price_is_not_backfilled_between_publish_and_first_snapshot():
    listing = _whole_listing()
    axis = build_lifecycle_axis(
        [listing],
        latest_snapshot=date(2026, 8, 25),
        min_price=500,
        eligible_roles={ROLE_WHOLE},
    )

    series = build_seller_series(
        [listing],
        axis,
        min_price=500,
        eligible_roles={ROLE_WHOLE},
    )

    assert series[0]["date"] == date(2026, 7, 7)
    assert series[0]["price"] is None
    assert series[1]["date"] == date(2026, 8, 10)
    assert series[1]["price"] == 596.0
