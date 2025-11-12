"""
Strava Integration Helper Utilities
===================================

Shared utility functions for Strava integration to eliminate code repetition.

These functions provide common patterns used across Strava routes and services:
- Session management with proper cleanup
- User ID extraction and validation
- Athlete link retrieval
- Background job execution
- Frontend redirect URL construction
"""

from flask import g
from typing import Optional, Tuple, Callable
from src.db.db_session import get_session
from src.db.dao.user_athletes_dao import get_by_user_id
from src.db.models.user_athletes import UserAthleteLink
from src.utils.response_utils import unauthorized_response
import os
import threading
import logging

logger = logging.getLogger(__name__)


def get_authenticated_user_id() -> Tuple[Optional[str], Optional[tuple]]:
    """
    Extract and validate authenticated user ID from Flask g object.

    Returns:
        Tuple of (user_id, error_response):
        - If authenticated: (user_id, None)
        - If not authenticated: (None, unauthorized_response)

    Example:
        user_id, error = get_authenticated_user_id()
        if error:
            return error
        # Use user_id
    """
    internal_user_id = getattr(g, "user_id", None)

    if not internal_user_id:
        return None, unauthorized_response(reason="User not authenticated")

    return internal_user_id, None


def get_user_athlete_link(
    user_id: str,
) -> Tuple[Optional[UserAthleteLink], Optional[tuple]]:
    """
    Get athlete link for a user.

    Args:
        user_id: Internal user ID (UUID)

    Returns:
        Tuple of (athlete_link, error_response):
        - If found: (athlete_link, None)
        - If not found: (None, not_found_response)

    Example:
        athlete_link, error = get_user_athlete_link(user_id)
        if error:
            return error
        # Use athlete_link
    """
    from src.utils.response_utils import not_found_response

    athlete_link = get_by_user_id(user_id)

    if not athlete_link:
        return None, not_found_response(
            resource="Strava connection",
        )

    return athlete_link, None


def get_authenticated_user_with_athlete() -> (
    Tuple[Optional[str], Optional[UserAthleteLink], Optional[tuple]]
):
    """
    Get authenticated user ID and their athlete link in one call.

    Returns:
        Tuple of (user_id, athlete_link, error_response):
        - If authenticated and connected: (user_id, athlete_link, None)
        - If error: (None, None, error_response)

    Example:
        user_id, athlete_link, error = get_authenticated_user_with_athlete()
        if error:
            return error
        # Use user_id and athlete_link
    """
    user_id, error = get_authenticated_user_id()
    if error:
        return None, None, error

    athlete_link, error = get_user_athlete_link(user_id)
    if error:
        return user_id, None, error

    return user_id, athlete_link, None


def with_db_session(func: Callable) -> Callable:
    """
    Decorator to manage database session lifecycle.

    Automatically creates session, passes it to function, and ensures cleanup.

    Args:
        func: Function that takes session as first argument

    Returns:
        Wrapped function that manages session

    Example:
        @with_db_session
        def my_function(session, other_args):
            # Use session
            return result
    """

    def wrapper(*args, **kwargs):
        session = get_session()
        try:
            return func(session, *args, **kwargs)
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    return wrapper


def run_background_job(job_func: Callable, *args, **kwargs) -> None:
    """
    Run a function in a background thread with proper session management.

    Creates a fresh database session for the background job and ensures cleanup.

    Args:
        job_func: Function to run in background
        *args: Positional arguments for job_func
        **kwargs: Keyword arguments for job_func

    Example:
        def my_background_job(session, user_id):
            # Do work with session
            pass

        run_background_job(my_background_job, user_id="123")
    """

    def background_wrapper():
        db = get_session()
        try:
            logger.info("🚀 [Background Job] Thread started, executing job function...")
            job_func(db, *args, **kwargs)
            logger.info("✅ [Background Job] Job function completed successfully")
        except Exception as e:
            logger.error(
                f"❌ [Background Job] Background job failed: {e}",
                exc_info=True,
            )
        finally:
            db.close()
            logger.info("🔒 [Background Job] Database session closed")

    thread = threading.Thread(target=background_wrapper, daemon=False)
    thread.start()
    logger.info(
        f"🚀 [Background Job] Started background thread (thread_id={thread.ident})"
    )


def get_frontend_redirect_url(default: str = "https://localhost:5173/setup") -> str:
    """
    Get frontend redirect URL from environment or use default.

    Args:
        default: Default URL if environment variable not set

    Returns:
        Cleaned redirect URL (stripped, no trailing slash)

    Example:
        redirect_url = get_frontend_redirect_url()
        return redirect(f"{redirect_url}?strava=connected")
    """
    redirect_url = (os.getenv("FRONTEND_REDIRECT") or default).strip().rstrip("/")
    return redirect_url


def is_uuid_format(value: str) -> bool:
    """
    Check if a string matches UUID format.

    Args:
        value: String to check

    Returns:
        True if value matches UUID format, False otherwise

    Example:
        if is_uuid_format(state_or_sub):
            user_id = state_or_sub
    """
    import re

    uuid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    return bool(uuid_pattern.match(value)) if value else False


def normalize_redirect_uri(redirect_uri: str) -> str:
    """
    Normalize Strava redirect URI (auto-fix HTTP to HTTPS for localhost).

    Args:
        redirect_uri: Redirect URI to normalize

    Returns:
        Normalized redirect URI

    Example:
        redirect_uri = normalize_redirect_uri(os.getenv("STRAVA_REDIRECT_URI"))
    """
    redirect_uri = redirect_uri.strip().rstrip(";")

    # Auto-fix HTTP to HTTPS for localhost if app is running on HTTPS
    if redirect_uri.startswith("http://localhost:5000") or redirect_uri.startswith(
        "http://127.0.0.1:5000"
    ):
        redirect_uri = redirect_uri.replace("http://", "https://")

    return redirect_uri
