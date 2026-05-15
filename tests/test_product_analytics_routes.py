"""Product analytics batch ingest API."""

import uuid

from src.db.models.user_auth_providers import UserAuthProvider
from src.db.models.user_identity import UserIdentity


def test_post_analytics_events_accepts_batch(
    app, client, auth_header, test_db_session
):  # noqa: ARG001
    """Pre-seed Auth0 mapping so SQLite tests never hit UUID bind issues on user creation."""

    uid = uuid.uuid5(uuid.NAMESPACE_DNS, "auth0|test-user")
    test_db_session.merge(
        UserIdentity(
            user_id=uid,
            email="analytics-test@example.com",
            email_verified=True,
            name="Analytics Test",
            picture=None,
        )
    )
    test_db_session.merge(
        UserAuthProvider(
            user_id=str(uid),
            provider_name="auth0",
            provider_user_id="test-user",
            full_provider_id="auth0|test-user",
        )
    )
    test_db_session.commit()

    from src.db.models.product_analytics_event import ProductAnalyticsEvent
    from src.db import db_session

    res = client.post(
        "/api/analytics/events",
        json={
            "events": [
                {
                    "event_name": "pilot_test",
                    "outcome": "success",
                    "properties": {"k": "v"},
                    "client_event_id": "unit-1",
                }
            ]
        },
        headers={**auth_header(), "Content-Type": "application/json"},
    )
    assert res.status_code == 200
    assert res.get_json().get("accepted") == 1

    s = db_session.SessionLocal()
    try:
        rows = (
            s.query(ProductAnalyticsEvent)
            .filter(ProductAnalyticsEvent.event_name == "pilot_test")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].outcome == "success"
        assert rows[0].source == "client"
        assert rows[0].client_event_id == "unit-1"
        assert rows[0].user_id == str(uid)
    finally:
        s.close()
