import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, jsonify
import jwt

import src.utils.jwt_utils as jwt_utils
import src.utils.config as config


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


def create_token(payload, expired=False):
    key = config.SECRET_KEY
    if expired:
        payload['exp'] = 0  # expired
    else:
        payload['exp'] = 9999999999
    return jwt.encode(payload, key, algorithm="HS256")


def test_decode_token_valid():
    token = create_token({"sub": "user1"})
    decoded = jwt_utils.decode_token(token)
    assert decoded["sub"] == "user1"


def test_decode_token_invalid():
    with pytest.raises(ValueError):
        jwt_utils.decode_token("not-a-token")


def test_require_auth_internal_key(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    # Internal key present and matches config
    with app.test_client() as client:
        headers = {"X-Internal-Key": config.INTERNAL_API_KEY}
        resp = client.get("/protected", headers=headers)
        assert resp.status_code == 200
        assert resp.json == {"success": True}


def test_require_auth_missing_auth_header(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        resp = client.get("/protected")
        assert resp.status_code == 401
        assert resp.json["error"] == "Authorization header missing"


def test_require_auth_invalid_auth_header(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    with app.test_client() as client:
        headers = {"Authorization": "InvalidToken abc"}
        resp = client.get("/protected", headers=headers)
        assert resp.status_code == 401
        assert resp.json["error"] == "Authorization header missing"


def test_require_auth_expired_token(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    expired_token = create_token({"sub": "user1"}, expired=True)
    auth_header = f"Bearer {expired_token}"

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": auth_header})
        assert resp.status_code == 401
        assert resp.json["error"] == "Token expired"


def test_require_auth_invalid_token(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    invalid_token = "abc.def.ghi"
    auth_header = f"Bearer {invalid_token}"

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": auth_header})
        assert resp.status_code == 401
        assert resp.json["error"] == "Invalid token"


def test_require_auth_valid_token(client, app):
    app.route("/protected")(jwt_utils.require_auth(lambda: jsonify(success=True)))

    token = create_token({"sub": "user1"})
    auth_header = f"Bearer {token}"

    with app.test_client() as client:
        resp = client.get("/protected", headers={"Authorization": auth_header})
        assert resp.status_code == 200
        assert resp.json == {"success": True}
