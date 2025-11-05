"""
Email Service
=============

Service for sending email notifications via SendGrid REST API.

Supports:
- HTML email templates
- Plain text fallback
- SendGrid REST API (required - works on Railway)

Note: SMTP fallback has been removed. SendGrid REST API is required.

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

# SMTP fallback removed - SendGrid REST API is required


class EmailService:
    """Service for sending emails via SendGrid REST API (required)."""

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
        """Get SMTP configuration from environment variables (fallback).

        Note: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD are no longer used.
        Only SMTP_FROM_EMAIL and SMTP_FROM_NAME are kept as fallbacks for SendGrid.
        """
        return {
            "from_email": os.getenv("SMTP_FROM_EMAIL"),
            "from_name": os.getenv("SMTP_FROM_NAME", "SmartCoach"),
        }

    @staticmethod
    def is_configured() -> bool:
        """Check if email service is configured (SendGrid API required)."""
        # Check SendGrid API (required)
        sendgrid_config = EmailService.get_sendgrid_config()
        if sendgrid_config["api_key"]:
            return True

        # SMTP fallback removed - SendGrid REST API is required
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
                error_body = (
                    response.body.decode("utf-8")
                    if response.body
                    else "No error details"
                )
                logger.error(
                    f"❌ SendGrid API returned status code {response.status_code}"
                )
                logger.error(f"Error details: {error_body}")

                # Provide specific guidance for common errors
                if response.status_code == 403:
                    logger.error("💡 403 Forbidden usually means:")
                    logger.error("   1. Sender email not verified in SendGrid")
                    logger.error("   2. API key doesn't have 'Mail Send' permissions")
                    logger.error(
                        "   3. Check SendGrid dashboard → Settings → Sender Authentication"
                    )
                elif response.status_code == 401:
                    logger.error(
                        "💡 401 Unauthorized - check that SENDGRID_API_KEY is correct"
                    )
                elif response.status_code == 400:
                    logger.error("💡 400 Bad Request - check email format and content")

                return False

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email} via SendGrid API: {e}")
            import traceback

            logger.error(traceback.format_exc())

            # Check if it's a 403 error specifically
            if "403" in str(e) or "Forbidden" in str(e):
                logger.error(
                    "💡 403 Forbidden - verify sender email in SendGrid dashboard"
                )

            return False

    @staticmethod
    def send_email_via_smtp(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP (removed - use SendGrid REST API instead)."""
        logger.error("❌ SMTP fallback removed - SendGrid REST API is required")
        logger.error("💡 Set SENDGRID_API_KEY to enable email sending")
        return False

    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SendGrid REST API (required).

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
            logger.warning("Set SENDGRID_API_KEY to enable emails")
            return False

        # Use SendGrid REST API (required)
        sendgrid_config = EmailService.get_sendgrid_config()
        if sendgrid_config["api_key"]:
            return EmailService.send_email_via_sendgrid_api(
                to_email, subject, html_content, text_content
            )

        logger.error("❌ SENDGRID_API_KEY not configured - email sending disabled")
        logger.error("💡 Set SENDGRID_API_KEY to enable email sending")
        return False

    @staticmethod
    def send_weekly_update_email(
        to_email: str,
        user_name: Optional[str],
        week_num: int,
        week_start: str,
        this_week_actual_runs: Dict[str, Optional[Dict[str, Any]]],
        next_week_original_plan: List[Dict[str, Any]],
        next_week_updated_plan: List[Dict[str, Any]],
        metrics_refresh_success: bool,
        metrics_refresh_message: str,
    ) -> bool:
        """
        Send weekly update email with workout comparison table.

        Args:
            to_email: Recipient email
            user_name: Optional user name for personalization
            week_num: Week number that was rebuilt
            week_start: Week start date (YYYY-MM-DD)
            this_week_actual_runs: Dict of actual runs from THIS WEEK by day
            next_week_original_plan: List of original planned workouts before rebuild
            next_week_updated_plan: List of updated planned workouts after rebuild
            metrics_refresh_success: Whether metrics refresh succeeded
            metrics_refresh_message: Metrics refresh status message

        Returns:
            True if email sent successfully
        """
        display_name = user_name or "Runner"

        # Build comparison table with days of week across top
        from src.utils.date_helpers import DAY_NAMES_FULL

        day_names = DAY_NAMES_FULL

        # Helper function to format pace from target dict
        def format_pace_from_target(target: Any) -> str:
            """Format pace from target dict (low/high in seconds) or string."""
            if isinstance(target, dict):
                low_sec = target.get("low", 0)
                high_sec = target.get("high", 0)
                if low_sec and high_sec:
                    # Convert seconds to MM:SS/mi
                    low_min = int(low_sec // 60)
                    low_sec_rem = int(low_sec % 60)
                    high_min = int(high_sec // 60)
                    high_sec_rem = int(high_sec % 60)
                    if low_min == high_min and low_sec_rem == high_sec_rem:
                        return f"{low_min}:{low_sec_rem:02d}/mi"
                    return (
                        f"{low_min}:{low_sec_rem:02d}-{high_min}:{high_sec_rem:02d}/mi"
                    )
            elif isinstance(target, str):
                return target
            return ""

        # Helper function to format segment breakdown
        def format_segment_breakdown(workout: Optional[Dict[str, Any]]) -> str:
            """Format detailed segment breakdown from workout."""
            if not workout:
                return ""

            # Try to get segments from workout
            segments = workout.get("segments")
            if not segments:
                return ""

            # Handle segments in different formats
            if isinstance(segments, str):
                import json

                try:
                    segments = json.loads(segments)
                except:
                    return ""
            elif not isinstance(segments, dict):
                return ""

            steps = segments.get("steps", [])
            if not steps:
                return ""

            # Build segment breakdown
            breakdown = "<div style='margin-top: 8px; font-size: 11px; border-top: 1px solid #ddd; padding-top: 5px;'>"
            for i, step in enumerate(steps):
                name = step.get("name", "Segment")
                value = step.get("value", 0)
                duration_type = step.get("durationType", "DISTANCE")
                target = step.get("target", {})
                intensity = step.get("intensity", "")

                # Format value
                if duration_type == "DISTANCE":
                    value_str = f"{value:.2f} mi" if value > 0 else ""
                else:
                    value_str = f"{value} {duration_type.lower()}"

                # Format pace
                pace_str = format_pace_from_target(target)
                if pace_str:
                    pace_str = f" @ {pace_str}"

                # Build segment line
                segment_line = f"{name}"
                if value_str:
                    segment_line += f" {value_str}"
                if pace_str:
                    segment_line += pace_str
                if intensity and intensity != "EASY":
                    segment_line += f" ({intensity})"

                breakdown += f"• {segment_line}<br/>"

            breakdown += "</div>"
            return breakdown

        # Helper function to format workout details
        def format_workout_details(workout: Optional[Dict[str, Any]]) -> str:
            """Format workout details for display with segment breakdown."""
            if not workout:
                return "<em>Rest</em>"

            miles = workout.get("miles", 0) or workout.get("distance", 0)
            workout_type = workout.get("workout_type", "Run")
            # Get pace from either 'pace' (actual runs) or 'target_zone' (planned)
            pace = workout.get("pace") or workout.get("target_zone", "")
            desc = workout.get("description") or workout.get("name", "")

            details = f"<strong>{workout_type}</strong><br/>"
            if miles > 0:
                details += f"{miles:.1f} mi"
            else:
                details += f"{workout_type}"

            if pace and pace != "N/A" and pace:
                details += f"<br/><small>@{pace}</small>"
            if desc:
                # Truncate description if too long
                desc_short = desc[:30] + "..." if len(desc) > 30 else desc
                details += f"<br/><small style='color: #666;'>{desc_short}</small>"

            # Add segment breakdown if available (for planned workouts)
            segment_breakdown = format_segment_breakdown(workout)
            if segment_breakdown:
                details += segment_breakdown

            return details

        # Helper function to get workout for a day
        def get_workout_for_day(
            workouts: List[Dict[str, Any]], day_name: str
        ) -> Optional[Dict[str, Any]]:
            """Get workout for a specific day from list."""
            for workout in workouts:
                if workout.get("day") == day_name:
                    return workout
            return None

        # Build table HTML
        table_html = "<h3>📊 Weekly Comparison</h3>"
        table_html += "<table style='border-collapse: collapse; width: 100%; margin: 20px 0; background-color: white;'>"

        # Header row with days of week
        table_html += "<tr style='background-color: #4CAF50; color: white;'>"
        table_html += "<th style='padding: 12px; border: 1px solid #ddd; text-align: left;'>Week</th>"
        for day_name in day_names:
            table_html += f"<th style='padding: 12px; border: 1px solid #ddd; text-align: center;'>{day_name[:3]}</th>"
        table_html += "</tr>"

        # Row 1: This week actual runs
        table_html += "<tr style='background-color: #e3f2fd;'>"
        table_html += "<td style='padding: 10px; border: 1px solid #ddd; font-weight: bold;'>This Week<br/>Actual Runs</td>"
        for day_name in day_names:
            run_data = this_week_actual_runs.get(day_name)
            if run_data:
                table_html += f"<td style='padding: 10px; border: 1px solid #ddd;'>{format_workout_details(run_data)}</td>"
            else:
                table_html += "<td style='padding: 10px; border: 1px solid #ddd;'><em>Rest</em></td>"
        table_html += "</tr>"

        # Row 2: Next week original plan
        table_html += "<tr style='background-color: #f9f9f9;'>"
        table_html += "<td style='padding: 10px; border: 1px solid #ddd; font-weight: bold;'>Next Week<br/>Original Plan</td>"
        for day_name in day_names:
            workout = get_workout_for_day(next_week_original_plan, day_name)
            table_html += f"<td style='padding: 10px; border: 1px solid #ddd;'>{format_workout_details(workout)}</td>"
        table_html += "</tr>"

        # Row 3: Next week updated plan
        table_html += "<tr style='background-color: #fff3cd;'>"
        table_html += "<td style='padding: 10px; border: 1px solid #ddd; font-weight: bold;'>Next Week<br/>Updated Plan</td>"
        for day_name in day_names:
            workout = get_workout_for_day(next_week_updated_plan, day_name)
            # Check if this day changed from original (compare key fields)
            original_workout = get_workout_for_day(next_week_original_plan, day_name)
            is_changed = False
            if workout and original_workout:
                # Compare key fields to determine if changed
                is_changed = (
                    workout.get("miles") != original_workout.get("miles")
                    or workout.get("workout_type")
                    != original_workout.get("workout_type")
                    or workout.get("target_zone") != original_workout.get("target_zone")
                    or workout.get("target_hr") != original_workout.get("target_hr")
                    or workout.get("description") != original_workout.get("description")
                )
            elif workout != original_workout:  # One is None and other is not
                is_changed = True

            cell_style = "background-color: #ffeb3b;" if is_changed else ""
            table_html += f"<td style='padding: 10px; border: 1px solid #ddd; {cell_style}'>{format_workout_details(workout)}</td>"
        table_html += "</tr>"

        table_html += "</table>"

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
            <p>The table below shows:</p>
            <ul>
                <li><strong>This Week Actual Runs:</strong> What you actually ran this week (Mon-Sun)</li>
                <li><strong>Next Week Original Plan:</strong> What was originally planned for next week</li>
                <li><strong>Next Week Updated Plan:</strong> How the plan was adjusted based on your performance (highlighted in yellow)</li>
            </ul>

            {table_html}

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
