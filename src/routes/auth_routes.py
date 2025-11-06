"""
auth_routes.py

Authentication & OAuth Routes (Main Module)
===========================================

This module imports and registers all authentication-related blueprints.

The authentication routes have been split into separate modules:
- auth0_routes.py - Auth0 login/callback
- strava_routes.py - Strava OAuth flow
- token_routes.py - Token refresh/logout
- auth_debug_routes.py - Debug utilities

This file maintains backward compatibility by exporting a combined auth_bp.
"""

from flask import Blueprint
import logging

# Import all auth blueprints
from src.routes.auth0_routes import auth0_bp
from src.routes.strava_routes import strava_bp, strava_connection_bp
from src.routes.token_routes import token_bp
from src.routes.auth_debug_routes import auth_debug_bp

# Create main auth blueprint for backward compatibility
auth_bp = Blueprint("auth", __name__)

# Register all auth blueprints with the main auth blueprint
# This maintains backward compatibility while allowing modular organization


def register_auth_blueprints(app):
    """
    Register all authentication blueprints with the Flask app.

    This function should be called from app.py to register:
    - auth0_bp (Auth0 login/callback)
    - strava_bp (Strava OAuth flow)
    - token_bp (Token management)
    - auth_debug_bp (Debug utilities) - Only in development if enabled
    """
    import os

    app.register_blueprint(auth0_bp)
    app.register_blueprint(strava_bp)
    app.register_blueprint(strava_connection_bp)  # Connection management routes
    app.register_blueprint(token_bp)

    # Only register debug endpoints in development and if explicitly enabled
    # This prevents debug endpoints from being exposed in production
    is_production = os.getenv("FLASK_ENV") == "production"
    enable_debug = os.getenv("ENABLE_DEBUG_ROUTES", "0") == "1"

    if not is_production and enable_debug:
        app.register_blueprint(auth_debug_bp)
        logger = logging.getLogger(__name__)
        logger.warning("⚠️ Debug routes enabled - should not be used in production")
    elif is_production:
        logger = logging.getLogger(__name__)
        logger.info("🔒 Debug routes disabled in production (security best practice)")


# Export token utilities for backward compatibility and tests
import src.services.token_service as token_service

delete_athlete_tokens = token_service.delete_athlete_tokens
refresh_token_if_expired = token_service.refresh_token_if_expired
store_tokens_from_callback = token_service.store_tokens_from_callback
