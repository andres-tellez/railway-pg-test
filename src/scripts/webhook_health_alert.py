#!/usr/bin/env python3
"""
webhook_health_alert.py

Runs webhook health check and sends email alert if issues detected.
Designed to run daily via Railway cron job.

Usage:
    python -m src.scripts.webhook_health_alert
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_local_path = Path(".env.local")
if env_local_path.exists():
    load_dotenv(".env.local")
else:
    load_dotenv(".env.staging")

from src.scripts.check_webhook_health import check_webhook_health


def send_alert(message: str):
    """Send alert via email or webhook"""

    alert_email = os.getenv("ALERT_EMAIL")
    alert_webhook = os.getenv("ALERT_WEBHOOK_URL")  # Discord/Slack webhook

    if alert_webhook:
        # Send to Discord/Slack
        import requests
        try:
            payload = {
                "content": f"🚨 **Webhook Health Alert**\n```\n{message}\n```"
            }
            requests.post(alert_webhook, json=payload, timeout=10)
            print("[ALERT] Sent webhook notification")
        except Exception as e:
            print(f"[ERROR] Failed to send webhook alert: {e}")

    if alert_email:
        # Send email (you'd need to add email service like SendGrid)
        print(f"[ALERT] Would send email to {alert_email}")
        # TODO: Implement email sending

    if not alert_webhook and not alert_email:
        print("[WARN] No alert destinations configured")
        print("       Set ALERT_WEBHOOK_URL or ALERT_EMAIL in Railway")


def main():
    """Run health check and alert on failure"""

    print("Running webhook health check with alerting...")
    print()

    # Run health check
    is_healthy = check_webhook_health()

    if not is_healthy:
        # Health check failed - send alert!
        alert_message = """
WEBHOOK SYSTEM UNHEALTHY

Issues detected in webhook processing.
Check Railway logs or run health check for details:

python -m src.scripts.check_webhook_health

Or visit: https://your-app.up.railway.app/webhooks/strava/status
        """.strip()

        send_alert(alert_message)
        sys.exit(1)
    else:
        print()
        print("[INFO] No alerts needed - system is healthy")
        sys.exit(0)


if __name__ == "__main__":
    main()
