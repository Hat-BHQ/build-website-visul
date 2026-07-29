import os
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.security import ROLE_PERMISSIONS


def test_admin_can_sync_hqa():
    assert "hqa.sync.run" in ROLE_PERMISSIONS["HQA"]["admin"]


def test_user_cannot_sync_hqa():
    assert "hqa.sync.run" not in ROLE_PERMISSIONS["HQA"]["user"]
