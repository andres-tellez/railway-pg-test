#!/usr/bin/env python3
"""
Script to compare plan generation endpoints (v1 vs v2).

Usage:
    python scripts/compare_endpoints.py

    Or with custom input:
    python scripts/compare_endpoints.py --race-date 2026-02-15 --training-days Mon Wed Thu Sat
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add project root to sys.path so tests/utils can be imported directly
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import requests
from tests.utils.plan_comparison import compare_plan_outputs, compare_with_deepdiff


def get_auth_token() -> str:
    """Get auth token from environment or prompt."""
    token = os.getenv("AUTH_TOKEN")
    if not token:
        print("Warning: AUTH_TOKEN not set. Using empty token (may fail)")
        return ""
    return token


def create_test_request(
    race_date: str = "2026-02-15",
    race_distance: str = "Marathon",
    training_days: list = None,
) -> dict:
    """Create a test plan request."""
    if training_days is None:
        training_days = ["Mon", "Wed", "Thu", "Sat"]

    return {
        "race_date": race_date,
        "race_distance": race_distance,
        "primary_goal": "Just Finish",
        "training_days": training_days,
    }


def call_endpoint(url: str, request_data: dict, token: str) -> dict:
    """Call an endpoint and return response JSON."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=request_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling {url}: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Compare v1 and v2 plan endpoints")
    parser.add_argument(
        "--race-date", default="2026-02-15", help="Race date (YYYY-MM-DD)"
    )
    parser.add_argument("--race-distance", default="Marathon", help="Race distance")
    parser.add_argument(
        "--training-days",
        nargs="+",
        default=["Mon", "Wed", "Thu", "Sat"],
        help="Training days",
    )
    parser.add_argument("--base-url", default="http://localhost:5000", help="Base URL")
    parser.add_argument(
        "--save-responses", action="store_true", help="Save responses to files"
    )

    args = parser.parse_args()

    # Get auth token
    token = get_auth_token()

    # Create test request
    test_request = create_test_request(
        race_date=args.race_date,
        race_distance=args.race_distance,
        training_days=args.training_days,
    )

    print("=" * 80)
    print("Plan Endpoint Comparison Test")
    print("=" * 80)
    print(f"\nTest Request:")
    print(json.dumps(test_request, indent=2))
    print()

    # Call both endpoints
    print("Calling v1 endpoint...")
    v1_url = f"{args.base_url}/api/plan/draft"
    try:
        v1_response = call_endpoint(v1_url, test_request, token)
        print("✅ v1 endpoint responded")
    except Exception as e:
        print(f"❌ v1 endpoint failed: {e}")
        return 1

    print("\nCalling v2 endpoint...")
    v2_url = f"{args.base_url}/api/plan-v2/draft"
    try:
        v2_response = call_endpoint(v2_url, test_request, token)
        print("✅ v2 endpoint responded")
    except Exception as e:
        print(f"❌ v2 endpoint failed: {e}")
        return 1

    # Save responses if requested
    if args.save_responses:
        with open("v1_response.json", "w") as f:
            json.dump(v1_response, f, indent=2)
        with open("v2_response.json", "w") as f:
            json.dump(v2_response, f, indent=2)
        print("\n✅ Responses saved to v1_response.json and v2_response.json")

    # Compare responses
    print("\n" + "=" * 80)
    print("Comparison Results")
    print("=" * 80)

    comparison = compare_plan_outputs(v1_response, v2_response, normalize=True)

    if comparison["identical"]:
        print("\n✅ RESPONSES ARE IDENTICAL!")
        print("\nAll plan data matches between v1 and v2 endpoints.")
    else:
        print("\n❌ DIFFERENCES FOUND:")
        print(f"\nTotal differences: {len(comparison['differences'])}")

        if comparison["differences"]:
            print("\nDifferences:")
            for diff in comparison["differences"][:20]:  # Show first 20
                print(f"  - {diff}")
            if len(comparison["differences"]) > 20:
                print(f"  ... and {len(comparison['differences']) - 20} more")

        if comparison["week_differences"]:
            print("\nWeek-by-week differences:")
            for week_num, week_diffs in comparison["week_differences"].items():
                print(f"  Week {week_num}:")
                for diff in week_diffs:
                    print(f"    - {diff}")

        print(f"\nValidation match: {comparison['validation_match']}")
        print(f"Time assessment match: {comparison['time_assessment_match']}")

        # Show DeepDiff for more details
        print("\n" + "-" * 80)
        print("Detailed Diff (DeepDiff):")
        print("-" * 80)
        deep_diff = compare_with_deepdiff(v1_response, v2_response, normalize=True)
        if deep_diff:
            print(json.dumps(deep_diff.to_dict(), indent=2))
        else:
            print("No differences found with DeepDiff (after normalization)")

    print("\n" + "=" * 80)

    return 0 if comparison["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
