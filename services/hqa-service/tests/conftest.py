import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")

import datetime as dt
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import marketplace_research_results, metadata
from app.report_config import REPORT_GROUPS_BY_KEY
from app.security import decode


REPORT_DATE = dt.date(2026, 7, 30)


def _first_match_title(report_key: str) -> str:
    entries = REPORT_GROUPS_BY_KEY[report_key].keyword_entries
    if not entries:
        return f"{report_key}-keyword"
    entry = entries[0]
    if entry.match_strategy == "brand_model":
        return f"{entry.brand} {entry.model} verified listing"
    if entry.match_strategy == "model":
        return f"Model {entry.model} tested unit"
    return f"{entry.keyword} verified listing"


def _row(
    row_id: str,
    *,
    research_date: dt.date,
    marketplace: str,
    listing_id: str,
    listing_title: str,
    seller_or_shop: str,
    price,
    currency: str,
    condition: str,
    category: str,
    category_name: str,
    listing_status: str,
    brand: str | None = None,
    model: str | None = None,
    buying_options: str | None = None,
):
    return {
        "id": row_id,
        "research_date": research_date,
        "collected_at": dt.datetime(2026, 7, 30, 10, 0, 0),
        "marketplace": marketplace,
        "listing_id": listing_id,
        "listing_title": listing_title,
        "listing_url": f"https://example.test/{listing_id}",
        "image_url": None,
        "seller_or_shop": seller_or_shop,
        "price": price,
        "currency": currency,
        "condition": condition,
        "category": category,
        "category_name": category_name,
        "listing_status": listing_status,
        "brand": brand,
        "model": model,
        "buying_options": buying_options,
        "listing_location": "VN",
        "listing_views": 10,
        "quantity": 1,
        "count": None,
        "updated_at": dt.datetime(2026, 7, 30, 12, 0, 0),
        "shipping_price": None,
        "total_price": None,
        "exclude_flag": False,
    }


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_regexp_replace(dbapi_connection, connection_record):
        def _regexp_replace(value, pattern, repl, flags):
            source = value or ""
            return re.sub(pattern, repl, source)

        dbapi_connection.create_function("regexp_replace", 4, _regexp_replace)

    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
        metadata.create_all(connection)
        connection.execute(
            marketplace_research_results.insert(),
            [
                    _row(
                        "1",
                        research_date=REPORT_DATE,
                        marketplace="ebay",
                        listing_id="G1-OK",
                        listing_title=_first_match_title("main_repeated"),
                        seller_or_shop="Seller A",
                        price=600,
                        currency="USD",
                        condition="Used",
                        category="speaker",
                        category_name="Vintage Speakers",
                        listing_status="NEW_LISTING",
                        brand="Pioneer",
                        model="SX1080",
                        buying_options="FIXED_PRICE",
                    ),
                _row(
                    "2",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="G1-500",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller A",
                    price=500,
                    currency="USD",
                    condition="Used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="NEW_LISTING",
                ),
                _row(
                    "3",
                    research_date=REPORT_DATE,
                    marketplace="reverb",
                    listing_id="G2-OK",
                    listing_title=_first_match_title("amplifier_receiver"),
                    seller_or_shop="Seller B",
                    price=700,
                    currency="USD",
                    condition="Good",
                    category="speakers",
                    category_name="Amplifiers & Preamps",
                    listing_status="active",
                    brand="Sansui",
                    model="AU-717",
                    buying_options="FIXED_PRICE, BEST_OFFER",
                ),
                    _row(
                        "4",
                        research_date=REPORT_DATE,
                        marketplace="etsy",
                        listing_id="G3-OK",
                        listing_title=f"{_first_match_title('speaker_parts')} horn",
                        seller_or_shop="Seller C",
                        price=800,
                        currency="USD",
                        condition="new",
                        category="speaker frame",
                        category_name="Other Speaker Parts & Comp.",
                        listing_status="active",
                        brand="JBL",
                        model="L100",
                        buying_options="BEST_OFFER",
                    ),
                _row(
                    "5",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="G4-OK",
                    listing_title=_first_match_title("other_home_audio"),
                    seller_or_shop="Seller D",
                    price=900,
                    currency="USD",
                    condition="refurbished",
                    category="speaker",
                    category_name="Headphones",
                    listing_status="active",
                ),
                _row(
                    "6",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="G5-OK",
                    listing_title=_first_match_title("vintage_accessories"),
                    seller_or_shop="Seller E",
                    price=760,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Knobs, Jacks & Switches",
                    listing_status="active",
                ),
                _row(
                    "7",
                    research_date=REPORT_DATE,
                    marketplace="reverb",
                    listing_id="G6-OK",
                    listing_title="Game console accessory",
                    seller_or_shop="Seller F",
                    price=999,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Video Games & Consoles",
                    listing_status="active",
                ),
                _row(
                    "8",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="COND-BLOCK",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller G",
                    price=1200,
                    currency="USD",
                    condition="FOR PARTS OR NOT WORKING",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="active",
                ),
                _row(
                    "9",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="CAT-BLOCK",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller H",
                    price=1200,
                    currency="USD",
                    condition="used",
                    category="other",
                    category_name="Vintage Speakers",
                    listing_status="active",
                ),
                _row(
                    "10",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="ENDED-TODAY",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller I",
                    price=220,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="ended",
                ),
                _row(
                    "11",
                    research_date=REPORT_DATE,
                    marketplace="reverb",
                    listing_id="OOS-TODAY",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller J",
                    price=180,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="out_of_stock",
                ),
                _row(
                    "12",
                    research_date=dt.date(2026, 7, 1),
                    marketplace="ebay",
                    listing_id="ENDED-OLD",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller K",
                    price=190,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="ended",
                ),
                _row(
                    "13",
                    research_date=dt.date(2026, 7, 1),
                    marketplace="etsy",
                    listing_id="OOS-OLD",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller L",
                    price=210,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="out_of_stock",
                ),
                _row(
                    "14",
                    research_date=dt.date(2026, 7, 3),
                    marketplace="etsy",
                    listing_id="ENDED-NULL-PRICE",
                    listing_title=_first_match_title("main_repeated"),
                    seller_or_shop="Seller M",
                    price=None,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="ended",
                ),
                _row(
                    "15",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="EXCLUDE-TITLE",
                    listing_title=f"{_first_match_title('main_repeated')} manual",
                    seller_or_shop="Seller Z",
                    price=1200,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="active",
                ),
                _row(
                    "16",
                    research_date=REPORT_DATE,
                    marketplace="ebay",
                    listing_id="NO-MATCH-TITLE",
                    listing_title="completely unrelated title",
                    seller_or_shop="Seller N",
                    price=1500,
                    currency="USD",
                    condition="used",
                    category="speaker",
                    category_name="Vintage Speakers",
                    listing_status="active",
                ),
                    _row(
                        "17",
                        research_date=dt.date(2026, 7, 23),
                        marketplace="ebay",
                        listing_id="RAW-23-A",
                        listing_title="Acoustic panel set",
                        seller_or_shop="Raw Seller A",
                        price=120,
                        currency="USD",
                        condition="used",
                        category="other",
                        category_name="Misc Components",
                        listing_status="new_listing",
                        brand="JBL",
                        model="L100",
                        buying_options="FIXED_PRICE, BEST_OFFER",
                    ),
                    _row(
                        "18",
                        research_date=dt.date(2026, 7, 23),
                        marketplace="reverb",
                        listing_id="RAW-23-B",
                        listing_title="Pioneer Reference Bundle",
                        seller_or_shop="Raw Seller B",
                        price=950,
                        currency="USD",
                        condition="new",
                        category="speaker frame",
                        category_name="Frame Components",
                        listing_status="new_listing",
                        brand="jbl",
                        model="L100",
                        buying_options="FIXED_PRICE",
                    ),
                _row(
                    "19",
                    research_date=dt.date(2026, 7, 23),
                    marketplace="etsy",
                    listing_id="RAW-23-C",
                    listing_title="Collector shelf stand",
                    seller_or_shop="Raw Seller C",
                    price=300,
                    currency="USD",
                    condition="refurbished",
                    category="speakers",
                    category_name="Collector Parts",
                    listing_status="new_listing",
                    brand="Pioneer",
                    model="L100",
                    buying_options="",
                ),
                    _row(
                        "20",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-ACTIVE",
                        listing_title="Status active row",
                        seller_or_shop="Status Seller A",
                        price=111,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status=" ACTIVE ",
                        brand="TestBrand",
                        model="TB-1",
                        buying_options="FIXED_PRICE",
                    ),
                    _row(
                        "21",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-ENDED",
                        listing_title="Status ended row",
                        seller_or_shop="Status Seller B",
                        price=112,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status="paused",
                        brand="TestBrand",
                        model="TB-2",
                        buying_options="BEST_OFFER",
                    ),
                    _row(
                        "22",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-NEW",
                        listing_title="Status new row",
                        seller_or_shop="Status Seller C",
                        price=113,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status="new_listing",
                        brand="TestBrand",
                        model="TB-3",
                        buying_options="AUCTION",
                    ),
                    _row(
                        "23",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-OOS",
                        listing_title="Status out row",
                        seller_or_shop="Status Seller D",
                        price=114,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status="retired",
                        brand="TestBrand",
                        model="TB-4",
                        buying_options=None,
                    ),
                    _row(
                        "24",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-UNKNOWN-EMPTY",
                        listing_title="Status empty row",
                        seller_or_shop="Status Seller E",
                        price=115,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status="",
                        brand="",
                        model="",
                        buying_options="",
                    ),
                    _row(
                        "25",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-UNKNOWN-NULL",
                        listing_title="Status null row",
                        seller_or_shop="Status Seller F",
                        price=116,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status=None,
                        brand=None,
                        model=None,
                        buying_options=None,
                    ),
                    _row(
                        "26",
                        research_date=dt.date(2026, 8, 24),
                        marketplace="ebay",
                        listing_id="RAW-24-UNKNOWN-INVALID",
                        listing_title="Status invalid row",
                        seller_or_shop="Status Seller G",
                        price=117,
                        currency="USD",
                        condition="used",
                        category="speaker",
                        category_name="Status Category",
                        listing_status="archived",
                        brand="LegacyBrand",
                        model="LB-1",
                        buying_options="FIXED_PRICE, BEST_OFFER",
                    ),
            ],
        )

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    def override_decode():
        return {
            "sub": "user-1",
            "type": "access",
            "exp": int((dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)).timestamp()),
            "system_role": "superadmin",
            "modules": [],
        }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[decode] = override_decode
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
