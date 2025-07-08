import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import jwt
from requests.models import Response
from src.services import token_service
from src.db.models.tokens import Token


def test_is_expired():
    past = int((datetime.utcnow() - timedelta(seconds=10)).timestamp())
    future = int((datetime.utcnow() + timedelta(seconds=10)).timestamp())
    assert token_service.is_expired(past) is True
    assert token_service.is_expired(future) is False


@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.is_expired")
def test_get_valid_token_success(mock_is_expired, mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    mock_get_tokens.return_value = {"access_token": "abc", "expires_at": 99999999999}
    mock_is_expired.return_value = False

    token = token_service.get_valid_token(mock_session, athlete_id)
    assert token == "abc"


@patch("src.services.token_service.get_tokens_sa", return_value=None)
def test_get_valid_token_no_tokens(mock_get_tokens):
    mock_session = MagicMock()
    with pytest.raises(RuntimeError):
        token_service.get_valid_token(mock_session, 123)


@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.refresh_token_static")
@patch("src.services.token_service.insert_token_sa")
def test_refresh_access_token_success(mock_insert, mock_refresh_static, mock_get_tokens):
    mock_session = MagicMock()
    mock_get_tokens.return_value = {"refresh_token": "old_refresh"}
    mock_refresh_static.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": 1234567890
    }

    result = token_service.refresh_access_token(mock_session, 123)
    assert result["access_token"] == "new_access"
    mock_insert.assert_called_once()


@patch("src.services.token_service.get_tokens_sa", return_value=None)
def test_refresh_access_token_no_tokens(mock_get_tokens):
    mock_session = MagicMock()
    with pytest.raises(RuntimeError):
        token_service.refresh_access_token(mock_session, 123)


@patch("src.services.token_service.requests.post")
def test_refresh_token_static_success(mock_post):
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "access", "refresh_token": "refresh", "expires_at": 12345}
    mock_post.return_value = mock_resp

    tokens = token_service.refresh_token_static("dummy_refresh")
    assert "access_token" in tokens


@patch("src.services.token_service.requests.post")
def test_exchange_code_for_token_success(mock_post):
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "access", "refresh_token": "refresh", "expires_at": 12345}
    mock_post.return_value = mock_resp

    tokens = token_service.exchange_code_for_token("dummy_code")
    assert "access_token" in tokens


def test_refresh_token_if_expired_true():
    mock_session = MagicMock()
    expired_token = Token(
        athlete_id=123,
        access_token="old",
        refresh_token="old_refresh",
        expires_at=int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    )
    mock_session.query.return_value.filter_by.return_value.first.return_value = expired_token

    with patch("src.services.token_service.refresh_token_static") as mock_refresh_static:
        mock_refresh_static.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_at": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        }
        result = token_service.refresh_token_if_expired(mock_session, 123)
        assert result is True


def test_refresh_token_if_expired_false():
    mock_session = MagicMock()
    valid_token = Token(
        athlete_id=123,
        access_token="abc",
        refresh_token="ref",
        expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    )
    mock_session.query.return_value.filter_by.return_value.first.return_value = valid_token

    result = token_service.refresh_token_if_expired(mock_session, 123)
    assert result is False


def test_refresh_token_if_expired_no_tokens():
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    with pytest.raises(ValueError):
        token_service.refresh_token_if_expired(mock_session, 123)


def test_get_authorization_url_valid():
    url = token_service.get_authorization_url()
    assert "strava.com/oauth/authorize" in url
    assert f"client_id={token_service.config.STRAVA_CLIENT_ID}" in url


@patch("src.services.token_service.insert_athlete")
@patch("src.services.token_service.requests.post")
@patch("src.services.token_service.insert_token_sa")
def test_store_tokens_from_callback(mock_insert_token, mock_post, mock_insert_athlete):
    mock_session = MagicMock()
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "athlete": {"id": 123, "firstname": "John", "lastname": "Doe", "email": "john@example.com"},
        "access_token": "access", "refresh_token": "refresh", "expires_at": 1234567890
    }
    mock_post.return_value = mock_response

    athlete_id = token_service.store_tokens_from_callback("dummy_code", mock_session)
    assert athlete_id == 123
    mock_insert_token.assert_called_once()
    mock_insert_athlete.assert_called_once()



@patch("src.services.token_service.get_session")
@patch("src.services.token_service.insert_token_sa")
def test_login_user_success(mock_insert_token, mock_get_session):
    mock_get_session.return_value = MagicMock()
    data = {"username": token_service.config.ADMIN_USER, "password": token_service.config.ADMIN_PASS}

    access_token, refresh_token = token_service.login_user(data)
    assert access_token and refresh_token
    mock_insert_token.assert_called_once()


def test_login_user_invalid_credentials():
    with pytest.raises(PermissionError):
        token_service.login_user({"username": "bad", "password": "bad"})


@patch("src.services.token_service.refresh_token_static")
@patch("src.services.token_service.get_session")
@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.jwt.decode")
def test_refresh_token_success_basic(mock_jwt_decode, mock_get_tokens, mock_get_session, mock_refresh_static):
    mock_get_session.return_value = MagicMock()
    mock_get_tokens.return_value = {"refresh_token": "valid_token"}
    mock_jwt_decode.return_value = {"sub": "admin", "type": "refresh"}
    mock_refresh_static.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": 1234567890
    }

    token = token_service.refresh_token("valid_token")
    assert token


@patch("src.services.token_service.jwt.decode", side_effect=jwt.ExpiredSignatureError)
def test_refresh_token_expired_signature(mock_jwt_decode):
    with pytest.raises(PermissionError):
        token_service.refresh_token("token")


@patch("src.services.token_service.jwt.decode", side_effect=jwt.InvalidTokenError)
def test_refresh_token_invalid_token(mock_jwt_decode):
    with pytest.raises(PermissionError):
        token_service.refresh_token("token")


def test_delete_athlete_tokens():
    mock_session = MagicMock()
    mock_session.query().filter_by().delete.return_value = True

    result = token_service.delete_athlete_tokens(mock_session, 123)
    assert result is True
    mock_session.commit.assert_called_once()


def test_logout_user_noop():
    token_service.logout_user("token")
