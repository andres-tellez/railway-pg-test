"""
Activity Routes Module
======================

Provides API endpoints for managing and enriching user activities.

Endpoints:
----------
GET  /api/activities/
    Get user's activities (last 30 days) for plan generation context

GET  /api/activities/enrich/status
    Check enrichment service status

POST /api/activities/enrich/activity/<activity_id>
    Enrich a single activity with additional data

POST /api/activities/enrich/batch
    Enrich a batch of activities for an athlete

Dependencies:
-------------
- ActivityIngestionService: Activity enrichment logic
- requires_auth: JWT authentication decorator
- Database: activities table, user_athletes table

Data Source:
-----------
- activities table: Stores synced Strava activities
- Enrichment: Adds calculated metrics (pace zones, HR zones, etc.)
"""

from __future__ import annotations

import traceback
from typing import Optional
from datetime import datetime
from io import BytesIO

from flask import Blueprint, jsonify, request, g, send_file
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import UUID

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService, run_enrichment_batch
from src.utils.auth0_jwt import requires_auth

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activities")


@activity_bp.get("/")
@requires_auth
def get_activities():
    """
    Return user's activities for plan generation context.
    Returns basic activity data with distances and dates.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"activities": []}), 200

        # Get athlete_id for this user
        stmt = text(
            """
            SELECT athlete_id
            FROM public.user_athletes
            WHERE user_id = :uid
            LIMIT 1
            """
        ).bindparams(bindparam("uid", type_=UUID))
        athlete_row = session.execute(stmt, {"uid": internal_user_id}).fetchone()

        if not athlete_row:
            return jsonify({"activities": []}), 200

        athlete_id = athlete_row.athlete_id

        # Fetch activities from the last 30 days (4 weeks)
        # Use PostgreSQL to convert UTC datetime to activity's local timezone and extract date
        # Timezone format: "(GMT-06:00) America/Chicago" -> extract "America/Chicago"
        activities_stmt = text(
            """
            SELECT
                activity_id,
                CASE
                    WHEN timezone IS NOT NULL AND timezone LIKE '%America/%' THEN
                        -- Extract timezone name after ") " (e.g., "America/Chicago")
                        DATE((start_date AT TIME ZONE 'UTC') AT TIME ZONE
                            SUBSTRING(timezone FROM POSITION(') ' IN timezone) + 2))
                    WHEN timezone IS NOT NULL THEN
                        -- Try to extract timezone name, fallback to UTC conversion
                        DATE((start_date AT TIME ZONE 'UTC') AT TIME ZONE
                            COALESCE(
                                NULLIF(SUBSTRING(timezone FROM POSITION(') ' IN timezone) + 2), ''),
                                'UTC'
                            ))
                    ELSE
                        -- No timezone: assume start_date is already in local time, extract date directly
                        DATE(start_date)
                END as local_date,
                distance,
                moving_time,
                name,
                type,
                average_heartrate
            FROM public.activities
            WHERE athlete_id = :aid
            AND start_date >= NOW() - INTERVAL '30 days'
            ORDER BY start_date DESC
            """
        )

        activities_result = session.execute(
            activities_stmt, {"aid": athlete_id}
        ).fetchall()

        activities = [
            {
                "activity_id": row[0],
                "date": (
                    row[1].isoformat() if row[1] else None
                ),  # Already converted to local date by PostgreSQL
                "distance_miles": (
                    float(row[2] * 0.000621371) if row[2] else 0
                ),  # Convert meters to miles
                "moving_time": row[3],
                "name": row[4],
                "type": row[5],
                "average_heartrate": float(row[6]) if row[6] is not None else None,
            }
            for row in activities_result
        ]

        return jsonify({"activities": activities}), 200

    except Exception as e:
        print(f"❌ Error fetching activities: {e}")
        traceback.print_exc()
        return jsonify({"activities": []}), 200
    finally:
        session.close()


# -------- Enrichment routes --------
@activity_bp.get("/enrich/status")
@requires_auth
def enrich_status():
    return jsonify({"enrich": "ok"}), 200


@activity_bp.post("/enrich/activity/<int:activity_id>")
@requires_auth
def enrich_single(activity_id: int):
    session = get_session()
    try:
        row = session.execute(
            text("SELECT athlete_id FROM activities WHERE activity_id = :id"),
            {"id": activity_id},
        ).fetchone()
        if not row:
            return jsonify({"error": f"Activity {activity_id} not found"}), 404

        athlete_id = row.athlete_id  # type: ignore[attr-defined]
        service = ActivityIngestionService(session, athlete_id)
        service.enrich_single_activity(activity_id)
        return jsonify({"status": "ok", "activity_id": activity_id}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@activity_bp.post("/enrich/batch")
@requires_auth
def enrich_batch():
    athlete_id: Optional[int] = request.args.get("athlete_id", type=int)
    batch: int = request.args.get("batch", default=20, type=int)

    if not athlete_id:
        return jsonify({"error": "Missing athlete_id"}), 400

    batch = max(1, min(batch or 20, 500))

    session = get_session()
    try:
        enriched_count = run_enrichment_batch(session, athlete_id, batch_size=batch)
        return (
            jsonify(
                {
                    "status": "ok",
                    "athlete_id": athlete_id,
                    "batch_size": batch,
                    "enriched_count": int(enriched_count),
                }
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@activity_bp.get("/export")
@requires_auth
def export_activities():
    """
    Export user's activities to Excel file.

    Query Parameters:
    - start_date: Start date in YYYY-MM-DD format (required)
    - end_date: End date in YYYY-MM-DD format (required)

    Returns:
    - Excel file with formatted activity data
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get date range from query parameters
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        if not start_date_str or not end_date_str:
            return jsonify({"error": "start_date and end_date are required"}), 400

        # Validate date format
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

        if start_date > end_date:
            return (
                jsonify({"error": "start_date must be before or equal to end_date"}),
                400,
            )

        # Query activities from v_completed_activities view
        # Note: activity_date is a text field (YYYY-MM-DD) from the view, so we cast it to date for comparison
        # Removed max_hr since it's not in the desired format
        query = text(
            """
            SELECT
                activity_date,
                activity_name,
                distance,
                avg_speed,
                elevation,
                avg_hr,
                hr_zone1,
                hr_zone2,
                hr_zone3,
                hr_zone4,
                hr_zone5,
                activity_id,
                moving_time
            FROM v_completed_activities
            WHERE user_id = :user_id
              AND activity_date::date BETWEEN CAST(:start_date AS date) AND CAST(:end_date AS date)
            ORDER BY activity_date DESC, activity_id DESC
        """
        )

        try:
            activities = session.execute(
                query,
                {
                    "user_id": str(internal_user_id),
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                },
            ).fetchall()
        except Exception as query_error:
            print(f"❌ Query error: {query_error}", flush=True)
            traceback.print_exc()
            return (
                jsonify(
                    {"error": "Failed to query activities", "detail": str(query_error)}
                ),
                500,
            )

        if not activities:
            return (
                jsonify({"error": "No activities found in the specified date range"}),
                404,
            )

        # Generate Excel file
        try:
            import xlsxwriter
        except ImportError as import_error:
            print(f"❌ xlsxwriter import error: {import_error}", flush=True)
            return (
                jsonify(
                    {
                        "error": "xlsxwriter library not installed",
                        "detail": str(import_error),
                    }
                ),
                500,
            )

        # Create in-memory Excel file
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Activities")

        # Define formats
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4472C4",  # Blue
                "font_color": "#FFFFFF",
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "border_color": "#FFFFFF",
            }
        )

        date_format = workbook.add_format(
            {
                "num_format": "yyyy-mm-dd",
                "align": "center",
                "valign": "vcenter",
            }
        )

        number_format = workbook.add_format(
            {
                "num_format": "0.00",
                "align": "center",
                "valign": "vcenter",
            }
        )

        integer_format = workbook.add_format(
            {
                "num_format": "0",
                "align": "center",
                "valign": "vcenter",
            }
        )

        percent_format = workbook.add_format(
            {
                "num_format": "0.0",
                "align": "center",
                "valign": "vcenter",
            }
        )

        text_format = workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
            }
        )

        activity_name_format = workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
            }
        )

        centered_text_format = workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
            }
        )

        hyperlink_format = workbook.add_format(
            {
                "font_color": "#0066CC",
                "underline": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        # Write headers in the desired order
        headers = [
            "Date",
            "Activity Name",
            "Distance (mi)",
            "Pace",
            "Avg HR (bpm)",
            "HR Zone 1 (%)",
            "HR Zone 2 (%)",
            "HR Zone 3 (%)",
            "HR Zone 4 (%)",
            "HR Zone 5 (%)",
            "Strava Link",
            "Moving Time",
            "Elevation (ft)",
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Prepare data for width calculation (before writing rows)
        data_rows = []
        for activity in activities:
            try:
                date_str = (
                    str(activity.activity_date)
                    if hasattr(activity, "activity_date") and activity.activity_date
                    else ""
                )
                activity_name = str(getattr(activity, "activity_name", None) or "")
                distance = getattr(activity, "distance", None) or 0
                avg_speed = getattr(activity, "avg_speed", None) or 0
                avg_hr = getattr(activity, "avg_hr", None) or 0
                hr_zone1 = getattr(activity, "hr_zone1", None) or 0
                hr_zone2 = getattr(activity, "hr_zone2", None) or 0
                hr_zone3 = getattr(activity, "hr_zone3", None) or 0
                hr_zone4 = getattr(activity, "hr_zone4", None) or 0
                hr_zone5 = getattr(activity, "hr_zone5", None) or 0
                strava_link = "View on Strava"  # Fixed text for hyperlink
                moving_time = str(getattr(activity, "moving_time", None) or "")
                elevation = getattr(activity, "elevation", None) or 0

                # Column order: Date, Activity Name, Distance, Pace, Avg HR, HR Zone 1-5, Strava Link, Moving Time, Elevation
                data_rows.append(
                    [
                        date_str,
                        activity_name,
                        distance,
                        avg_speed,
                        avg_hr,
                        hr_zone1,
                        hr_zone2,
                        hr_zone3,
                        hr_zone4,
                        hr_zone5,
                        strava_link,
                        moving_time,
                        elevation,
                    ]
                )
            except Exception:
                continue

        # Calculate dynamic column widths based on content
        def calculate_column_width(
            headers_list, data_list, col_index, min_width=8, max_width=50
        ):
            """Calculate optimal column width based on header and data content."""
            # Start with header width
            max_width_needed = (
                len(headers_list[col_index])
                if col_index < len(headers_list)
                else min_width
            )

            # Check all data rows for this column
            for row_data in data_list:
                if col_index < len(row_data):
                    cell_value = row_data[col_index]
                    if cell_value is None:
                        continue
                    # For numbers, estimate width (roughly 1 char per digit + decimals)
                    if isinstance(cell_value, (int, float)):
                        cell_str = f"{cell_value:.2f}".rstrip("0").rstrip(".")
                        max_width_needed = max(max_width_needed, len(cell_str))
                    else:
                        max_width_needed = max(max_width_needed, len(str(cell_value)))

            # Add padding (1-2 characters) and clamp between min and max
            width = min(max(max_width_needed + 2, min_width), max_width)
            return width

        # Calculate and set dynamic widths for each column
        num_cols = len(headers)
        for col_idx in range(num_cols):
            if col_idx == 1:  # Activity Name - allow wider max
                width = calculate_column_width(
                    headers, data_rows, col_idx, min_width=10, max_width=50
                )
            else:
                width = calculate_column_width(
                    headers, data_rows, col_idx, min_width=8, max_width=20
                )
            worksheet.set_column(col_idx, col_idx, width)

        # Freeze header row
        worksheet.freeze_panes(1, 0)

        # Add conditional formatting (data bars) for HR Zone columns (F-J, indices 5-9) after data is written
        # We'll add this after the loop

        # Write data rows
        for row_idx, activity in enumerate(activities, start=1):
            try:
                # Date
                if hasattr(activity, "activity_date") and activity.activity_date:
                    try:
                        # activity_date is a text field (YYYY-MM-DD) from the view
                        date_str = str(activity.activity_date).strip()
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        worksheet.write_datetime(row_idx, 0, date_obj, date_format)
                    except (ValueError, AttributeError, TypeError) as date_err:
                        # Fallback: write as string if parsing fails
                        print(
                            f"⚠️ Date parsing error for row {row_idx}: {date_err}, value: {activity.activity_date}",
                            flush=True,
                        )
                        worksheet.write(
                            row_idx, 0, str(activity.activity_date), text_format
                        )
                else:
                    worksheet.write(row_idx, 0, "", text_format)

                # Activity Name (column 1) - left aligned
                activity_name = getattr(activity, "activity_name", None) or ""
                worksheet.write(row_idx, 1, str(activity_name), activity_name_format)

                # Distance (column 2)
                distance = getattr(activity, "distance", None)
                worksheet.write(
                    row_idx,
                    2,
                    float(distance) if distance is not None else 0,
                    number_format,
                )

                # Pace - renamed from Avg Speed (column 3)
                avg_speed = getattr(activity, "avg_speed", None)
                worksheet.write(
                    row_idx,
                    3,
                    float(avg_speed) if avg_speed is not None else 0,
                    number_format,
                )

                # Avg HR (column 4)
                avg_hr = getattr(activity, "avg_hr", None)
                worksheet.write(
                    row_idx,
                    4,
                    float(avg_hr) if avg_hr is not None else 0,
                    integer_format,
                )

                # HR Zones (as percentages) - columns 5-9
                hr_zone1 = getattr(activity, "hr_zone1", None)
                hr_zone2 = getattr(activity, "hr_zone2", None)
                hr_zone3 = getattr(activity, "hr_zone3", None)
                hr_zone4 = getattr(activity, "hr_zone4", None)
                hr_zone5 = getattr(activity, "hr_zone5", None)
                worksheet.write(
                    row_idx,
                    5,
                    float(hr_zone1) if hr_zone1 is not None else 0,
                    percent_format,
                )
                worksheet.write(
                    row_idx,
                    6,
                    float(hr_zone2) if hr_zone2 is not None else 0,
                    percent_format,
                )
                worksheet.write(
                    row_idx,
                    7,
                    float(hr_zone3) if hr_zone3 is not None else 0,
                    percent_format,
                )
                worksheet.write(
                    row_idx,
                    8,
                    float(hr_zone4) if hr_zone4 is not None else 0,
                    percent_format,
                )
                worksheet.write(
                    row_idx,
                    9,
                    float(hr_zone5) if hr_zone5 is not None else 0,
                    percent_format,
                )

                # Strava Link (hyperlink) - column 10 - centered
                activity_id = getattr(activity, "activity_id", None)
                if activity_id:
                    strava_url = f"https://www.strava.com/activities/{activity_id}"
                    worksheet.write_url(
                        row_idx,
                        10,
                        strava_url,
                        hyperlink_format,
                        string="View on Strava",
                    )
                else:
                    worksheet.write(row_idx, 10, "", hyperlink_format)

                # Moving Time (text, already formatted) - column 11 - centered
                moving_time = getattr(activity, "moving_time", None) or ""
                worksheet.write(row_idx, 11, str(moving_time), centered_text_format)

                # Elevation - column 12
                elevation = getattr(activity, "elevation", None)
                worksheet.write(
                    row_idx,
                    12,
                    float(elevation) if elevation is not None else 0,
                    integer_format,
                )
            except Exception as row_error:
                print(f"❌ Error writing row {row_idx}: {row_error}", flush=True)
                traceback.print_exc()
                # Continue with next row instead of failing completely
                continue

        # Add conditional formatting (data bars) for HR Zone columns (columns 5-9, indices 5-9)
        # Data bars for percentages in HR Zone columns - solid yellow/gold bars
        if len(activities) > 0:
            # last_data_row is the last row with data (0-indexed, so len(activities) is correct since we start at row 1)
            last_data_row = len(activities)
            data_bar_options = {
                "type": "data_bar",
                "bar_color": "#FFC000",  # Yellow/Gold color
                "bar_solid": True,  # Solid bars as shown in the image
                "min_type": "num",  # Minimum value type
                "max_type": "num",  # Maximum value type
                "min_value": 0,  # Minimum value for scaling
                "max_value": 100,  # Maximum value (percentage)
            }
            # HR Zone 1 (column 5, index 5)
            worksheet.conditional_format(1, 5, last_data_row, 5, data_bar_options)
            # HR Zone 2 (column 6, index 6)
            worksheet.conditional_format(1, 6, last_data_row, 6, data_bar_options)
            # HR Zone 3 (column 7, index 7)
            worksheet.conditional_format(1, 7, last_data_row, 7, data_bar_options)
            # HR Zone 4 (column 8, index 8)
            worksheet.conditional_format(1, 8, last_data_row, 8, data_bar_options)
            # HR Zone 5 (column 9, index 9)
            worksheet.conditional_format(1, 9, last_data_row, 9, data_bar_options)

        # Close workbook
        workbook.close()
        output.seek(0)

        # Generate filename
        filename = f"activities_{start_date_str}_to_{end_date_str}.xlsx"

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    except Exception as e:
        print(f"❌ Error exporting activities: {e}", flush=True)
        traceback.print_exc()
        return jsonify({"error": "Failed to export activities", "detail": str(e)}), 500
    finally:
        session.close()
