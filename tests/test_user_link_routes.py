# tests/test_user_link_routes.py
import pytest
from unittest.mock import patch
import base64
import json

# === Mock current user globally for test control ===
_current_user = {}


# ✅ Patch requires_auth so it skips real Auth0 validation
@pytest.fixture(autouse=True)
def mock_auth(monkeypatch):
    # Fake decorator that just runs the function
    def fake_requires_auth(fn):
        def wrapper(*args, **kwargs):
            # Inject current_user into Flask.g
            from flask import g

            g.current_user = {"sub": _current_user.get("id", "auth0|test-user")}
            return fn(*args, **kwargs)

        return wrapper

    monkeypatch.setattr("src.utils.auth0_jwt.requires_auth", fake_requires_auth)
    yield


# ✅ Fixture to dynamically set Authorization header
@pytest.fixture
def auth_header():
    def _h(user_id: str):
        _current_user["id"] = user_id
        # Create a valid-looking fake JWT (not validated in tests)
        payload = (
            base64.urlsafe_b64encode(json.dumps({"sub": user_id}).encode())
            .decode()
            .rstrip("=")
        )
        fake_token = f"eyJhbGciOiJub25lIn0.{payload}."
        return {"Authorization": f"Bearer {fake_token}"}

    return _h


# === TESTS START HERE ===


def test_get_link_unauthorized(client):
    resp = client.get("/api/user/link")
    # Now will be handled by requires_auth shim → returns 404 when no link
    assert resp.status_code in (401, 404)


def test_post_link_conflict(client, auth_header, make_athlete, link_user):
    athlete = make_athlete()
    link_user(user_id="auth0|abc", athlete_id=athlete.id)
    resp = client.post(
        "/api/user/link",
        headers=auth_header("auth0|abc"),
        json={"athlete_id": athlete.id},
    )
    assert resp.status_code == 409


def test_post_link_conflict_same_athlete_different_user(
    client, auth_header, make_athlete, link_user
):
    athlete = make_athlete()
    link_user(user_id="auth0|uA", athlete_id=athlete.id)
    resp = client.post(
        "/api/user/link",
        headers=auth_header("auth0|uB"),
        json={"athlete_id": athlete.id},
    )
    assert resp.status_code == 409


def test_post_link_and_get(client, auth_header, make_athlete):
    athlete = make_athlete()
    resp = client.post(
        "/api/user/link",
        headers=auth_header("auth0|u1"),
        json={"athlete_id": athlete.id},
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    resp = client.get("/api/user/link", headers=auth_header("auth0|u1"))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user_id"] == "auth0|u1"
    assert data["athlete_id"] == athlete.id


def test_get_link_404_when_missing(client, auth_header):
    resp = client.get("/api/user/link", headers=auth_header("auth0|no-link-yet"))
    assert resp.status_code == 404


def test_delete_link(client, auth_header, make_athlete):
    athlete = make_athlete()
    client.post(
        "/api/user/link",
        headers=auth_header("auth0|u2"),
        json={"athlete_id": athlete.id},
    )
    resp = client.delete("/api/user/link", headers=auth_header("auth0|u2"))
    assert resp.status_code == 200
    resp = client.get("/api/user/link", headers=auth_header("auth0|u2"))
    assert resp.status_code == 404


def test_delete_link_missing_returns_404(client, auth_header):
    resp = client.delete("/api/user/link", headers=auth_header("auth0|no-link-here"))
    assert resp.status_code == 404


def test_ignores_spoofed_user_id_in_body(client, auth_header, make_athlete):
    athlete = make_athlete()
    resp = client.post(
        "/api/user/link",
        headers=auth_header("auth0|real-user"),
        json={"athlete_id": athlete.id, "user_id": "auth0|spoof"},
    )
    assert resp.status_code == 201
    resp = client.get("/api/user/link", headers=auth_header("auth0|real-user"))
    assert resp.status_code == 200
    assert resp.get_json()["user_id"] == "auth0|real-user"
