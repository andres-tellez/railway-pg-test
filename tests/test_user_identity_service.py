from datetime import datetime, timezone
from types import SimpleNamespace
import pytest

from src.services.user_identity_service import get_or_create_user_identity
import src.db.dao.user_identity_dao as dao


def test_get_or_create_user_identity_happy_path(monkeypatch):
    calls = {"upsert": []}

    def fake_upsert_identity(payload):
        calls["upsert"].append(payload)
        # Return Row-like (dict-like) structure
        return SimpleNamespace(
            _mapping={
                "user_id": payload["user_id"],
                "email": payload.get("email"),
                "email_verified": payload.get("email_verified"),
                "name": payload.get("name"),
                "picture": payload.get("picture"),
                "updated_at": datetime(2025, 8, 10, 12, 34, 56, tzinfo=timezone.utc),
            }
        )

    def fake_get_by_user_id(_uid):
        return None

    monkeypatch.setattr(dao, "upsert_identity", fake_upsert_identity)
    monkeypatch.setattr(dao, "get_by_user_id", fake_get_by_user_id)

    claims = {
        "sub": "auth0|svcuser",
        "email": "svc@example.com",
        "email_verified": True,
        "name": "Svc User",
        "picture": "https://p.png",
        "updated_at": "2025-08-10T12:34:56Z",
        "permissions": ["read:me"],
    }

    resp = get_or_create_user_identity(claims)

    assert resp["user_id"] == "auth0|svcuser"
    assert resp["email"] == "svc@example.com"
    assert resp["email_verified"] is True
    assert resp["name"] == "Svc User"
    assert resp["picture"] == "https://p.png"
    assert resp["roles"] == ["read:me"]
    assert isinstance(resp["updated_at"], str)
