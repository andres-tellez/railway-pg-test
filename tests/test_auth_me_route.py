# tests/test_auth_me_route.py


import re
import pytest

pytestmark = pytest.mark.skip(reason="legacy password login removed")


@pytest.fixture(scope="function")
def client(monkeypatch):
    # Enable your built-in DEV BYPASS for this test only
    monkeypatch.setenv("AUTH_BYPASS", "1")

    from src.app import create_app

    app = create_app({"TESTING": True})
    return app.test_client()


def _try_get(client, path, headers=None):
    resp = client.get(path, headers=headers or {})
    return resp.status_code, resp


def test_auth_me_route(client):
    # With AUTH_BYPASS=1, the decorator sets g.current_user.sub to this fixed id
    expected_user = "auth0|dev-bypass"

    # Endpoint moved from /auth/me to /api/me (merged into user_identity_routes.py)
    status, resp = _try_get(client, "/api/me")

    assert status == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    # Endpoint now returns just user_id (merged from auth_me_routes.py)
    assert "user_id" in data
    assert isinstance(data["user_id"], str)
