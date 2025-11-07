#!/usr/bin/env python3
"""
manage_webhook_subscription.py

Strava Webhook Subscription Management
=======================================

This script helps you create, view, and delete Strava webhook subscriptions.

Usage:
    # View current subscription
    python -m src.scripts.manage_webhook_subscription view

    # Create new subscription
    python -m src.scripts.manage_webhook_subscription create

    # Delete subscription
    python -m src.scripts.manage_webhook_subscription delete <subscription_id>

Environment Variables Required:
    - STRAVA_CLIENT_ID: Your Strava app client ID
    - STRAVA_CLIENT_SECRET: Your Strava app client secret
    - STRAVA_WEBHOOK_VERIFY_TOKEN: Secret token for webhook verification
    - WEBHOOK_CALLBACK_URL: Your public webhook endpoint URL
      Example: https://your-app.up.railway.app/webhooks/strava

Setup Instructions:
1. Set environment variables (add to Railway or .env file)
2. Run 'create' command to register webhook with Strava
3. Strava will send test event to verify endpoint
4. Once verified, you'll start receiving real-time notifications!
"""

import os
import sys
import requests
import argparse


def get_strava_config():
    """Get Strava configuration from environment variables"""
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    verify_token = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")
    callback_url = os.getenv("WEBHOOK_CALLBACK_URL")

    if not all([client_id, client_secret, verify_token, callback_url]):
        print("❌ Missing required environment variables:")
        if not client_id:
            print("   - STRAVA_CLIENT_ID")
        if not client_secret:
            print("   - STRAVA_CLIENT_SECRET")
        if not verify_token:
            print("   - STRAVA_WEBHOOK_VERIFY_TOKEN")
        if not callback_url:
            print("   - WEBHOOK_CALLBACK_URL")
        sys.exit(1)

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "verify_token": verify_token,
        "callback_url": callback_url,
    }


def view_subscription():
    """View current webhook subscription"""
    config = get_strava_config()

    print("\n🔍 Checking for existing webhook subscriptions...")
    print(f"   Client ID: {config['client_id']}")

    url = "https://www.strava.com/api/v3/push_subscriptions"
    params = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        subscriptions = response.json()

        if not subscriptions:
            print("\n✅ No active webhook subscriptions found.")
            print("\nTo create one, run:")
            print("   python -m src.scripts.manage_webhook_subscription create")
            return

        print(f"\n✅ Found {len(subscriptions)} subscription(s):\n")
        for sub in subscriptions:
            print(f"   ID: {sub['id']}")
            print(f"   Callback URL: {sub['callback_url']}")
            print(f"   Created: {sub.get('created_at', 'N/A')}")
            print()

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Error fetching subscriptions: {e}")
        print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


def create_subscription():
    """Create a new webhook subscription"""
    config = get_strava_config()

    print("\n📝 Creating new webhook subscription...")
    print(f"   Callback URL: {config['callback_url']}")
    print(f"   Verify Token: {config['verify_token'][:10]}...")

    # First check if subscription already exists
    url = "https://www.strava.com/api/v3/push_subscriptions"
    params = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        existing = response.json()

        if existing:
            print("\n⚠️ Subscription already exists!")
            for sub in existing:
                print(f"   ID: {sub['id']}")
                print(f"   URL: {sub['callback_url']}")
            print("\nTo delete and recreate, run:")
            print(f"   python -m src.scripts.manage_webhook_subscription delete {existing[0]['id']}")
            return

    except Exception as e:
        print(f"⚠️ Could not check existing subscriptions: {e}")

    # Create new subscription
    data = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "callback_url": config["callback_url"],
        "verify_token": config["verify_token"],
    }

    try:
        print("\n🚀 Sending subscription request to Strava...")
        response = requests.post(url, data=data)
        response.raise_for_status()

        result = response.json()

        print("\n✅ Webhook subscription created successfully!")
        print(f"   Subscription ID: {result['id']}")
        print(f"   Callback URL: {result.get('callback_url')}")
        print("\n🎉 Your app will now receive real-time activity notifications!")
        print("\nTest it by:")
        print("   1. Opening Strava app on your phone")
        print("   2. Recording a short run")
        print("   3. Checking your webhook status endpoint:")
        print(f"      {config['callback_url'].replace('/strava', '/strava/status')}")

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Error creating subscription: {e}")
        print(f"   Status Code: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        print("\nPossible issues:")
        print("   - Your webhook endpoint might not be publicly accessible")
        print("   - The endpoint might not be responding to verification challenge")
        print("   - Check your server logs for verification request")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


def delete_subscription(subscription_id):
    """Delete a webhook subscription"""
    config = get_strava_config()

    print(f"\n🗑️ Deleting webhook subscription {subscription_id}...")

    url = f"https://www.strava.com/api/v3/push_subscriptions/{subscription_id}"
    params = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
    }

    try:
        response = requests.delete(url, params=params)
        response.raise_for_status()

        print("\n✅ Webhook subscription deleted successfully!")

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Error deleting subscription: {e}")
        print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


def main():
    """Main command-line interface"""
    parser = argparse.ArgumentParser(
        description="Manage Strava webhook subscriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View current subscription
  python -m src.scripts.manage_webhook_subscription view

  # Create new subscription
  python -m src.scripts.manage_webhook_subscription create

  # Delete subscription
  python -m src.scripts.manage_webhook_subscription delete 12345
        """,
    )

    parser.add_argument(
        "action",
        choices=["view", "create", "delete"],
        help="Action to perform",
    )

    parser.add_argument(
        "subscription_id",
        nargs="?",
        type=int,
        help="Subscription ID (required for delete action)",
    )

    args = parser.parse_args()

    # Validate delete requires subscription_id
    if args.action == "delete" and not args.subscription_id:
        parser.error("delete action requires subscription_id")

    # Execute action
    if args.action == "view":
        view_subscription()
    elif args.action == "create":
        create_subscription()
    elif args.action == "delete":
        delete_subscription(args.subscription_id)


if __name__ == "__main__":
    main()
