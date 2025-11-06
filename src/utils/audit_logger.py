"""
Authentication Audit Logger
===========================

Structured logging for authentication events.

Provides centralized audit logging for:
- Security monitoring
- Compliance requirements
- Attack detection
- Forensic analysis
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from flask import request, g
from src.db.db_session import get_session
from src.db.models.auth_audit_log import AuthAuditLog

logger = logging.getLogger(__name__)


def log_auth_event(
    event_type: str,
    event_status: str,
    user_id: Optional[str] = None,
    auth0_sub: Optional[str] = None,
    athlete_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Log an authentication event to audit log.

    Args:
        event_type: Type of event (login, logout, token_refresh, oauth_callback, etc.)
        event_status: Status (success, failure)
        user_id: Internal user_id (UUID)
        auth0_sub: Auth0 subject identifier
        athlete_id: Strava athlete ID
        details: Additional context (dict)
        message: Human-readable message
        ip_address: Client IP address (auto-detected if None)
        user_agent: User agent string (auto-detected if None)
    """
    try:
        # Auto-detect IP and user agent from request if available
        if ip_address is None and request:
            ip_address = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                if request.headers.get("X-Forwarded-For")
                else (request.remote_addr or "unknown")
            )

        if user_agent is None and request:
            user_agent = request.headers.get("User-Agent")

        # Try to get user_id from Flask g if not provided
        if user_id is None and hasattr(g, "user_id"):
            user_id = g.user_id

        # Create audit log entry
        session = get_session()
        try:
            audit_entry = AuthAuditLog(
                user_id=user_id,
                auth0_sub=auth0_sub,
                athlete_id=str(athlete_id) if athlete_id else None,
                event_type=event_type,
                event_status=event_status,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                message=message,
                timestamp=datetime.utcnow(),
            )

            session.add(audit_entry)
            session.commit()

            # Also log to application logger
            log_level = logging.INFO if event_status == "success" else logging.WARNING
            logger.log(
                log_level,
                f"[AUDIT] {event_type} {event_status} - user_id={user_id}, ip={ip_address}",
            )

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to write audit log: {e}", exc_info=True)
        finally:
            session.close()

    except Exception as e:
        # Don't fail the request if audit logging fails
        logger.error(f"Audit logging error: {e}", exc_info=True)


def log_login_success(user_id: str, auth0_sub: str, **kwargs):
    """Log successful login."""
    log_auth_event(
        event_type="login",
        event_status="success",
        user_id=user_id,
        auth0_sub=auth0_sub,
        message=f"User {user_id} logged in successfully",
        **kwargs,
    )


def log_login_failure(
    auth0_sub: Optional[str] = None, reason: Optional[str] = None, **kwargs
):
    """Log failed login attempt."""
    log_auth_event(
        event_type="login",
        event_status="failure",
        auth0_sub=auth0_sub,
        details={"reason": reason} if reason else None,
        message=f"Login failed for {auth0_sub or 'unknown user'}: {reason or 'unknown reason'}",
        **kwargs,
    )


def log_logout(user_id: str, **kwargs):
    """Log logout event."""
    log_auth_event(
        event_type="logout",
        event_status="success",
        user_id=user_id,
        message=f"User {user_id} logged out",
        **kwargs,
    )


def log_token_refresh(
    user_id: str, athlete_id: Optional[str] = None, success: bool = True, **kwargs
):
    """Log token refresh event."""
    log_auth_event(
        event_type="token_refresh",
        event_status="success" if success else "failure",
        user_id=user_id,
        athlete_id=athlete_id,
        message=f"Token refresh {'successful' if success else 'failed'} for user {user_id}",
        **kwargs,
    )


def log_oauth_callback(
    user_id: str,
    athlete_id: str,
    success: bool = True,
    provider: str = "strava",
    **kwargs,
):
    """Log OAuth callback event."""
    log_auth_event(
        event_type="oauth_callback",
        event_status="success" if success else "failure",
        user_id=user_id,
        athlete_id=athlete_id,
        details={"provider": provider},
        message=f"OAuth callback from {provider} {'successful' if success else 'failed'} for user {user_id}",
        **kwargs,
    )


def log_token_revocation(user_id: str, athlete_id: str, **kwargs):
    """Log token revocation event."""
    log_auth_event(
        event_type="token_revocation",
        event_status="success",
        user_id=user_id,
        athlete_id=athlete_id,
        message=f"Tokens revoked for user {user_id}, athlete {athlete_id}",
        **kwargs,
    )
