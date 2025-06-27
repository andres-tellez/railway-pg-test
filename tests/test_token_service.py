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
    token_data = {"access_token": "abc", "expires_at": 99999999999}
    mock_get_tokens.return_value = token_data
    mock_is_expired.return_value = False

    token = token_service.get_valid_token(mock_session, athlete_id)
    assert token == "abc"


@patch("src.services.token_service.get_tokens_sa", return_value=None)
def test_get_valid_token_no_tokens(mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    with pytest.raises(RuntimeError):
        token_service.get_valid_token(mock_session, athlete_id)


@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.refresh_token_static")
@patch("src.services.token_service.insert_token_sa")
def test_refresh_access_token_success(mock_insert, mock_refresh_static, mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    old_token_data = {"refresh_token": "old_refresh"}
    new_tokens = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": 1234567890
    }
    mock_get_tokens.return_value = old_token_data
    mock_refresh_static.return_value = new_tokens

    result = token_service.refresh_access_token(mock_session, athlete_id)
    assert result == new_tokens
    mock_insert.assert_called_once_with(
        session=mock_session,
        athlete_id=athlete_id,
        access_token="new_access",
        refresh_token="new_refresh",
        expires_at=1234567890,
    )


@patch("src.services.token_service.get_tokens_sa", return_value=None)
def test_refresh_access_token_no_tokens(mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    with pytest.raises(RuntimeError):
        token_service.refresh_access_token(mock_session, athlete_id)


@patch("src.services.token_service.requests.post")
def test_refresh_token_static_success(mock_post):
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "access", "refresh_token": "refresh", "expires_at": 12345}
    mock_post.return_value = mock_resp

    tokens = token_service.refresh_token_static("dummy_refresh")
    assert "access_token" in tokens
    mock_post.assert_called_once()


@patch("src.services.token_service.requests.post")
def test_exchange_code_for_token_success(mock_post):
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "access", "refresh_token": "refresh", "expires_at": 12345}
    mock_post.return_value = mock_resp

    tokens = token_service.exchange_code_for_token("dummy_code")
    assert "access_token" in tokens
    mock_post.assert_called_once()


@patch("src.services.token_service.refresh_token_static")
@patch("src.services.token_service.get_tokens_sa")
def test_refresh_token_if_expired_true(monkeypatch):
    mock_session = MagicMock()
    # Token expires in past to trigger refresh
    expired_token = Token(
        athlete_id=123,
        access_token="old",
        refresh_token="old_refresh",
        expires_at=int((datetime.utcnow() - timedelta(hours=1)).timestamp())
    )
    mock_query = MagicMock()
    mock_query.filter_by.return_value.first.return_value = expired_token
    mock_session.query.return_value = mock_query

    # Patch refresh_token_static to avoid actual HTTP calls
    monkeypatch.setattr("src.services.token_service.refresh_token_static", lambda rt: {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    })

    from src.services import token_service
    result = token_service.refresh_token_if_expired(mock_session, 123)
    assert result is True


@patch("src.services.token_service.get_tokens_sa")
def test_refresh_token_if_expired_false(mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    mock_get_tokens.return_value = {"expires_at": 9999999999}
    result = token_service.refresh_token_if_expired(mock_session, athlete_id)
    assert result is False


@patch("src.services.token_service.get_tokens_sa", return_value=None)
def test_refresh_token_if_expired_no_tokens(mock_get_tokens):
    mock_session = MagicMock()
    athlete_id = 123
    with pytest.raises(ValueError):
        token_service.refresh_token_if_expired(mock_session, athlete_id)


def test_get_authorization_url_valid():
    url = token_service.get_authorization_url()
    assert "strava.com/oauth/authorize" in url
    assert f"client_id={token_service.config.STRAVA_CLIENT_ID}" in url


@patch("src.services.token_service.insert_token_sa")
@patch("src.services.token_service.exchange_code_for_token")
@patch("src.services.token_service.insert_athlete")
def test_store_tokens_from_callback(mock_insert_athlete, mock_exchange_code, mock_insert_token):
    mock_session = MagicMock()
    code = "dummy_code"
    athlete_info = {
        "id": 123,
        "firstname": "John",
        "lastname": "Doe",
        "email": "john@example.com"
    }
    token_response = {
        "athlete": athlete_info,
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": 1234567890
    }
    mock_exchange_code.return_value = token_response

    athlete_id = token_service.store_tokens_from_callback(code, mock_session)
    assert athlete_id == 123
    mock_insert_token.assert_called_once()
    mock_insert_athlete.assert_called_once()


@patch("src.services.token_service.get_session")
@patch("src.services.token_service.insert_token_sa")
def test_login_user_success(mock_insert_token, mock_get_session):
    mock_get_session.return_value = MagicMock()
    data = {"username": token_service.config.ADMIN_USER, "password": token_service.config.ADMIN_PASS}

    access_token, refresh_token = token_service.login_user(data)
    assert access_token is not None
    assert refresh_token is not None
    mock_insert_token.assert_called_once()


def test_login_user_invalid_credentials():
    data = {"username": "bad", "password": "bad"}
    with pytest.raises(PermissionError):
        token_service.login_user(data)


@patch("src.services.token_service.jwt.decode")
@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.get_session")
def test_refresh_token_success_basic(mock_get_session, mock_get_tokens, mock_jwt_decode):
    mock_get_session.return_value = MagicMock()
    mock_get_tokens.return_value = {"refresh_token": "valid_token"}
    mock_jwt_decode.return_value = {"sub": "admin"}

    new_token = token_service.refresh_token("valid_token")
    assert new_token is not None


@patch("src.services.token_service.jwt.decode")
def test_refresh_token_expired_signature(mock_jwt_decode):
    mock_jwt_decode.side_effect = jwt.ExpiredSignatureError
    with pytest.raises(PermissionError):
        token_service.refresh_token("token")


@patch("src.services.token_service.jwt.decode")
def test_refresh_token_invalid_token(mock_jwt_decode):
    mock_jwt_decode.side_effect = jwt.InvalidTokenError
    with pytest.raises(PermissionError):
        token_service.refresh_token("token")


def test_delete_athlete_tokens():
    mock_session = MagicMock()
    mock_session.query().filter_by().delete.return_value = True

    athlete_id = 123
    result = token_service.delete_athlete_tokens(mock_session, athlete_id)

    assert result is True
    mock_session.query().filter_by().delete.assert_called_once()
    mock_session.commit.assert_called_once()


def test_logout_user_noop():
    token_service.logout_user("token")


@patch("src.services.token_service.refresh_token_static")
@patch("src.services.token_service.jwt.decode")
@patch("src.services.token_service.get_tokens_sa")
@patch("src.services.token_service.get_session")
def test_refresh_token_success(mock_get_session, mock_get_tokens, mock_jwt_decode, mock_refresh_static):
    mock_get_session.return_value = MagicMock()
    mock_get_tokens.return_value = {"refresh_token": "valid_token"}
    mock_jwt_decode.return_value = {"sub": "admin", "type": "refresh"}
    mock_refresh_static.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": 1234567890
    }

    new_token = token_service.refresh_token("valid_token")
    assert new_token is not None
