# tests/test_auth.py
import jwt


def test_login_and_refresh_and_logout(client):
    # login
    resp = client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data and "refresh_token" in data

    # refresh
    rt = data["refresh_token"]
    resp2 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert resp2.status_code == 200
    new_at = resp2.get_json()["access_token"]
    payload = jwt.decode(
        new_at, client.application.config["SECRET_KEY"], algorithms=["HS256"]
    )
    assert payload["sub"] == "admin"

    # logout
    resp3 = client.post("/auth/logout", json={"refresh_token": rt})
    assert resp3.status_code == 200
    assert resp3.get_json()["message"] == "logged out"


def test_login_bad(client):
    resp = client.post("/auth/login", json={"username": "x", "password": "y"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()
