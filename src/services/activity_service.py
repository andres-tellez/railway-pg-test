"""
Activity service for ingestion and enrichment logic.
"""

import time
import json
import logging
import os
import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, or_, select, text

from src.services.token_service import get_valid_token
from src.db.dao.split_dao import upsert_splits
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.utils.config import config
from src.utils.logger import get_logger
from src.utils.conversions import convert_metrics
from src.db.models.activities import Activity

log = get_logger(__name__)
log.setLevel(logging.INFO)


def _epoch_to_utc_iso(ts):
    """Human-readable UTC instant for ingest validation logs."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return f"<invalid ts {ts!r}>"


def _access_token_fingerprint(access_token: str | None) -> str:
    """Correlate requests without logging secret material."""
    if not access_token:
        return "empty"
    digest = hashlib.sha256(access_token.encode("utf-8")).hexdigest()[:12]
    return f"sha256:{digest} len={len(access_token)}"


def log_strava_payload(activity_id, activity_json, zones_data, streams):
    """Write debug payload to file."""
    try:
        os.makedirs("debug_dumps", exist_ok=True)
        with open(
            f"debug_dumps/strava_debug_{activity_id}.json", "w", encoding="utf-8"
        ) as f:
            json.dump(
                {"activity": activity_json, "zones": zones_data, "streams": streams},
                f,
                indent=2,
            )
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.warning("Could not write debug payload for %s: %s", activity_id, e)


def _pending_detail_enrichment_where(athlete_id, after=None, before=None):
    """
    Shared SQLAlchemy predicate: Run rows for athlete pending Strava detail enrichment.

    ``after`` / ``before`` are optional Unix timestamps; bounds are compared to
    ``activities.start_date`` as naive UTC instants (aligned with list-ingest chunking).
    """
    parts = [
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.detail_enriched_at.is_(None),
    ]
    if after is not None:
        after_dt = datetime.fromtimestamp(int(after), tz=timezone.utc).replace(
            tzinfo=None
        )
        parts.append(Activity.start_date >= after_dt)
    if before is not None:
        before_dt = datetime.fromtimestamp(int(before), tz=timezone.utc).replace(
            tzinfo=None
        )
        parts.append(Activity.start_date <= before_dt)
    return and_(*parts)


def _pending_detail_missing_summary_where(athlete_id, after=None, before=None):
    """
    Runs still missing the Strava detail pass **and** missing list-level fields the
    coach needs (see ``ActivityFetcher``): distance (raw or converted) and moving time.

    Rows with summary data but ``detail_enriched_at IS NULL`` are not blocking: the
    coach can answer from list-ingest columns; enrichment only adds streams/splits/zones.
    """
    no_distance = and_(Activity.distance.is_(None), Activity.conv_distance.is_(None))
    parts = [
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.detail_enriched_at.is_(None),
        or_(no_distance, Activity.moving_time.is_(None)),
    ]
    if after is not None:
        after_dt = datetime.fromtimestamp(int(after), tz=timezone.utc).replace(
            tzinfo=None
        )
        parts.append(Activity.start_date >= after_dt)
    if before is not None:
        before_dt = datetime.fromtimestamp(int(before), tz=timezone.utc).replace(
            tzinfo=None
        )
        parts.append(Activity.start_date <= before_dt)
    return and_(*parts)


def count_pending_detail_missing_summary(session, athlete_id, after=None, before=None):
    """Count Run rows in the window that block coach until list summary exists."""
    stmt = select(func.count(Activity.activity_id)).where(
        _pending_detail_missing_summary_where(athlete_id, after, before)
    )
    return int(session.scalar(stmt) or 0)


def get_activities_to_enrich(session, athlete_id, limit, after=None, before=None):
    """
    Get activities (with start dates) for enrichment.

    Only returns runs where detail enrichment has not been recorded yet
    (``detail_enriched_at IS NULL``).

    Args:
        session: Database session
        athlete_id: Strava athlete ID
        limit: Maximum number of activities to return
        after: Optional Unix timestamp - only get activities after this time
        before: Optional Unix timestamp - only get activities before this time
    """
    import sys

    print(
        f"🔍 [Get Activities] Executing query for athlete {athlete_id} with params: "
        f"after={after} ({datetime.fromtimestamp(after) if after and isinstance(after, (int, float)) else None}), "
        f"before={before} ({datetime.fromtimestamp(before) if before and isinstance(before, (int, float)) else None}), "
        f"limit={limit}",
        file=sys.stdout,
        flush=True,
    )
    log.info(
        f"🔍 [Get Activities] Executing query for athlete {athlete_id} with params: "
        f"after={after} ({datetime.fromtimestamp(after) if after else None}), "
        f"before={before} ({datetime.fromtimestamp(before) if before else None}), "
        f"limit={limit}"
    )

    stmt = (
        select(Activity.activity_id, Activity.start_date)
        .where(_pending_detail_enrichment_where(athlete_id, after, before))
        .order_by(Activity.start_date.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()

    print(
        f"🔍 [Get Activities] Query returned {len(rows)} activities",
        file=sys.stdout,
        flush=True,
    )
    log.info(f"🔍 [Get Activities] Query returned {len(rows)} activities")

    activities = [
        {"activity_id": row.activity_id, "start_date": row.start_date} for row in rows
    ]

    if activities:
        activity_ids = [a["activity_id"] for a in activities[:5]]
        print(
            f"🔍 [Get Activities] Found activities: {activity_ids}",
            file=sys.stdout,
            flush=True,
        )
        log.info(f"🔍 [Get Activities] Found activities: {activity_ids}")
    else:
        print(
            f"⚠️ [Get Activities] No activities found for athlete {athlete_id} "
            f"with filters: after={after}, before={before}",
            file=sys.stdout,
            flush=True,
        )
        log.warning(
            f"⚠️ [Get Activities] No activities found for athlete {athlete_id} "
            f"with filters: after={after}, before={before}"
        )

    return activities


def count_pending_detail_enrichment(session, athlete_id, after=None, before=None):
    """Count Run rows in the window with ``detail_enriched_at IS NULL``."""
    stmt = select(func.count(Activity.activity_id)).where(
        _pending_detail_enrichment_where(athlete_id, after, before)
    )
    return int(session.scalar(stmt) or 0)


def project_strava_enrichment_calls(
    activities, split_cutoff, *, persist_splits: bool = True
):
    """
    Estimated Strava API calls for enriching the given activity rows (detail + zones;
    plus streams when ``fetch_streams`` would be True for the row and ``persist_splits``.
    """
    total = 0
    for row in activities:
        start_date = row.get("start_date")
        total += 2  # get_activity + get_hr_zones
        fetch_streams = True
        if split_cutoff is not None and start_date is not None:
            start_dt = start_date
            cutoff_dt = split_cutoff
            if start_dt.tzinfo is None and cutoff_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=cutoff_dt.tzinfo)
            elif start_dt.tzinfo is not None and cutoff_dt.tzinfo is None:
                cutoff_dt = cutoff_dt.replace(tzinfo=start_dt.tzinfo)
            fetch_streams = start_dt >= cutoff_dt
        elif split_cutoff is not None and start_date is None:
            fetch_streams = True
        if persist_splits and fetch_streams:
            total += 1
    return total


def enrich_one_activity(
    session,
    access_token,
    activity_id,
    *,
    fetch_streams: bool = True,
    persist_splits: bool = True,
):
    """Enrich a single activity: summary fields, HR zones, and optionally streams + mile splits.

    Stream fetch and split upserts run only when both ``fetch_streams`` and ``persist_splits``
    are true. Callers should pass ``persist_splits`` from
    ``persist_splits_for_user`` (which folds in ``ENABLE_SPLITS``). Activity row
    updates do not require splits or streams.
    """
    try:
        client = StravaClient(access_token)
        retries = 3
        required_fields = ["distance", "moving_time", "average_speed", "name"]
        soft_fields = ["average_heartrate", "suffer_score", "max_speed", "calories"]

        activity_json = None
        for attempt in range(retries):
            activity_json = client.get_activity(activity_id)
            if not isinstance(activity_json, dict):
                log.warning(
                    "Invalid activity payload for activity %s, retry %d/%d...",
                    activity_id,
                    attempt + 1,
                    retries,
                )
                time.sleep(1)
                continue

            if not all(activity_json.get(field) for field in required_fields):
                log.warning(
                    "Missing required fields for activity %s, retry %d/%d...",
                    activity_id,
                    attempt + 1,
                    retries,
                )
                time.sleep(1)
                continue

            zones_data = client.get_hr_zones(activity_id)
            streams = {}

            # Fetch streams only for mile/lap splits (not for HR zone calculation).
            # HR zones come from Strava's zones API only.
            if fetch_streams and persist_splits:
                streams = client.get_streams(
                    activity_id,
                    keys=["distance", "time", "velocity_smooth", "heartrate"],
                )
            elif fetch_streams and not persist_splits:
                log.info(
                    "Skipping stream fetch for activity %s (persist_splits false)",
                    activity_id,
                )
            else:
                log.info(
                    "Skipping stream fetch for activity %s (outside split lookback window)",
                    activity_id,
                )

            break
        else:
            raise ValueError(
                f"Critical data missing after retries for activity {activity_id}: "
                f"{[(field, activity_json.get(field) if isinstance(activity_json, dict) else None) for field in required_fields]}"
            )

        log_strava_payload(activity_id, activity_json, zones_data, streams)

        missing_soft = [f for f in soft_fields if activity_json.get(f) is None]
        if missing_soft:
            log.warning(
                "Partial enrichment for activity %s - missing: %s",
                activity_id,
                missing_soft,
            )

        log.info("Enriching activity %s - %s", activity_id, activity_json.get("name"))

        if not isinstance(activity_json, dict):
            raise ValueError(f"Invalid activity response for activity {activity_id}")
        aid = activity_json.get("id")
        if aid is not None and int(aid) != int(activity_id):
            raise ValueError(
                f"Activity id mismatch for {activity_id}: response has id {aid!r}"
            )

        # Extract HR zones from zones endpoint if available (paid users only)
        # Free users will have hr_zone_pcts = [0.0] * 5 (zones API returns 402)
        hr_zone_pcts = extract_hr_zone_percentages(zones_data)

        # Note: We no longer calculate HR zones from streams for free users
        # HR zones are only available for paid Strava subscribers via the zones API
        if hr_zone_pcts == [0.0] * 5 and zones_data is None:
            log.info(
                "HR zones unavailable (402 Payment Required) - skipping calculation. "
                "HR zones are only available for paid Strava subscribers."
            )

        update_activity_enrichment(
            session,
            activity_id,
            activity_json,
            hr_zone_pcts,
            set_detail_enriched_at=True,
        )

        splits = []
        if fetch_streams and persist_splits:
            splits = build_mile_splits(activity_id, streams)
            if splits:
                upsert_splits(session, splits)
                log.info("Synced %d splits for activity %s", len(splits), activity_id)
        else:
            if fetch_streams and not persist_splits:
                log.debug(
                    "Split generation skipped for activity %s (persist_splits false)",
                    activity_id,
                )
            else:
                log.debug("Split generation skipped for activity %s", activity_id)

        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.error("Exception while enriching %s: %s", activity_id, e)
        raise


def enrich_one_activity_with_refresh(
    session,
    athlete_id,
    activity_id,
    max_retries=2,
    *,
    fetch_streams: bool = True,
    persist_splits: bool = True,
):
    """Attempt enrichment with token refresh and retries."""
    for attempt in range(1, max_retries + 1):
        try:
            access_token = get_valid_token(session, athlete_id)
            enrich_one_activity(
                session,
                access_token,
                activity_id,
                fetch_streams=fetch_streams,
                persist_splits=persist_splits,
            )
            session.expire_all()

            # Check if enrichment succeeded - only require essential fields
            # suffer_score is optional (may not be available for all activities)
            enriched = (
                session.query(Activity)
                .filter(
                    Activity.activity_id == activity_id,
                    Activity.average_speed.isnot(None),
                    Activity.max_speed.isnot(None),
                    Activity.calories.isnot(None),
                )
                .first()
            )

            if enriched:
                log.info(
                    "Enrichment succeeded on attempt %d for activity %s",
                    attempt,
                    activity_id,
                )
                return True

            # Check what fields are actually missing for better logging
            activity_check = (
                session.query(Activity)
                .filter(Activity.activity_id == activity_id)
                .first()
            )
            missing_fields = []
            if not activity_check or activity_check.average_speed is None:
                missing_fields.append("average_speed")
            if not activity_check or activity_check.max_speed is None:
                missing_fields.append("max_speed")
            if not activity_check or activity_check.calories is None:
                missing_fields.append("calories")

            log.warning(
                "Enrichment fields missing on attempt %d for %s. Missing: %s. Retrying...",
                attempt,
                activity_id,
                missing_fields,
            )
            time.sleep(1)

        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error(
                "Enrichment error on attempt %d for %s: %s", attempt, activity_id, e
            )
            time.sleep(1)

    log.error(
        "All retries failed - Activity %s has incomplete enrichment.", activity_id
    )
    raise RuntimeError(f"Enrichment failed for activity {activity_id}")


def update_activity_enrichment(
    session,
    activity_id,
    activity_json,
    hr_zone_pcts,
    *,
    set_detail_enriched_at=False,
):
    """Update enriched fields on activity.

    ``detail_enriched_at`` is set only when ``set_detail_enriched_at`` is True
    (full success after Strava activity + zones calls completed without failure).
    """
    conv = convert_metrics(
        {
            "distance": activity_json.get("distance"),
            "elevation": activity_json.get("total_elevation_gain"),
            "average_speed": activity_json.get("average_speed"),
            "max_speed": activity_json.get("max_speed"),
            "moving_time": activity_json.get("moving_time"),
            "elapsed_time": activity_json.get("elapsed_time"),
        },
        [
            "distance",
            "elevation",
            "average_speed",
            "max_speed",
            "moving_time",
            "elapsed_time",
        ],
    )

    for key in ["average_heartrate", "max_speed", "suffer_score", "calories"]:
        if activity_json.get(key) is None:
            log.warning("%s missing from activity %s", key, activity_id)

    params = {
        "activity_id": activity_id,
        "name": activity_json.get("name"),
        "distance": activity_json.get("distance"),
        "moving_time": activity_json.get("moving_time"),
        "elapsed_time": activity_json.get("elapsed_time"),
        "elevation": activity_json.get("total_elevation_gain"),
        "type": activity_json.get("type"),
        "avg_speed": activity_json.get("average_speed"),
        "max_speed": activity_json.get("max_speed"),
        "suffer_score": activity_json.get("suffer_score"),
        "average_heartrate": activity_json.get("average_heartrate"),
        "max_heartrate": activity_json.get("max_heartrate"),
        "calories": activity_json.get("calories"),
        "hr_zone_1": hr_zone_pcts[0],
        "hr_zone_2": hr_zone_pcts[1],
        "hr_zone_3": hr_zone_pcts[2],
        "hr_zone_4": hr_zone_pcts[3],
        "hr_zone_5": hr_zone_pcts[4],
        **conv,
    }

    detail_clause = ""
    if set_detail_enriched_at:
        params["detail_enriched_at"] = datetime.now(timezone.utc)
        detail_clause = ", detail_enriched_at = :detail_enriched_at"

    session.execute(
        text(
            f"""
            UPDATE activities SET
                name = :name,
                distance = :distance,
                moving_time = :moving_time,
                elapsed_time = :elapsed_time,
                total_elevation_gain = :elevation,
                type = :type,
                average_speed = :avg_speed,
                max_speed = :max_speed,
                suffer_score = :suffer_score,
                average_heartrate = :average_heartrate,
                max_heartrate = :max_heartrate,
                calories = :calories,
                conv_distance = :conv_distance,
                conv_elevation_feet = :conv_elevation_feet,
                conv_avg_speed = :conv_avg_speed,
                conv_max_speed = :conv_max_speed,
                conv_moving_time = :conv_moving_time,
                conv_elapsed_time = :conv_elapsed_time,
                hr_zone_1 = :hr_zone_1,
                hr_zone_2 = :hr_zone_2,
                hr_zone_3 = :hr_zone_3,
                hr_zone_4 = :hr_zone_4,
                hr_zone_5 = :hr_zone_5
                {detail_clause}
            WHERE activity_id = :activity_id
        """
        ),
        params,
    )
    session.commit()


def extract_hr_zone_percentages(zones_data):
    """Compute HR zone percentages from Strava zones API response."""
    if zones_data is None:
        log.debug(
            "HR zones data is None (may be unavailable due to 402 or missing data)"
        )
        return [0.0] * 5

    try:
        for zone_group in zones_data:
            if zone_group.get("type") == "heartrate":
                buckets = zone_group.get("distribution_buckets", [])
                times = [b.get("time", 0.0) for b in buckets[:5]]
                total_time = sum(times)
                if total_time > 0:
                    return [round((t / total_time) * 100, 2) for t in times]
    except Exception as e:  # pylint: disable=broad-exception-caught
        log.warning("HR zone extraction failed: %s", e)
    return [0.0] * 5


def calculate_hr_zones_from_streams(
    heartrate_stream, max_heartrate=None, time_stream=None
):
    """
    Calculate HR zone percentages from heartrate stream data.

    Uses Strava-compatible HR zone thresholds from centralized constants:
    - Zone 1: 50-60% of max HR (Recovery)
    - Zone 2: 60-75% of max HR (Easy/Aerobic)
    - Zone 3: 75-85% of max HR (Threshold)
    - Zone 4: 85-95% of max HR (VO2 Max)
    - Zone 5: 95-100% of max HR (Neuromuscular)

    Imported from src.utils.hr_zone_constants

    Args:
        heartrate_stream: List of heartrate values from stream
        max_heartrate: Maximum heartrate (from activity, database, or estimated)
        time_stream: Optional list of time values (seconds) for time-weighted calculation

    Returns:
        List of 5 zone percentages [zone1, zone2, zone3, zone4, zone5]
    """
    if not heartrate_stream or len(heartrate_stream) == 0:
        log.debug("No heartrate stream data available for HR zone calculation")
        return [0.0] * 5

    # Filter out None/null values
    hr_values = [float(hr) for hr in heartrate_stream if hr is not None]
    if not hr_values:
        log.debug("No valid heartrate values in stream")
        return [0.0] * 5

    # Estimate max HR from stream if not provided
    # Use actual maximum HR from stream + 10% buffer (more accurate than percentile)
    # Note: This is less accurate than using activity's max_heartrate or user's configured max HR
    if max_heartrate is None or max_heartrate == 0:
        if not hr_values:
            log.warning("Cannot estimate max HR - no valid HR values")
            return [0.0] * 5

        max_hr_from_stream = max(hr_values)
        # Add 10% buffer to account for activities that don't reach true max HR
        # This prevents underestimating max HR which would push zones too high
        max_heartrate = max_hr_from_stream * 1.10

        log.info(
            f"Estimated max HR from stream: {max_heartrate:.1f} bpm "
            f"(max in activity: {max_hr_from_stream:.0f} bpm + 10% buffer)"
        )
        log.warning(
            "Using estimated max HR from stream - accuracy may be reduced. "
            "Consider using activity's max_heartrate or user's configured max HR for better accuracy."
        )

    if max_heartrate <= 0:
        log.warning("Invalid max heartrate for HR zone calculation")
        return [0.0] * 5

    # Use time-weighted calculation if time stream is available
    use_time_weighting = (
        time_stream and len(time_stream) == len(hr_values) and len(time_stream) > 1
    )

    # Calculate time in each zone using Strava-compatible thresholds
    # HR values below 50% are excluded (not counted in any zone)
    # Import HR zone thresholds from centralized constants
    from src.utils.hr_zone_constants import HR_ZONE_THRESHOLDS

    zone_times = [0.0] * 5
    excluded_time = 0.0
    excluded_count = 0

    if use_time_weighting:
        # Time-weighted calculation (more accurate)
        for i, hr in enumerate(hr_values):
            # Calculate time interval for this reading
            if i == 0:
                time_interval = (
                    float(time_stream[1]) - float(time_stream[0])
                    if len(time_stream) > 1
                    else 1.0
                )
            elif i < len(time_stream):
                time_interval = float(time_stream[i]) - float(time_stream[i - 1])
            else:
                time_interval = 1.0  # Default to 1 second if missing

            # Skip invalid time intervals
            if time_interval <= 0:
                continue

            hr_pct = hr / max_heartrate

            # Exclude HR below 50% (warmup/cooldown or invalid readings)
            if hr_pct < HR_ZONE_THRESHOLDS["Z1_MIN"]:
                excluded_time += time_interval
                excluded_count += 1
                continue
            elif hr_pct < HR_ZONE_THRESHOLDS["Z1_MAX"]:
                zone_times[0] += time_interval  # Zone 1: 50-60%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z2_MAX"]:
                zone_times[1] += time_interval  # Zone 2: 60-75%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z3_MAX"]:
                zone_times[2] += time_interval  # Zone 3: 75-85%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z4_MAX"]:
                zone_times[3] += time_interval  # Zone 4: 85-95%
            else:
                zone_times[4] += time_interval  # Zone 5: 95-100%
    else:
        # Fallback: Count each reading equally (assumes uniform sampling)
        for hr in hr_values:
            hr_pct = hr / max_heartrate

            # Exclude HR below 50% (warmup/cooldown or invalid readings)
            if hr_pct < HR_ZONE_THRESHOLDS["Z1_MIN"]:
                excluded_count += 1
                continue
            elif hr_pct < HR_ZONE_THRESHOLDS["Z1_MAX"]:
                zone_times[0] += 1  # Zone 1: 50-60%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z2_MAX"]:
                zone_times[1] += 1  # Zone 2: 60-75%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z3_MAX"]:
                zone_times[2] += 1  # Zone 3: 75-85%
            elif hr_pct < HR_ZONE_THRESHOLDS["Z4_MAX"]:
                zone_times[3] += 1  # Zone 4: 85-95%
            else:
                zone_times[4] += 1  # Zone 5: 95-100%

    total_time = sum(zone_times)
    if total_time == 0:
        log.warning("No HR values in valid zones (all below 50% max HR)")
        return [0.0] * 5

    # Convert to percentages
    zone_percentages = [round((t / total_time) * 100, 2) for t in zone_times]

    if excluded_count > 0:
        if use_time_weighting:
            excluded_pct = round(
                (excluded_time / (total_time + excluded_time)) * 100, 1
            )
            log.debug(
                f"Excluded {excluded_count} HR readings ({excluded_pct}% of time) "
                f"below 50% max HR from zone calculation"
            )
        else:
            excluded_pct = round((excluded_count / len(hr_values)) * 100, 1)
            log.debug(
                f"Excluded {excluded_count} HR readings ({excluded_pct}%) "
                f"below 50% max HR from zone calculation"
            )

    method = "time-weighted" if use_time_weighting else "sample-count"
    log.info(
        f"Calculated HR zones from streams ({method}): Z1={zone_percentages[0]:.1f}%, "
        f"Z2={zone_percentages[1]:.1f}%, Z3={zone_percentages[2]:.1f}%, "
        f"Z4={zone_percentages[3]:.1f}%, Z5={zone_percentages[4]:.1f}% "
        f"(max_hr={max_heartrate:.0f} bpm)"
    )
    return zone_percentages


def build_mile_splits(activity_id, streams):
    """Build mile splits from stream data."""
    distances = streams.get("distance", [])
    times = streams.get("time", [])
    paces = streams.get("velocity_smooth", [])
    hrs = streams.get("heartrate", [])

    splits = []
    mile_threshold = 1609.344
    mile_index = 1
    start_index = 0
    speed_threshold = 0.5

    for i, d in enumerate(distances):
        if float(d) < mile_index * mile_threshold - 1e-6:
            continue

        segment_distance = float(d) - float(distances[start_index])
        elapsed_time = float(times[i]) - float(times[start_index])
        moving_time = sum(
            float(times[j]) - float(times[j - 1])
            for j in range(start_index + 1, i + 1)
            if j < len(paces) and float(paces[j]) > speed_threshold
        )

        avg_speed = (
            sum(paces[start_index : i + 1]) / (i + 1 - start_index) if paces else 0
        )
        avg_hr = sum(hrs[start_index : i + 1]) / (i + 1 - start_index) if hrs else None

        segment_distance = round(segment_distance, 2)
        avg_speed = round(avg_speed, 2)
        max_speed_val = round(max(paces[start_index : i + 1]), 2) if paces else None
        avg_hr = round(avg_hr, 2) if avg_hr else None

        conv_data = convert_metrics(
            {
                "distance": segment_distance,
                "average_speed": avg_speed,
                "moving_time": moving_time,
                "elapsed_time": elapsed_time,
            },
            ["distance", "average_speed", "moving_time", "elapsed_time"],
        )

        splits.append(
            {
                "activity_id": activity_id,
                "lap_index": mile_index,
                "distance": segment_distance,
                "elapsed_time": elapsed_time,
                "moving_time": moving_time,
                "average_speed": avg_speed,
                "max_speed": max_speed_val,
                "start_index": start_index,
                "end_index": i,
                "split": mile_index,
                "average_heartrate": avg_hr,
                "pace_zone": None,
                **conv_data,
            }
        )

        start_index = i + 1
        mile_index += 1

    return splits


class ActivityIngestionService:
    """
    Service to ingest activities from Strava.
    """

    def __init__(self, session, athlete_id, user_id=None):
        self.session = session
        self.athlete_id = athlete_id
        self.user_id = user_id  # keep track of user_id
        self._refresh_client()

    def _refresh_client(self):
        access_token = get_valid_token(self.session, self.athlete_id)
        self._access_token_fingerprint = _access_token_fingerprint(access_token)
        self.client = StravaClient(access_token)

    def fetch_all_activities(
        self,
        after=None,
        before=None,
        per_page=None,
        limit=None,
        *,
        type_filter: str | None = None,
        type_limit: int | None = None,
    ):
        """Fetch activities from Strava with pagination.

        Args:
            after: Only return activities after this epoch timestamp.
            before: Only return activities before this epoch timestamp.
            per_page: Page size for each Strava API request.
            limit: Maximum number of activities to retrieve (all types).
            type_filter: Optional activity `type` to filter (e.g. "Run").
            type_limit: Maximum number of filtered activities to return.
        """
        self._refresh_client()
        log.info(
            "[STRAVA_FETCH_VALIDATE] fetch_all_activities INPUT athlete_id=%s "
            "after_ts=%s before_ts=%s after_utc=%s before_utc=%s "
            "access_token_fp=%s per_page=%s type_filter=%r type_limit=%s limit=%s",
            self.athlete_id,
            after,
            before,
            _epoch_to_utc_iso(after),
            _epoch_to_utc_iso(before),
            getattr(self, "_access_token_fingerprint", "?"),
            per_page or config.STRAVA_PER_PAGE,
            type_filter,
            type_limit,
            limit,
        )
        page = 1
        results = []
        filtered: list[dict] = []

        # When looking for a filtered set, prefer that count as the stopping
        # condition but provide a reasonable safety cap for total fetches.
        filtered_target = type_limit if type_limit is not None else None

        def _ingest_debug_fetch_return(result: list) -> list:
            print("[INGEST_DEBUG] STRAVA RESPONSE")
            print("count:", len(result))
            newest = result[0].get("start_date") if result else None
            if result:
                print("newest:", newest)
            runs_trace_count = len(filtered) if type_filter else None
            log.info(
                "[STRAVA_FETCH_VALIDATE] fetch_all_activities RESPONSE athlete_id=%s "
                "returned_count=%s raw_strava_rows_fetched=%s runs_filtered_total=%s "
                "newest_activity_start_date=%s access_token_fp=%s",
                self.athlete_id,
                len(result),
                len(results),
                runs_trace_count,
                newest,
                getattr(self, "_access_token_fingerprint", "?"),
            )
            return result

        while True:
            batch = self.client.get_activities_page(
                page=page,
                per_page=per_page or config.STRAVA_PER_PAGE,
                after=after,
                before=before,
            )
            if not batch:
                break
            results.extend(batch)

            # Apply per-type filtering if requested.
            if type_filter:
                for activity in batch:
                    if activity.get("type") == type_filter:
                        filtered.append(activity)
                        if filtered_target and len(filtered) >= filtered_target:
                            return _ingest_debug_fetch_return(
                                filtered[:filtered_target]
                            )

            # Stop early if we reached the unfiltered limit (only when not filtering).
            if not type_filter and limit and len(results) >= limit:
                return _ingest_debug_fetch_return(results[:limit])

            log.info(
                f"[INFO] Page {page} -> {len(batch)} activities (total={len(results)})"
            )

            # Safety: if we were asked for a filter but also have an overall limit,
            # respect whichever condition hits first.
            if type_filter and limit and len(results) >= limit:
                break

            page += 1
        return _ingest_debug_fetch_return(
            filtered[:filtered_target] if type_filter else results
        )

    def ingest_full_history(
        self, lookback_days=None, max_activities=None, per_page=None, dry_run=False
    ):
        after = (
            int((datetime.utcnow() - timedelta(days=lookback_days)).timestamp())
            if lookback_days
            else None
        )
        all_activities = self.fetch_all_activities(
            after=after,
            per_page=per_page or config.STRAVA_PER_PAGE,
            limit=None,
            type_filter="Run",
            type_limit=max_activities,
        )

        if dry_run:
            return all_activities

        if not all_activities:
            return 0

        # inject user_id before saving
        for act in all_activities:
            act["user_id"] = self.user_id

        ActivityDAO.upsert_activities(
            self.session, self.athlete_id, all_activities, self.user_id
        )
        return len(all_activities)

    def ingest_between(self, start_date, end_date, max_activities=None, per_page=None):
        """Ingest activities between date range."""
        self._refresh_client()
        after = int(start_date.timestamp())
        before = int(end_date.timestamp())
        activities = self.client.get_activities(
            after=after,
            before=before,
            per_page=per_page or config.STRAVA_PER_PAGE,
            limit=max_activities,
        )
        activities = [a for a in activities if a.get("type") == "Run"]

        # inject user_id before saving
        for act in activities:
            act["user_id"] = self.user_id

        return ActivityDAO.upsert_activities(
            self.session, self.athlete_id, activities, self.user_id
        )

    def enrich_single_activity(self, activity_id: int, *, fetch_streams: bool = True):
        """Enrich one run by id using this service's athlete (and optional user for split policy)."""
        from src.db.dao.user_identity_dao import persist_splits_for_user

        persist_splits = persist_splits_for_user(self.session, self.user_id)
        enrich_one_activity_with_refresh(
            self.session,
            self.athlete_id,
            activity_id,
            fetch_streams=fetch_streams,
            persist_splits=persist_splits,
        )


def run_enrichment_batch(
    session,
    athlete_id,
    batch_size=10,
    *,
    split_cutoff=None,
    after=None,
    before=None,
    activities=None,
    persist_splits: bool = True,
):
    """
    Batch enrichment job for activities.

    Args:
        session: Database session
        athlete_id: Strava athlete ID
        batch_size: Number of activities to enrich (ignored if ``activities`` is provided)
        split_cutoff: Optional datetime - activities before this won't fetch streams
        after: Optional Unix timestamp - only enrich activities after this time
        before: Optional Unix timestamp - only enrich activities before this time
        activities: Optional pre-fetched list from :func:`get_activities_to_enrich`;
            when set, ``after``/``before`` are not used for selection.
    """
    import sys

    if activities is None:
        print(
            f"🔄 [Enrichment Batch] Starting enrichment for athlete {athlete_id}, "
            f"batch_size={batch_size}, after={after}, before={before}",
            file=sys.stdout,
            flush=True,
        )
        log.info(
            f"🔄 [Enrichment Batch] Starting enrichment for athlete {athlete_id}, "
            f"batch_size={batch_size}, after={after}, before={before}"
        )
        activities = get_activities_to_enrich(
            session, athlete_id, batch_size, after=after, before=before
        )
    else:
        print(
            f"🔄 [Enrichment Batch] Starting enrichment for athlete {athlete_id}, "
            f"preselected_count={len(activities)}, after={after}, before={before}",
            file=sys.stdout,
            flush=True,
        )
        log.info(
            f"🔄 [Enrichment Batch] Starting enrichment for athlete {athlete_id}, "
            f"preselected_count={len(activities)}, after={after}, before={before}"
        )

    log.info(f"📋 [Enrichment Batch] Found {len(activities)} activities to enrich")
    if not activities:
        log.warning(
            f"⚠️ [Enrichment Batch] No activities found to enrich for athlete {athlete_id}"
        )
        return 0

    enriched_count = 0
    failed_count = 0

    for row in activities:
        aid = row["activity_id"]
        start_date = row.get("start_date")

        fetch_streams = True
        if split_cutoff is not None and start_date is not None:
            start_dt = start_date
            cutoff_dt = split_cutoff

            if start_dt.tzinfo is None and cutoff_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=cutoff_dt.tzinfo)
            elif start_dt.tzinfo is not None and cutoff_dt.tzinfo is None:
                cutoff_dt = cutoff_dt.replace(tzinfo=start_dt.tzinfo)

            fetch_streams = start_dt >= cutoff_dt

        try:
            enrich_one_activity_with_refresh(
                session,
                athlete_id,
                aid,
                fetch_streams=fetch_streams,
                persist_splits=persist_splits,
            )
            enriched_count += 1
            log.info(f"Successfully enriched activity {aid} for athlete {athlete_id}")
        except Exception as e:
            failed_count += 1
            log.error(
                f"Failed to enrich activity {aid} for athlete {athlete_id}: {e}",
                exc_info=True,
            )
            # Continue with next activity - don't let one failure stop the batch

        time.sleep(1)

    log.info(
        f"Enrichment batch complete for athlete {athlete_id}: "
        f"{enriched_count} enriched, {failed_count} failed"
    )
    return enriched_count


def run_enrichment_batches_in_window(
    session,
    athlete_id,
    batch_size,
    *,
    split_cutoff=None,
    after=None,
    before=None,
    max_batches_per_chunk=None,
    rate_buffer=10,
    persist_splits: bool = True,
):
    """
    Run enrichment repeatedly until no pending rows remain in the window or caps hit.

    Returns:
        (total_enriched, defer_due_to_rate_limit): when defer is True, stop and let the
        caller schedule a retry (partial progress may already be persisted).
    """
    from src.utils.rate_limiter import get_rate_limiter

    max_batches = (
        max_batches_per_chunk
        if max_batches_per_chunk is not None
        else config.MAX_ENRICHMENT_BATCHES_PER_CHUNK
    )
    total_enriched = 0
    limiter = get_rate_limiter()

    for batch_num in range(max_batches):
        activities = get_activities_to_enrich(
            session, athlete_id, batch_size, after=after, before=before
        )
        if not activities:
            break

        projected = project_strava_enrichment_calls(
            activities, split_cutoff, persist_splits=persist_splits
        )
        stats = limiter.get_stats()
        remaining_15m = stats.get("remaining_15min", 0)
        if projected + rate_buffer > remaining_15m:
            log.warning(
                "[Enrichment] Rate limit headroom too low (%s remaining, %s projected "
                "+ buffer for batch %s). Deferring with %s activities enriched so far.",
                remaining_15m,
                projected,
                batch_num + 1,
                total_enriched,
            )
            return total_enriched, True

        batch_enriched = run_enrichment_batch(
            session,
            athlete_id,
            batch_size=batch_size,
            split_cutoff=split_cutoff,
            after=after,
            before=before,
            activities=activities,
            persist_splits=persist_splits,
        )
        total_enriched += batch_enriched

    pending_after = count_pending_detail_enrichment(
        session, athlete_id, after=after, before=before
    )
    if pending_after > 0:
        log.info(
            "[Enrichment] %s activities still pending detail in this window "
            "(batch cap max_batches_per_chunk=%s).",
            pending_after,
            max_batches,
        )

    return total_enriched, False
