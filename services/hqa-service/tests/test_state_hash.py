import os
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")

from app.schemas import ListingIn
from app.service import state_hash


def test_state_hash_changes_with_quantity():
    a = ListingIn(marketplace="ebay", external_listing_id="1", listing_title="x", quantity=1)
    b = ListingIn(marketplace="ebay", external_listing_id="1", listing_title="x", quantity=2)
    assert state_hash(a) != state_hash(b)
