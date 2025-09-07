from datetime import datetime, timezone, timedelta
from src.db.dao.user_identity_dao import get_by_user_id, upsert_identity


def test_upsert_and_get_roundtrip():
    uid = "auth0|dao-user-1"

    upsert_identity(
        {
            "user_id": uid,
            "email": "runner1@example.com",
            "email_verified": True,
            "name": "Runner One",
            "picture": "https://example.com/1.png",
            "updated_at": datetime.now(timezone.utc),
        }
    )

    row = get_by_user_id(uid)
    assert row is not None
    m = getattr(row, "_mapping", row)
    assert m["user_id"] == uid
    assert m["email"] == "runner1@example.com"
    assert m["email_verified"] is True
    assert m["name"] == "Runner One"
    assert m["picture"] == "https://example.com/1.png"

    later = datetime.now(timezone.utc) + timedelta(seconds=1)
    upsert_identity(
        {
            "user_id": uid,
            "email": "runner1+new@example.com",
            "name": "Runner One Updated",
            "updated_at": later,
        }
    )

    row2 = get_by_user_id(uid)
    m2 = getattr(row2, "_mapping", row2)
    assert m2["email"] == "runner1+new@example.com"
    assert m2["name"] == "Runner One Updated"
    assert m2["updated_at"] is not None
