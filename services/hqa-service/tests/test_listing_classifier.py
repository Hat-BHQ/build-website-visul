from app.listing_classifier import (
    ROLE_COMPONENT,
    ROLE_WHOLE,
    classify_listing_role,
)


def _row(*, title: str, category: str, price: float = 900.0) -> dict:
    return {
        "listing_title": title,
        "category_name": category,
        "category": category,
        "brand": "JBL",
        "model": "4311B",
        "price": price,
        "exclude_flag": False,
    }


def test_home_speakers_subwoofers_does_not_treat_woofer_as_substring():
    result = classify_listing_role(
        _row(
            title=(
                "JBL 4311B Speakers - Local Pickup Only Or "
                "You Arrange Shipping"
            ),
            category="Home Speakers & Subwoofers",
        ),
        {"reference_median": 1800.0},
    )

    assert result["listing_role"] == ROLE_WHOLE
    assert result["eligible_for_market_analytics"] is True
    assert "category suggests a speaker/electronic component" not in result["role_reasons"]


def test_real_woofer_title_remains_component_in_speaker_category():
    result = classify_listing_role(
        _row(
            title="JBL 4311B Replacement Woofer",
            category="Home Speakers & Subwoofers",
        ),
        {"reference_median": 1800.0},
    )

    assert result["listing_role"] == ROLE_COMPONENT
    assert result["eligible_for_market_analytics"] is False


def test_plural_woofer_category_still_matches_component_boundary():
    result = classify_listing_role(
        _row(
            title="JBL 4311B Audio Item",
            category="Replacement Woofers",
        ),
    )

    assert result["listing_role"] == ROLE_COMPONENT
    assert result["eligible_for_market_analytics"] is False


def test_subwoofer_word_is_not_a_woofer_component_token():
    result = classify_listing_role(
        _row(
            title="JBL Powered Subwoofer",
            category="Home Speakers & Subwoofers",
        ),
        {"reference_median": 900.0},
    )

    assert result["listing_role"] == ROLE_WHOLE
    assert result["eligible_for_market_analytics"] is True
    assert "category suggests a speaker/electronic component" not in result["role_reasons"]
