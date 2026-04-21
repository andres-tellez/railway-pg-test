#!/usr/bin/env python3
"""
Verify Strava OAuth configuration matches expected values.

This script checks:
1. Environment variables are set
2. Scopes requested match expected values
3. Redirect URI format is correct
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to load environment variables from .env.local if it exists
try:
    from dotenv import load_dotenv

    env_path = project_root / ".env.local"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not available, continue without it

# Import config after loading env vars
try:
    from src.utils.config import config
except Exception as e:
    print(f"Warning: Could not import config: {e}")
    print("Continuing with direct environment variable checks...")
    config = None


def verify_oauth_config():
    """Verify OAuth configuration."""
    print("=" * 60)
    print("Strava OAuth Configuration Verification")
    print("=" * 60)
    print()

    issues = []
    warnings = []

    # 1. Check environment variables
    print("1. Environment Variables:")
    print("-" * 60)

    # Get values from config or directly from env
    if config:
        client_id = config.STRAVA_CLIENT_ID
        client_secret = config.STRAVA_CLIENT_SECRET
        redirect_uri = config.STRAVA_REDIRECT_URI
    else:
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        redirect_uri = os.getenv("STRAVA_REDIRECT_URI") or os.getenv("REDIRECT_URI")
    if not client_id:
        issues.append("[ERROR] STRAVA_CLIENT_ID is not set")
        print("   [ERROR] STRAVA_CLIENT_ID: NOT SET")
    else:
        print(
            f"   [OK] STRAVA_CLIENT_ID: {client_id[:8]}...{client_id[-4:] if len(client_id) > 12 else ''}"
        )

    client_secret = config.STRAVA_CLIENT_SECRET
    if not client_secret:
        issues.append("[ERROR] STRAVA_CLIENT_SECRET is not set")
        print("   [ERROR] STRAVA_CLIENT_SECRET: NOT SET")
    else:
        masked_secret = (
            client_secret[:4] + "*" * (len(client_secret) - 8) + client_secret[-4:]
            if len(client_secret) > 8
            else "****"
        )
        print(f"   [OK] STRAVA_CLIENT_SECRET: {masked_secret}")

    redirect_uri = config.STRAVA_REDIRECT_URI
    if not redirect_uri:
        issues.append("[ERROR] STRAVA_REDIRECT_URI is not set")
        print("   [ERROR] STRAVA_REDIRECT_URI: NOT SET")
    else:
        redirect_uri = redirect_uri.strip().rstrip(";")
        print(f"   [OK] STRAVA_REDIRECT_URI: {redirect_uri}")

        # Validate redirect URI format
        is_local = "localhost" in redirect_uri or "127.0.0.1" in redirect_uri
        is_production = "api.smartcoach.dev" in redirect_uri

        if is_local:
            # Local development: allow HTTP
            if not redirect_uri.startswith("http://"):
                issues.append(
                    f"[ERROR] Local redirect URI should use HTTP (not HTTPS): {redirect_uri}"
                )
        elif not is_production:
            # Production must use HTTPS
            if not redirect_uri.startswith("https://"):
                issues.append(
                    f"[ERROR] Production redirect URI must use HTTPS: {redirect_uri}"
                )

        # Check that the path includes /strava/callback
        if "/auth/strava/callback" not in redirect_uri:
            issues.append(
                f"[ERROR] Redirect URI path is incorrect! Should end with /auth/strava/callback"
            )
            issues.append(f"   Current: {redirect_uri}")
            if is_local:
                issues.append(
                    f"   Expected: http://localhost:5000/auth/strava/callback"
                )
            else:
                issues.append(
                    f"   Expected: https://api.smartcoach.dev/auth/strava/callback"
                )
        elif (
            is_production
            and redirect_uri != "https://api.smartcoach.dev/auth/strava/callback"
        ):
            warnings.append(
                f"[WARN] Production redirect URI should be: https://api.smartcoach.dev/auth/strava/callback"
            )
            warnings.append(f"   Current: {redirect_uri}")
        elif is_local and redirect_uri not in [
            "http://localhost:5000/auth/strava/callback",
            "http://127.0.0.1:5000/auth/strava/callback",
        ]:
            # Local dev is fine with either localhost or 127.0.0.1
            pass  # Both are acceptable

    print()

    # 2. Check scopes
    print("2. OAuth Scopes:")
    print("-" * 60)

    # Import the function that generates the auth URL (only if config is available)
    try:
        if not config:
            raise ImportError("Config not available, cannot generate auth URL")
        from src.services.token_service import get_authorization_url

        auth_url = get_authorization_url()
        print(f"   [OK] Authorization URL generated successfully")
        print(f"   URL: {auth_url[:80]}...")

        # Extract scopes from URL
        if "scope=" in auth_url:
            scope_part = auth_url.split("scope=")[1].split("&")[0]
            scopes = scope_part.split(",")
            print(f"   [OK] Scopes requested: {', '.join(scopes)}")

            expected_scopes = {"read", "activity:read_all"}
            actual_scopes = set(scopes)

            if actual_scopes == expected_scopes:
                print("   [OK] Scopes match expected values")
            else:
                missing = expected_scopes - actual_scopes
                extra = actual_scopes - expected_scopes
                if missing:
                    issues.append(f"[ERROR] Missing scopes: {', '.join(missing)}")
                    print(f"   [ERROR] Missing scopes: {', '.join(missing)}")
                if extra:
                    warnings.append(
                        f"[WARN] Extra scopes (may be fine): {', '.join(extra)}"
                    )
                    print(f"   [WARN] Extra scopes: {', '.join(extra)}")
        else:
            issues.append("[ERROR] No scope parameter in authorization URL")
            print("   [ERROR] No scope parameter found in URL")

    except Exception as e:
        issues.append(f"[ERROR] Failed to generate authorization URL: {e}")
        print(f"   [ERROR] Error: {e}")

    print()

    # 3. Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    if not issues and not warnings:
        print("[OK] All checks passed!")
        print()
        print("Next steps:")
        print("1. Verify these settings in Strava Developer Portal:")
        print("   https://www.strava.com/settings/api")
        print(
            "2. Cross-check OAuth settings against docs/API_DOCUMENTATION.md and the Strava developer portal."
        )
        return 0
    else:
        if issues:
            print("[ERROR] Issues found:")
            for issue in issues:
                print(f"   {issue}")
            print()

        if warnings:
            print("[WARN] Warnings:")
            for warning in warnings:
                print(f"   {warning}")
            print()

        print("Please fix issues before proceeding to production.")
        return 1


if __name__ == "__main__":
    exit_code = verify_oauth_config()
    sys.exit(exit_code)
