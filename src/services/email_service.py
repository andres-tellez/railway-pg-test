"""
Email Service
=============

Service for sending email notifications via SendGrid REST API.
Falls back to SMTP if SendGrid API key is not configured (for backward compatibility).

Supports:
- HTML email templates
- Plain text fallback
- SendGrid REST API (preferred - works on Railway)
- SMTP fallback (for other providers)

Author: SmartCoach Development Team
"""

import os
import re
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Try to import SendGrid API (preferred method)
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, Content

    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logger.warning(
        "⚠️  SendGrid library not installed. Install with: pip install sendgrid"
    )

# Try to import SMTP (fallback method)
try:
    import smtplib
    import socket
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False


class EmailService:
    """Service for sending emails via SendGrid REST API or SMTP fallback."""

    @staticmethod
    def get_sendgrid_config() -> Dict[str, Any]:
        """Get SendGrid API configuration from environment variables."""
        api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("SENDGRID_FROM_EMAIL") or os.getenv("SMTP_FROM_EMAIL")
        from_name = os.getenv("SENDGRID_FROM_NAME") or os.getenv(
            "SMTP_FROM_NAME", "SmartCoach"
        )

        return {
            "api_key": api_key,
            "from_email": from_email,
            "from_name": from_name,
        }

    @staticmethod
    def get_smtp_config() -> Dict[str, Any]:
        """Get SMTP configuration from environment variables (fallback)."""
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
        """Check if email service is configured (SendGrid API or SMTP)."""
        # Check SendGrid API first (preferred)
        sendgrid_config = EmailService.get_sendgrid_config()
        if sendgrid_config["api_key"]:
            return True

        # Fallback to SMTP
        if SMTP_AVAILABLE:
            smtp_config = EmailService.get_smtp_config()
            return bool(smtp_config["username"] and smtp_config["password"])

        return False

    @staticmethod
    def send_email_via_sendgrid_api(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email via SendGrid REST API."""
        if not SENDGRID_AVAILABLE:
            logger.error("❌ SendGrid library not available - cannot send email")
            return False

        config = EmailService.get_sendgrid_config()

        if not config["api_key"]:
            logger.error("❌ SENDGRID_API_KEY not configured")
            return False

        if not config["from_email"]:
            logger.error("❌ SENDGRID_FROM_EMAIL not configured")
            return False

        try:
            logger.info("📧 Attempting to send email via SendGrid REST API...")

            # Create plain text version if not provided
            if not text_content:
                text_content = re.sub(r"<[^>]+>", "", html_content)
                text_content = text_content.strip()

            # Create SendGrid message
            message = Mail(
                from_email=Email(config["from_email"], config["from_name"]),
                to_emails=to_email,
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content),
            )

            # Send via SendGrid API
            sg = SendGridAPIClient(config["api_key"])
            response = sg.send(message)

            # Check response status
            if 200 <= response.status_code < 300:
                logger.info(
                    f"✅ Email sent successfully to {to_email} via SendGrid API"
                )
                return True
            else:
                logger.error(
                    f"❌ SendGrid API returned status code {response.status_code}: {response.body}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email} via SendGrid API: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return False

    @staticmethod
    def send_email_via_smtp(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP (fallback method)."""
        if not SMTP_AVAILABLE:
            logger.error("❌ SMTP library not available - cannot send email")
            return False

        config = EmailService.get_smtp_config()

        if not config["username"] or not config["password"]:
            logger.error("❌ SMTP credentials not configured")
            return False

        logger.info(
            f"📧 Attempting to send email via SMTP ({config['host']}:{config['port']})..."
        )

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config['from_name']} <{config['from_email']}>"
            msg["To"] = to_email

            # Create plain text version if not provided
            if not text_content:
                text_content = re.sub(r"<[^>]+>", "", html_content)
                text_content = text_content.strip()

            # Add parts
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")

            msg.attach(part1)
            msg.attach(part2)

            # Send email
            port = config["port"]
            host = config["host"]

            if port == 465:
                # Use SSL connection for port 465
                logger.info(f"🔌 Connecting to {host}:{port} using SSL...")
                with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                    server.login(config["username"], config["password"])
                    server.send_message(msg)
            else:
                # Use STARTTLS for port 587 and others
                logger.info(f"🔌 Connecting to {host}:{port} using STARTTLS...")
                with smtplib.SMTP(host, port, timeout=30) as server:
                    server.starttls()
                    server.login(config["username"], config["password"])
                    server.send_message(msg)

            logger.info(f"✅ Email sent successfully to {to_email} via SMTP")
            return True

        except socket.gaierror as e:
            logger.error(
                f"❌ Failed to send email to {to_email}: DNS resolution failed for {config['host']}: {e}"
            )
            return False
        except socket.timeout as e:
            logger.error(
                f"❌ Failed to send email to {to_email}: Connection timeout to {config['host']}:{config['port']}: {e}"
            )
            logger.error(
                "💡 Railway blocks SMTP ports. Use SendGrid REST API instead (set SENDGRID_API_KEY)"
            )
            return False
        except OSError as e:
            logger.error(
                f"❌ Failed to send email to {to_email}: Network error ({e.errno}): {e}"
            )
            if e.errno == 101:  # Network is unreachable
                logger.error(
                    "💡 Railway blocks SMTP connections. Use SendGrid REST API instead (set SENDGRID_API_KEY)"
                )
            return False
        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                f"❌ Failed to send email to {to_email}: SMTP authentication failed: {e}"
            )
            return False
        except smtplib.SMTPException as e:
            logger.error(f"❌ Failed to send email to {to_email}: SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return False

    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SendGrid REST API (preferred) or SMTP (fallback).

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
                "Set SENDGRID_API_KEY (preferred) or SMTP_USERNAME/SMTP_PASSWORD to enable emails"
            )
            return False

        # Try SendGrid API first (preferred - works on Railway)
        sendgrid_config = EmailService.get_sendgrid_config()
        if sendgrid_config["api_key"]:
            return EmailService.send_email_via_sendgrid_api(
                to_email, subject, html_content, text_content
            )

        # Fallback to SMTP (may not work on Railway)
        if SMTP_AVAILABLE:
            logger.warning(
                "⚠️  Using SMTP fallback. SendGrid API is recommended for Railway (set SENDGRID_API_KEY)"
            )
            return EmailService.send_email_via_smtp(
                to_email, subject, html_content, text_content
            )

        logger.error("❌ No email method available (SendGrid library or SMTP)")
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
