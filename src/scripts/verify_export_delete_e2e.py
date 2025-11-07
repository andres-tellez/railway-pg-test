#!/usr/bin/env python
"""
verify_export_delete_e2e.py

End-to-End Verification Script for Export/Delete Flows
======================================================

This script verifies that the export and delete endpoints work correctly
in staging/production environments.

Usage:
    python -m src.scripts.verify_export_delete_e2e

Requirements:
    - Environment variables: AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET
    - Test user credentials (or use staging test account)
    - API endpoint accessible (staging or production URL)
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment
env_path = Path(".env.staging") if Path(".env.staging").exists() else Path(".env.local")
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ Loaded environment from {env_path}")
else:
    print("⚠️  No .env.staging or .env.local found, using system environment")

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL") or os.getenv(
    "FRONTEND_REDIRECT", "https://api.smartcoach.dev"
)
if API_BASE_URL.startswith("https://app."):
    API_BASE_URL = API_BASE_URL.replace("app.", "api.")

print(f"🔗 API Base URL: {API_BASE_URL}")


class Colors:
    """Terminal colors for output"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_success(message):
    """Print success message in green"""
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")


def print_error(message):
    """Print error message in red"""
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")


def print_warning(message):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")


def print_info(message):
    """Print info message in blue"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.RESET}")


def get_auth_token(email, password):
    """
    Get Auth0 JWT token for test user.

    Note: This requires Auth0 test credentials. In production, you might
    need to use a different authentication method or test user credentials.
    """
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    if not auth0_domain:
        print_warning("AUTH0_DOMAIN not set - skipping token generation")
        print_info(
            "You can manually provide a token via AUTH_TOKEN environment variable"
        )
        return os.getenv("AUTH_TOKEN")

    # For manual testing, you can set AUTH_TOKEN directly
    manual_token = os.getenv("AUTH_TOKEN")
    if manual_token:
        print_info("Using AUTH_TOKEN from environment")
        return manual_token

    print_warning("Automatic token generation not implemented")
    print_info("Set AUTH_TOKEN environment variable with a valid JWT token")
    return None


def test_export_data(token):
    """Test the export data endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: Export User Data")
    print("=" * 60)

    url = f"{API_BASE_URL}/api/user/export-data"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        print_info(f"Requesting: GET {url}")
        response = requests.get(url, headers=headers, timeout=30)

        print_info(f"Response Status: {response.status_code}")

        if response.status_code == 401:
            print_error("Authentication failed - invalid token")
            return False

        if response.status_code != 200:
            print_error(f"Export failed: {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return False

        data = response.json()

        # Verify export structure
        required_keys = ["export_date", "user_id", "data", "summary"]
        missing_keys = [key for key in required_keys if key not in data]

        if missing_keys:
            print_error(f"Missing required keys in export: {missing_keys}")
            return False

        print_success("Export response structure is valid")

        # Verify data sections
        data_sections = data.get("data", {})
        print_info(f"Data sections found: {list(data_sections.keys())}")

        # Check identity
        if "identity" in data_sections:
            identity = data_sections["identity"]
            print_success(f"Identity data present: {list(identity.keys())}")
        else:
            print_warning(
                "No identity data found (user may not have completed profile)"
            )

        # Check profile
        if "profile" in data_sections:
            profile = data_sections["profile"]
            print_success(f"Profile data present: {list(profile.keys())}")
        else:
            print_warning(
                "No profile data found (user may not have completed onboarding)"
            )

        # Check activities
        activities = data_sections.get("activities", [])
        activity_count = len(activities)
        print_info(f"Activities exported: {activity_count}")

        if activity_count > 0:
            sample_activity = activities[0]
            required_activity_fields = [
                "activity_id",
                "name",
                "type",
                "start_date",
                "distance",
            ]
            missing_fields = [
                field
                for field in required_activity_fields
                if field not in sample_activity
            ]
            if missing_fields:
                print_error(f"Missing required activity fields: {missing_fields}")
                return False
            print_success("Activity data structure is valid")

        # Check Strava connections
        strava_connections = data_sections.get("strava_connections", [])
        print_info(f"Strava connections: {len(strava_connections)}")

        # Save export to file
        export_file = f"export_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(export_file, "w") as f:
            json.dump(data, f, indent=2)
        print_success(f"Export saved to: {export_file}")

        # Verify summary
        summary = data.get("summary", {})
        print_info(f"Summary: {summary}")

        if summary.get("total_activities") != activity_count:
            print_error(
                f"Summary mismatch: total_activities={summary.get('total_activities')}, "
                f"actual={activity_count}"
            )
            return False

        print_success("Export test passed!")
        return True

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON response: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_delete_account(token):
    """Test the delete account endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Delete User Account")
    print("=" * 60)

    print_warning("⚠️  WARNING: This will permanently delete the test user's account!")
    print_warning("⚠️  Only use this with a dedicated test account!")

    confirm = input("\nType 'DELETE' to confirm account deletion: ")
    if confirm != "DELETE":
        print_warning("Deletion cancelled")
        return False

    url = f"{API_BASE_URL}/api/user/delete-account"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        print_info(f"Requesting: DELETE {url}")
        response = requests.delete(url, headers=headers, timeout=30)

        print_info(f"Response Status: {response.status_code}")

        if response.status_code == 401:
            print_error("Authentication failed - invalid token")
            return False

        if response.status_code != 200:
            print_error(f"Delete failed: {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return False

        data = response.json()

        # Verify response structure
        if "success" not in data or not data["success"]:
            print_error("Delete response indicates failure")
            return False

        print_success("Delete response indicates success")

        # Verify deletion summary
        deletions = data.get("deleted", {})
        print_info(f"Deletion summary: {deletions}")

        # Check that deletion counts are reported
        expected_keys = [
            "activities",
            "plans",
            "athlete_links",
            "tokens",
            "profile",
            "identity",
        ]
        for key in expected_keys:
            if key in deletions:
                count = deletions[key]
                print_info(f"  {key}: {count}")

        # Verify timestamp
        if "timestamp" in data:
            print_success(f"Deletion timestamp: {data['timestamp']}")

        # Verify account is actually deleted by trying to access it
        print_info("Verifying account is actually deleted...")

        # Try to get user info (should fail)
        verify_url = f"{API_BASE_URL}/api/user"
        verify_response = requests.get(verify_url, headers=headers, timeout=10)

        if verify_response.status_code == 404 or verify_response.status_code == 401:
            print_success("Account deletion verified - user no longer accessible")
        else:
            print_warning(
                f"Account may still be accessible (status: {verify_response.status_code})"
            )

        print_success("Delete test passed!")
        return True

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON response: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_authentication_required():
    """Test that endpoints require authentication"""
    print("\n" + "=" * 60)
    print("TEST 3: Authentication Requirements")
    print("=" * 60)

    endpoints = [
        ("GET", "/api/user/export-data"),
        ("DELETE", "/api/user/delete-account"),
    ]

    all_passed = True

    for method, endpoint in endpoints:
        url = f"{API_BASE_URL}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, timeout=10)
            else:
                continue

            if response.status_code == 401:
                print_success(f"{method} {endpoint} - Authentication required ✅")
            else:
                print_error(
                    f"{method} {endpoint} - Missing auth check "
                    f"(status: {response.status_code})"
                )
                all_passed = False

        except Exception as e:
            print_error(f"{method} {endpoint} - Request failed: {e}")
            all_passed = False

    return all_passed


def main():
    """Main verification function"""
    print("\n" + "=" * 60)
    print("Export/Delete End-to-End Verification")
    print("=" * 60)
    print(f"Environment: {os.getenv('FLASK_ENV', 'production')}")
    print(f"API URL: {API_BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")

    # Get authentication token
    token = get_auth_token(None, None)

    if not token:
        print_error("No authentication token available")
        print_info("\nTo run full tests:")
        print_info("1. Set AUTH_TOKEN environment variable with a valid JWT")
        print_info("2. Or implement Auth0 token generation in this script")
        print_info("\nRunning authentication requirement tests only...")

        # Test auth requirements without token
        auth_test = test_authentication_required()
        sys.exit(0 if auth_test else 1)

    # Run tests
    results = {
        "export": False,
        "delete": False,
        "auth": False,
    }

    # Test 1: Export
    results["export"] = test_export_data(token)

    # Test 2: Delete (only if export passed)
    if results["export"]:
        results["delete"] = test_delete_account(token)
    else:
        print_warning("Skipping delete test (export test failed)")

    # Test 3: Authentication
    results["auth"] = test_authentication_required()

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.upper():<15} {status}")

    all_passed = all(results.values())

    if all_passed:
        print_success("\nAll tests passed! ✅")
        sys.exit(0)
    else:
        print_error("\nSome tests failed! ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
