"""
Email Service
=============

Service for sending email notifications via SMTP.

Supports:
- HTML email templates
- Plain text fallback
- SMTP configuration via environment variables

Author: SmartCoach Development Team
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    @staticmethod
    def get_smtp_config() -> Dict[str, Any]:
        """Get SMTP configuration from environment variables."""
        return {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME"),
            "password": os.getenv("SMTP_PASSWORD"),
            "from_email": os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USERNAME")),
            "from_name": os.getenv("SMTP_FROM_NAME", "SmartCoach"),
        }

    @staticmethod
    def is_configured() -> bool:
        """Check if email service is configured."""
        config = EmailService.get_smtp_config()
        return bool(config["username"] and config["password"])

    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Optional plain text body (auto-generated if not provided)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not EmailService.is_configured():
            logger.warning("Email service not configured - skipping send")
            logger.warning(
                "Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD to enable emails"
            )
            return False

        config = EmailService.get_smtp_config()

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config['from_name']} <{config['from_email']}>"
            msg["To"] = to_email

            # Create plain text version if not provided
            if not text_content:
                # Simple HTML to text conversion (remove HTML tags)
                import re

                text_content = re.sub(r"<[^>]+>", "", html_content)
                text_content = text_content.strip()

            # Add parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")

            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(config["host"], config["port"]) as server:
                server.starttls()
                server.login(config["username"], config["password"])
                server.send_message(msg)

            logger.info(f"✅ Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False

    @staticmethod
    def send_weekly_update_email(
        to_email: str,
        user_name: Optional[str],
        week_num: int,
        week_start: str,
        workout_changes: List[Dict[str, Any]],
        metrics_refresh_success: bool,
        metrics_refresh_message: str,
    ) -> bool:
        """
        Send weekly update email with workout changes and metrics validation.

        Args:
            to_email: Recipient email
            user_name: Optional user name for personalization
            week_num: Week number that was rebuilt
            week_start: Week start date (YYYY-MM-DD)
            workout_changes: List of workout change dictionaries
            metrics_refresh_success: Whether metrics refresh succeeded
            metrics_refresh_message: Metrics refresh status message

        Returns:
            True if email sent successfully
        """
        display_name = user_name or "Runner"

        # Build workout changes HTML
        changes_html = ""
        if workout_changes:
            changes_html = "<h3>📊 Workout Updates</h3><table style='border-collapse: collapse; width: 100%; margin: 20px 0;'>"
            changes_html += (
                "<tr style='background-color: #f0f0f0;'><th style='padding: 8px; border: 1px solid #ddd;'>Date</th>"
                "<th style='padding: 8px; border: 1px solid #ddd;'>Workout</th>"
                "<th style='padding: 8px; border: 1px solid #ddd;'>Changes</th></tr>"
            )

            for change in workout_changes:
                date_str = change.get("date", "")
                workout_type = change.get("workout_type", "")
                miles = change.get("miles", 0)
                changes = change.get("changes", [])

                changes_cells = ""
                if changes:
                    changes_list = "<ul style='margin: 0; padding-left: 20px;'>"
                    for ch in changes:
                        field = ch.get("field", "")
                        before = ch.get("before", "")
                        after = ch.get("after", "")
                        changes_list += (
                            f"<li><strong>{field}:</strong> {before} → {after}</li>"
                        )
                    changes_list += "</ul>"
                    changes_cells = changes_list
                else:
                    changes_cells = "<em>No changes (already up to date)</em>"

                changes_html += (
                    f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{date_str}</td>"
                    f"<td style='padding: 8px; border: 1px solid #ddd;'><strong>{workout_type}</strong><br/>{miles} miles</td>"
                    f"<td style='padding: 8px; border: 1px solid #ddd;'>{changes_cells}</td></tr>"
                )

            changes_html += "</table>"
        else:
            changes_html = "<p><em>No workout changes this week</em></p>"

        # Metrics validation status
        metrics_status = (
            "✅ <strong>Success:</strong> "
            if metrics_refresh_success
            else "❌ <strong>Warning:</strong> "
        )
        metrics_status += metrics_refresh_message

        # HTML email template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ background-color: #f9f9f9; padding: 20px; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
        .metrics-box {{ background-color: {'#d4edda' if metrics_refresh_success else '#f8d7da'};
                        padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏃 SmartCoach Weekly Update</h1>
        </div>
        <div class="content">
            <h2>Hi {display_name}!</h2>
            <p>Your training plan for <strong>Week {week_num}</strong> (starting {week_start}) has been updated based on your recent performance.</p>

            {changes_html}

            <div class="metrics-box">
                <h3>📈 Metrics Dashboard Status</h3>
                <p>{metrics_status}</p>
            </div>

            <p style="margin-top: 30px;">
                <strong>What's Next?</strong><br/>
                Check out your updated workouts in the SmartCoach app. Your plan has been automatically adjusted to keep you on track toward your race goal.
            </p>
        </div>
        <div class="footer">
            <p>SmartCoach - Your AI Running Coach</p>
            <p>This is an automated notification. You're receiving this because you have an active training plan.</p>
        </div>
    </div>
</body>
</html>
        """

        subject = f"SmartCoach: Week {week_num} Update Ready"

        return EmailService.send_email(to_email, subject, html_content)
