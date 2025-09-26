# tests/test_jwt_utils.py
import pytest
from flask import Flask, jsonify
from unittest.mock import patch

import src.utils.jwt_utils as jwt_utils
import src.utils.config as config


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


# --- Helpers -------------------------------------------------
@pytest.fixture(autouse=True)
def mock_auth0(monkeypatch):
    """
    Patch verify_and_decode so we can simulate valid/invalid tokens.
    """

    def fake_verify_and_decode(token):
        if token == "valid":
            return {"sub": "user1"}
        elif token == "expired":
            raise Exception("Token expired")
        else:
            raise Exception("Invalid token")

    monkeypatch.setattr("src.utils.jwt_utils.verify_and_decode", fake_verify_and_decode)
    yield


# --- Tests ---------------------------------------------------


def test_decode_token_valid():
    claims = jwt_utils.decode_token("valid")
    assert claims["sub"] == "user1"


def test_decode_token_invalid():
    with pytest.raises(ValueError):
        jwt_utils.decode_token("bad")


def test_require_auth_internal_key(app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        headers = {"X-Internal-Key": config.INTERNAL_API_KEY}
        resp = client.get("/protected", headers=headers)
        assert resp.status_code == 200
        assert resp.json == {"success": True}


def test_require_auth_missing_auth_header(app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert resp.json["error"] == "Authorization header missing"


def test_require_auth_expired_token(app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": "Bearer expired"})
        assert resp.status_code == 401
        assert "expired" in resp.json["error"].lower()


def test_require_auth_invalid_token(app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
        assert "invalid" in resp.json["error"].lower()


def test_require_auth_valid_token(app):
    @app.route("/protected")
    @jwt_utils.require_auth
    def protected():
        from flask import g

        return jsonify(success=True, user_id=g.user_id)

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200
        assert resp.json["success"] is True
        # Now assert UUID-like value
        assert isinstance(resp.json["user_id"], str)
        assert len(resp.json["user_id"]) == 36  # UUID string
