#!/usr/bin/env python3
"""
validate_env_capabilities.py

Comprehensive validation script that tests all app capabilities to verify
environment variables are correct and complete.

This script:
1. Tests database connectivity
2. Tests Auth0 JWKS endpoint accessibility
3. Tests Strava OAuth configuration
4. Tests OpenAI API connectivity
5. Tests Email service configuration (SMTP/SendGrid)
6. Tests webhook configuration
7. Validates internal API keys are set
8. Tests CORS origins parsing
9. Validates business logic config values
10. Checks for missing required variables

Usage:
    python scripts/validate_env_capabilities.py
"""

import os
import sys
import io
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse

# Configure output encoding for Windows (before any print statements)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_local_path = Path(".env.local")
if env_local_path.exists():
    load_dotenv(".env.local")
    print("✅ Loaded .env.local")
else:
    load_dotenv(".env.staging")
    print("✅ Loaded .env.staging")

# Import config after env is loaded
from src.utils.config import config


# Color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(message: str):
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message: str):
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")


def print_info(message: str):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.RESET}")


def print_header(message: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


# Test Results
results: Dict[str, Tuple[bool, str]] = {}


def test_database_connection() -> Tuple[bool, str]:
    """Test database connectivity"""
    print_info("Testing database connection...")

    try:
        from psycopg2 import connect
        from sqlalchemy import create_engine, text

        db_url = config.DATABASE_URL
        if not db_url:
            return False, "DATABASE_URL not set"

        # Test with psycopg2 (like run.py does)
        sanitized_url = (
            db_url.replace("postgresql+psycopg2://", "postgresql://")
            .split("#")[0]
            .strip()
        )
        conn = connect(sanitized_url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()

        # Also test with SQLAlchemy
        engine = create_engine(db_url, connect_args={"sslmode": "require"})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


def test_auth0_jwks() -> Tuple[bool, str]:
    """Test Auth0 JWKS endpoint accessibility"""
    print_info("Testing Auth0 JWKS endpoint...")

    auth0_domain = config.AUTH0_DOMAIN
    if not auth0_domain:
        return False, "AUTH0_DOMAIN not set"

    try:
        jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
        response = requests.get(jwks_url, timeout=5)
        response.raise_for_status()

        data = response.json()
        if "keys" in data and len(data["keys"]) > 0:
            return True, f"Auth0 JWKS accessible (found {len(data['keys'])} keys)"
        else:
            return False, "Auth0 JWKS returned empty keys array"
    except requests.exceptions.RequestException as e:
        return False, f"Auth0 JWKS endpoint not accessible: {str(e)}"
    except Exception as e:
        return False, f"Auth0 JWKS test failed: {str(e)}"


def test_strava_config() -> Tuple[bool, str]:
    """Test Strava OAuth configuration"""
    print_info("Testing Strava OAuth configuration...")

    client_id = config.STRAVA_CLIENT_ID
    client_secret = config.STRAVA_CLIENT_SECRET
    redirect_uri = config.STRAVA_REDIRECT_URI

    issues = []

    if not client_id:
        issues.append("STRAVA_CLIENT_ID not set")
    if not client_secret:
        issues.append("STRAVA_CLIENT_SECRET not set")
    if not redirect_uri:
        issues.append("STRAVA_REDIRECT_URI not set")

    if issues:
        return False, "; ".join(issues)

    # Validate redirect URI format
    try:
        parsed = urlparse(redirect_uri)
        if not parsed.scheme or not parsed.netloc:
            return False, "STRAVA_REDIRECT_URI is not a valid URL"
    except Exception as e:
        return False, f"STRAVA_REDIRECT_URI validation failed: {str(e)}"

    return True, "Strava OAuth configuration valid"


def test_openai_api() -> Tuple[bool, str]:
    """Test OpenAI API connectivity"""
    print_info("Testing OpenAI API...")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, "OPENAI_API_KEY not set"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Make a minimal test call (just to validate API key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'test'"}],
            max_tokens=5,
            timeout=10,
        )

        if response.choices and response.choices[0].message.content:
            return True, "OpenAI API accessible and responding"
        else:
            return False, "OpenAI API returned empty response"
    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "Unauthorized" in error_str:
            return False, "OpenAI API key invalid or unauthorized"
        elif "429" in error_str:
            return False, "OpenAI API rate limit exceeded (try again later)"
        else:
            return False, f"OpenAI API test failed: {str(e)}"


def test_email_config() -> Tuple[bool, str]:
    """Test email service configuration"""
    print_info("Testing email service configuration...")

    try:
        from src.services.email_service import EmailService

        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        sendgrid_from_email = os.getenv("SENDGRID_FROM_EMAIL") or os.getenv(
            "SMTP_FROM_EMAIL"
        )
        sendgrid_from_name = os.getenv("SENDGRID_FROM_NAME") or os.getenv(
            "SMTP_FROM_NAME"
        )
        smtp_host = os.getenv("SMTP_HOST")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")

        is_local = env_local_path.exists()

        # SendGrid REST API is preferred (works on Railway)
        if sendgrid_key:
            if not sendgrid_from_email:
                return (
                    False,
                    "SENDGRID_API_KEY set but SENDGRID_FROM_EMAIL (or SMTP_FROM_EMAIL) missing",
                )
            return True, "SendGrid REST API configured (preferred - works on Railway)"

        # SMTP fallback (may not work on Railway)
        elif smtp_host and smtp_username and smtp_password:
            if not is_local:
                # Railway blocks SMTP - warn but don't fail
                return (
                    True,
                    "⚠️ SMTP configured but SENDGRID_API_KEY missing (SMTP may not work on Railway - use SendGrid REST API instead)",
                )
            return True, "SMTP configured (SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD set)"
        else:
            # For local dev, email is optional; for staging/prod, it's recommended
            if is_local:
                return True, "No email service configured (OK for local dev)"
            else:
                return (
                    False,
                    "No email service configured (recommended for staging/production - set SENDGRID_API_KEY)",
                )
    except Exception as e:
        return False, f"Email service test failed: {str(e)}"


def test_webhook_config() -> Tuple[bool, str]:
    """Test webhook configuration"""
    print_info("Testing webhook configuration...")

    is_local = env_local_path.exists()

    verify_token = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")
    callback_url = os.getenv("WEBHOOK_CALLBACK_URL")

    issues = []

    if not verify_token:
        issues.append("STRAVA_WEBHOOK_VERIFY_TOKEN not set")
    if not callback_url:
        issues.append("WEBHOOK_CALLBACK_URL not set")

    if issues:
        # For local dev, webhooks are optional; for staging/prod, they're required
        if is_local:
            return (
                True,
                f"Webhook config not set (OK for local dev): {', '.join(issues)}",
            )
        else:
            return False, "; ".join(issues)

    # Validate callback URL format
    try:
        parsed = urlparse(callback_url)
        if not parsed.scheme or not parsed.netloc:
            return False, "WEBHOOK_CALLBACK_URL is not a valid URL"
        if parsed.scheme not in ["http", "https"]:
            return False, "WEBHOOK_CALLBACK_URL must use http or https"
    except Exception as e:
        return False, f"WEBHOOK_CALLBACK_URL validation failed: {str(e)}"

    return True, "Webhook configuration valid"


def test_cors_origins() -> Tuple[bool, str]:
    """Test CORS origins parsing"""
    print_info("Testing CORS origins parsing...")

    cors_origins = os.getenv("CORS_ORIGINS", "")
    if not cors_origins:
        return False, "CORS_ORIGINS not set"

    try:
        origin_list = [
            o.strip().strip(";") for o in cors_origins.split(",") if o.strip()
        ]
        if len(origin_list) == 0:
            return False, "CORS_ORIGINS is empty after parsing"

        # Validate each origin is a valid URL
        for origin in origin_list:
            parsed = urlparse(origin)
            if not parsed.scheme or not parsed.netloc:
                return False, f"Invalid CORS origin format: {origin}"

        return True, f"CORS origins parsed successfully ({len(origin_list)} origins)"
    except Exception as e:
        return False, f"CORS origins parsing failed: {str(e)}"


def test_business_logic_config() -> Tuple[bool, str]:
    """Test business logic configuration values"""
    print_info("Testing business logic configuration...")

    min_activities = config.MIN_ACTIVITIES_REQUIRED
    max_activities = config.MAX_ACTIVITIES_TO_DOWNLOAD

    issues = []

    if min_activities < 1:
        issues.append(
            f"MIN_ACTIVITIES_REQUIRED should be >= 1 (currently {min_activities})"
        )
    if max_activities < min_activities:
        issues.append(
            f"MAX_ACTIVITIES_TO_DOWNLOAD ({max_activities}) should be >= MIN_ACTIVITIES_REQUIRED ({min_activities})"
        )

    if issues:
        return False, "; ".join(issues)

    return (
        True,
        f"Business logic config valid (min={min_activities}, max={max_activities})",
    )


def test_required_variables() -> Tuple[bool, str]:
    """Check for all required environment variables"""
    print_info("Checking required environment variables...")

    # Check if we're in local development
    is_local = env_local_path.exists()

    required_vars = {
        "DATABASE_URL": config.DATABASE_URL,
        "AUTH0_DOMAIN": config.AUTH0_DOMAIN,
        "AUTH0_AUDIENCE": config.AUTH0_AUDIENCE,
        "AUTH0_ISSUER": config.AUTH0_ISSUER,
        "STRAVA_CLIENT_ID": config.STRAVA_CLIENT_ID,
        "STRAVA_CLIENT_SECRET": config.STRAVA_CLIENT_SECRET,
        "STRAVA_REDIRECT_URI": config.STRAVA_REDIRECT_URI,
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS"),
    }

    # FRONTEND_REDIRECT is required for staging/production, optional for local
    if not is_local:
        required_vars["FRONTEND_REDIRECT"] = config.FRONTEND_REDIRECT

    missing = [var for var, value in required_vars.items() if not value]

    if missing:
        env_note = " (local dev)" if is_local else " (staging/production)"
        return False, f"Missing required variables{env_note}: {', '.join(missing)}"

    env_note = " (local dev - some vars optional)" if is_local else ""
    return True, f"All required variables present{env_note}"


def test_optional_variables() -> Tuple[bool, str]:
    """Check optional but recommended variables"""
    print_info("Checking optional environment variables...")

    is_local = env_local_path.exists()

    optional_vars = {
        "AUTH0_ALGORITHMS": config.AUTH0_ALGORITHMS or "RS256 (using default)",
        "SESSION_COOKIE_DOMAIN": os.getenv("SESSION_COOKIE_DOMAIN"),
        "SESSION_COOKIE_SECURE": os.getenv("SESSION_COOKIE_SECURE"),
        "SESSION_COOKIE_SAMESITE": os.getenv("SESSION_COOKIE_SAMESITE"),
        "STRAVA_WEBHOOK_VERIFY_TOKEN": os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN"),
        "WEBHOOK_CALLBACK_URL": os.getenv("WEBHOOK_CALLBACK_URL"),
        "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
        "SENDGRID_FROM_EMAIL": os.getenv("SENDGRID_FROM_EMAIL"),
        "SENDGRID_FROM_NAME": os.getenv("SENDGRID_FROM_NAME"),
        "SMTP_HOST": os.getenv("SMTP_HOST"),
    }

    missing = [
        var for var, value in optional_vars.items() if not value or value == "None"
    ]
    present = [var for var, value in optional_vars.items() if value and value != "None"]

    # For staging/prod, SendGrid API key is recommended
    sendgrid_key = optional_vars.get("SENDGRID_API_KEY")
    if not is_local and not sendgrid_key:
        return (
            True,
            f"⚠️ SENDGRID_API_KEY not set (recommended for Railway - SMTP doesn't work)",
        )

    if missing:
        return (
            True,
            f"Optional variables: {len(present)} set, {len(missing)} missing (OK for local dev)",
        )

    return True, f"All optional variables present ({len(present)} set)"


def main():
    """Run all validation tests"""
    print_header("SmartCoach Environment Variable Validation")
    print_info("Testing all app capabilities to validate environment variables...\n")

    # Run all tests
    tests = [
        ("Required Variables", test_required_variables),
        ("Database Connection", test_database_connection),
        ("Auth0 JWKS Endpoint", test_auth0_jwks),
        ("Strava OAuth Config", test_strava_config),
        ("OpenAI API", test_openai_api),
        ("Email Service Config", test_email_config),
        ("Webhook Config", test_webhook_config),
        ("CORS Origins", test_cors_origins),
        ("Business Logic Config", test_business_logic_config),
        ("Optional Variables", test_optional_variables),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            success, message = test_func()
            results[test_name] = (success, message)

            if success:
                print_success(f"{test_name}: {message}")
                passed += 1
            else:
                print_error(f"{test_name}: {message}")
                failed += 1
        except Exception as e:
            print_error(f"{test_name}: Test crashed - {str(e)}")
            results[test_name] = (False, f"Test crashed: {str(e)}")
            failed += 1

    # Summary
    print_header("Validation Summary")
    print(f"Total Tests: {len(tests)}")
    print_success(f"Passed: {passed}")
    if failed > 0:
        print_error(f"Failed: {failed}")
    else:
        print_success("All tests passed!")

    # Detailed results
    print_header("Detailed Results")
    for test_name, (success, message) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name:30} | {message}")

    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
