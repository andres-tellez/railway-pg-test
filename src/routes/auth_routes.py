"""
auth_routes.py

Authentication & OAuth Routes
=============================

This module defines the authentication-related routes for login, logout,
token management, and integrations with external OAuth providers (Strava, Auth0).

Responsibilities:
- Handle OAuth redirects and callbacks (Strava + Auth0)
- Decode and validate JWTs (Auth0 RS256)
- Store, refresh, and delete tokens
- Link Strava athletes ↔ users
- Trigger ingestion after authentication
- Provide debug & monitoring utilities

Architectural Note:
This file sits at the intersection of authentication and ingestion domains.
Long-term, you may want to split:
    - Auth0 login/logout
    - Strava OAuth flow
    - Token utilities
    - Debug / diagnostics
"""

from flask import (
    Blueprint,
    redirect,
    request,
    jsonify,
    session as flask_session,
)

import os, traceback, threading, logging

from src.db.db_session import get_session
import src.services.token_service as token_service
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.utils.auth0_jwt import verify_and_decode

# Flask Blueprint for all auth routes
auth_bp = Blueprint("auth", __name__)

# Export token utilities for tests/patching
delete_athlete_tokens = token_service.delete_athlete_tokens
refresh_token_if_expired = token_service.refresh_token_if_expired
store_tokens_from_callback = token_service.store_tokens_from_callback

# Auth0 env vars (for JWT validation)
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

logger = logging.getLogger(__name__)


# ========================================================================
# STRAVA OAUTH FLOW
# ========================================================================


@auth_bp.route("/strava-login", methods=["GET"])
def strava_login_redirect():
    """
    Step 1: Start Strava OAuth login.
    Reads Auth0 JWT from cookie (or fallback query param) to get `auth0_sub`.
    Redirects user to Strava with `state=auth0_sub`.
    """
    print("🛑 Flask route /auth/strava-login triggered", flush=True)

    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")
    client_id = os.getenv("STRAVA_CLIENT_ID") or ""

    # Extract user identity from cookie or fallback param
    jwt_cookie = request.cookies.get("user_jwt")
    auth0_sub = request.args.get("user_id")  # fallback

    if jwt_cookie:
        try:
            payload = verify_and_decode(jwt_cookie)
            auth0_sub = payload.get("sub") or auth0_sub
        except Exception as e:
            print(f"⚠️ Failed to decode JWT: {e}", flush=True)

    # Build Strava OAuth URL
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    if auth0_sub:
        url += f"&state={auth0_sub}"

    print(f"🔗 Redirecting to Strava URL: {url}", flush=True)
    return redirect(url)


@auth_bp.route("/strava/connect", methods=["GET"])
def strava_connect_alias():
    """Alias route to trigger Strava OAuth flow (for flexibility in frontend)."""
    print("⚡️ /auth/strava/connect triggered!", flush=True)
    return strava_login_redirect()


@auth_bp.route("/strava/callback", methods=["GET"])
def strava_callback_get():
    """
    Step 2 (Browser Redirect): Strava calls this after user approval.
    - Exchanges code for tokens
    - Links athlete ↔ user
    - ✅ Triggers ingestion in background (with fresh session)
    - Redirects back to frontend with both user_id + athlete_id
    """
    session = get_session()
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        print(f"🔁 Received Strava callback — code={code}, state={state}", flush=True)

        if not code or not state:
            return jsonify({"error": "Missing code or state"}), 400

        try:
            athlete_id, user_id = process_strava_callback(session, code, state)
        except Exception as e:
            raise RuntimeError(f"❌ Failed to process callback: {e}")

        session.commit()
    except Exception as e:
        session.rollback()
        traceback.print_exc()
        return jsonify({"error": "Callback error", "detail": str(e)}), 500
    finally:
        session.close()

    # ✅ ingestion runs with a brand new session
    def background_job():
        try:
            logger.info(
                f"🚀 Starting ingestion for user={user_id}, athlete={athlete_id}"
            )
            run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)
        except Exception as e:
            logger.error(
                f"❌ Ingestion failed for athlete={athlete_id}: {e}", exc_info=True
            )

    threading.Thread(target=background_job, daemon=True).start()

    frontend_redirect = (
        (os.getenv("FRONTEND_REDIRECT") or "http://localhost:5173/landing")
        .strip()
        .rstrip("/")
    )
    print(f"🔀 Redirecting user to: {frontend_redirect}", flush=True)
    return redirect(f"{frontend_redirect}?strava=connected")


@auth_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
def trigger_ingest(athlete_id):
    """Manually trigger ingestion for an athlete (admin/dev use)."""
    try:
        print(f"[Ingestion] Triggered ingestion for athlete {athlete_id}", flush=True)
        # 🚨 Always pass None so ingestion creates its own fresh session
        result = run_full_ingestion_and_enrichment(None, athlete_id)
        print(f"[Ingestion] Result: {result}", flush=True)
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/strava/callback", methods=["POST"])
def strava_callback_post():
    """
    Step 2 (API Exchange): Alternative to GET callback.
    Allows frontend to POST { code, sub } directly.
    Returns both user_id + athlete_id so frontend can track progress.
    """
    try:
        data = request.get_json() or {}
        code = data.get("code")
        auth0_sub = data.get("sub")

        if not code or not auth0_sub:
            return jsonify({"error": "Missing code or sub"}), 400

        athlete_id = None
        user_id = None
        with get_session() as session:
            athlete_id, user_id = process_strava_callback(session, code, auth0_sub)
            session.commit()

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    # ✅ ingestion runs in fresh session
    def background_job():
        db = get_session()
        try:
            logger.info(
                f"🚀 Starting ingestion for user={user_id}, athlete={athlete_id}"
            )
            run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)
        except Exception as e:
            logger.error(
                f"❌ Ingestion failed for athlete={athlete_id}: {e}", exc_info=True
            )
        finally:
            db.close()

    threading.Thread(target=background_job, daemon=True).start()

    # ✅ return both IDs
    return (
        jsonify(
            {
                "status": "success",
                "user_id": user_id,
                "athlete_id": athlete_id,
            }
        ),
        200,
    )


import re


def process_strava_callback(session, code, state_or_sub, create_if_missing=True):
    """
    Shared Strava OAuth processing logic.

    Handles:
    1. Accepts either internal user_id (UUID) or auth0_sub in `state_or_sub`.
    2. If UUID → use directly.
    3. If auth0_sub → resolve to user_id.
    4. Exchanges code for Strava tokens.
    5. Links athlete ↔ user.

    ⚠️ Does NOT trigger ingestion — caller should do that
       after closing the session, with a fresh one.
    """
    if not code or not state_or_sub:
        raise ValueError("Missing OAuth code or user identifier")

    print(
        f"🔄 Processing callback: code={code}, state_or_sub={state_or_sub}", flush=True
    )

    # Simple regex check for UUID format
    uuid_pattern = re.compile(r"^[0-9a-fA-F-]{36}$")

    if uuid_pattern.match(state_or_sub):
        user_id = state_or_sub  # ✅ Already internal user_id
    else:
        # Fallback: treat as auth0_sub
        from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

        user_id = resolve_user_id_from_auth_provider(
            state_or_sub, create_if_missing=create_if_missing
        )
        if not user_id:
            raise ValueError("User not found or could not be created")

    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")

    try:
        athlete_id = token_service.store_tokens_from_callback(
            code=code,
            session=session,
            redirect_uri=redirect_uri,
            user_id=user_id,
        )
        print(f"✅ Stored tokens for athlete {athlete_id}", flush=True)
        logger.info(
            f"[process_strava_callback] Linked athlete={athlete_id} to user={user_id}"
        )
    except Exception as e:
        raise RuntimeError(f"Token exchange failed: {e}")

    return athlete_id, user_id


# ========================================================================
# AUTH0 LOGIN FLOW
# ========================================================================


@auth_bp.route("/login/callback", methods=["POST"])
def login_callback():
    """
    Handles login after Auth0 provides an id_token (JWT).
    - Verifies JWT signature.
    - Extracts user profile fields.
    - Resolves or creates internal user_id.
    - Sets cookie with `user_jwt` for session persistence.
    """
    session = get_session()
    try:
        data = request.get_json() or {}
        id_token = data.get("id_token")
        if not id_token:
            return jsonify({"error": "Missing id_token"}), 400

        try:
            decoded_jwt = verify_and_decode(id_token)
            print(f"🔍 Decoded JWT claims: {decoded_jwt}", flush=True)
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        auth0_sub = decoded_jwt.get("sub")
        user_profile = {
            "email": decoded_jwt.get("email"),
            "name": decoded_jwt.get("name"),
            "picture": decoded_jwt.get("picture"),
            "email_verified": decoded_jwt.get("email_verified"),
        }

        from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

        user_id = resolve_user_id_from_auth_provider(
            auth0_sub, user_profile, create_if_missing=True
        )
        if not user_id:
            return jsonify({"error": "Could not resolve or create user"}), 404

        user_jwt = id_token  # ← Use the token you just verified

        resp = jsonify({"ok": True, "user_id": user_id})
        resp.set_cookie(
            "user_jwt",
            user_jwt,
            httponly=True,
            secure=True,
            samesite="None",
            domain=os.getenv("SESSION_COOKIE_DOMAIN"),
            path="/",
        )
        # logs
        print("🔐 Setting cookie → user_jwt")
        print("   • Value (truncated):", user_jwt[:15])
        print("   • Domain:", os.getenv("SESSION_COOKIE_DOMAIN"))
        print("   • Secure:", True)
        print("   • SameSite: None")
        print("   • Path: /")
        return resp, 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ========================================================================
# TOKEN MANAGEMENT
# ========================================================================


@auth_bp.route("/refresh/<int:athlete_id>", methods=["POST"])
def refresh_token(athlete_id):
    """Force refresh Strava tokens if expired."""
    session = get_session()
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        try:
            verify_and_decode(token)
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

        refreshed = refresh_token_if_expired(session, athlete_id)
        return jsonify({"refreshed": refreshed}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@auth_bp.route("/logout/<int:athlete_id>", methods=["POST"])
def logout(athlete_id):
    """Logout athlete by deleting stored Strava tokens."""
    session = get_session()
    try:
        deleted = delete_athlete_tokens(session, athlete_id)
        return jsonify({"deleted": deleted}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ========================================================================
# DEBUGGING & MONITORING UTILITIES
# ========================================================================


@auth_bp.route("/debug/set", methods=["GET"])
def debug_set_cookie():
    """Manually set a debug athlete_id in session (dev only)."""
    flask_session["athlete_id"] = "debug-athlete"
    flask_session.permanent = True
    return jsonify({"status": "set", "session": dict(flask_session)}), 200


@auth_bp.route("/debug/show", methods=["GET"])
def debug_show_cookie():
    """Show current request cookies + session contents (dev only)."""
    return (
        jsonify({"request_cookies": request.cookies, "session": dict(flask_session)}),
        200,
    )


@auth_bp.route("/monitor-tokens", methods=["GET"])
def monitor_tokens():
    """List all tokens with their expiry (for debugging)."""
    session = get_session()
    try:
        rows = session.execute(
            "SELECT athlete_id, expires_at FROM tokens ORDER BY expires_at"
        ).fetchall()
        data = [{"athlete_id": r.athlete_id, "expires_at": r.expires_at} for r in rows]
        return jsonify(data), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
