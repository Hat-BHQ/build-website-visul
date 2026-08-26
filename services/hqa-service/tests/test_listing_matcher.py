from app.listing_matcher import match_listing


def test_jbl_4311_matching():
    cases = [
        ("JBL 4311 speaker", True),
        ("JBL 4311 speakers", True),
        ("Vintage JBL 4311 speakers", True),
        ("JBL 4311 Studio Monitor Speakers Pair", True),

        ("JBL 4312 speakers", False),
        ("JBL 4311B speakers", False),
        ("JBL 14311 speakers", False),

        ("JBL 4311 replacement woofer", False),
        ("JBL 4311 speaker stand", False),
        ("JBL 4311 service manual", False),
    ]

    for title, expected in cases:
        result = match_listing(
            title=title,
            keyword="JBL 4311 speaker",
            brand="JBL",
            model="4311",
            role="whole_product",
        )

        assert result.matched == expected, (
            f"{title}: expected={expected}, "
            f"actual={result.matched}, "
            f"reason={result.reason}"
        )