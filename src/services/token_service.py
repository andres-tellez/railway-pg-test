# src/services/token_service.py
import logging
import requests
from datetime import datetime

from src.utils.config import config
from src.db.db_session import get_session as db_get_session
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa
from src.db.models.tokens import Token
from sqlalchemy.exc import IntegrityError
from src.db.dao import user_athletes_dao  # add this import


logger = logging.getLogger(__name__)


def get_session():
    return db_get_session()


def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())


def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        return refresh_access_token(session, athlete_id)["access_token"]

    return token_data["access_token"]


def refresh_access_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No refresh token available for athlete {athlete_id}")

    tokens = refresh_token_static(token_data["refresh_token"])
    print("Refreshed token:", tokens, flush=True)
    insert_token_sa(
        session=session,
        athlete_id=athlete_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_at=tokens["expires_at"],
    )
    return tokens


def refresh_token_static(refresh_token):
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    return response.json()


def refresh_token_if_expired(session, athlete_id):
    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        raise ValueError(f"No token found for athlete ID {athlete_id}")

    now = datetime.utcnow().timestamp()
    if token.expires_at <= now:
        refreshed = refresh_token_static(token.refresh_token)
        token.access_token = refreshed["access_token"]
        token.refresh_token = refreshed["refresh_token"]
        token.expires_at = refreshed["expires_at"]
        session.commit()
        return True
    return False


def delete_athlete_tokens(session, athlete_id):
    deleted = session.query(Token).filter_by(athlete_id=athlete_id).delete()
    session.commit()
    return deleted


def store_tokens_from_callback(code, session, redirect_uri, user_id: str | None = None):
    logger.info(
        f"[store_tokens_from_callback] called with user_id={user_id}, redirect_uri={redirect_uri}"
    )
    from sqlalchemy.exc import IntegrityError
    from src.db.dao import user_athletes_dao
    from src.db.dao.token_dao import insert_token_sa
    from src.db.models.tokens import Token
    from src.utils.config import config
    import requests

    print("🔑 Using Strava client_id:", config.STRAVA_CLIENT_ID, flush=True)
    print("🔑 Using Strava client_secret:", config.STRAVA_CLIENT_SECRET, flush=True)
    print("🔑 Using redirect_uri:", redirect_uri, flush=True)
    print("🔑 Using code:", code, flush=True)

    redirect_uri_clean = redirect_uri.strip().rstrip(";")
    print(
        f"[TokenService] Using cleaned redirect_uri: '{redirect_uri_clean}'", flush=True
    )

    payload = {
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri_clean,
    }

    print(f"[TokenService] Sending POST data to Strava token endpoint:\n{payload}")
    response = requests.post("https://www.strava.com/api/v3/oauth/token", data=payload)

    # 🔎 Debug logging so we can see the real error from Strava
    print("📥 Strava token response status:", response.status_code, flush=True)
    print("📥 Strava token response body:", response.text, flush=True)

    response.raise_for_status()
    token_data = response.json()

    athlete = token_data.get("athlete")
    if not athlete or "id" not in athlete:
        raise KeyError("❌ Strava callback response missing athlete ID")

    strava_athlete_id = athlete["id"]

    # ✅ 1. Ensure athlete exists in user_athletes BEFORE inserting token
    if user_id:
        try:
            user_athletes_dao.create_link(
                user_id=user_id,
                athlete_id=strava_athlete_id,
            )
            print(f"✅ Linked user {user_id} → athlete {strava_athlete_id}", flush=True)
        except IntegrityError:
            session.rollback()  # clear failed transaction
            print(f"🔗 Link already exists for user {user_id}", flush=True)

    # ✅ 2. Insert or update tokens
    try:
        insert_token_sa(
            session=session,
            athlete_id=strava_athlete_id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=token_data["expires_at"],
        )
        print(f"✅ Token stored for athlete: {strava_athlete_id}", flush=True)
    except IntegrityError:
        session.rollback()  # clear failed transaction
        print(
            f"♻️ Token already exists for athlete {strava_athlete_id}, updating instead",
            flush=True,
        )

        # UPDATE existing token row instead of failing
        existing = session.query(Token).filter_by(athlete_id=strava_athlete_id).first()
        if existing:
            existing.access_token = token_data["access_token"]
            existing.refresh_token = token_data["refresh_token"]
            existing.expires_at = token_data["expires_at"]
            session.commit()
            print(f"✅ Token updated for athlete: {strava_athlete_id}", flush=True)

    logger.info(
        f"[store_tokens_from_callback] ✅ Finished storing tokens for user_id={user_id}, athlete_id={strava_athlete_id}"
    )
    return strava_athlete_id


def exchange_code_for_token(code, redirect_uri=None):
    if redirect_uri is None:
        redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    else:
        redirect_uri = redirect_uri.strip().rstrip(";")

    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    return response.json()


def get_authorization_url():
    redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    client_id = config.STRAVA_CLIENT_ID
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return url
