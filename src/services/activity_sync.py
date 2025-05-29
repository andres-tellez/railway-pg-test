from datetime import datetime
from src.utils.logger import get_logger
from src.services.strava import fetch_activities_between
from src.db.dao.activity_dao import upsert_activities

log = get_logger(__name__)


def sync_recent_activities(conn, athlete_id, access_token, per_page=30) -> int:
    """
    Download recent activities from Strava and persist them.
    Returns the number of activities successfully inserted.
    """
    try:
        from datetime import timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        activities = fetch_activities_between(access_token, start_date, end_date, per_page)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch recent activities: {e}")

    if not activities:
        log.info(f"No recent activities for athlete {athlete_id}")
        return 0

    try:
        count = upsert_activities(conn, athlete_id, activities)
        log.info(f"Inserted {count} recent activities for athlete {athlete_id}")
        return count
    except Exception as e:
        raise RuntimeError(f"Failed to persist activities: {e}")


def sync_activities_between(conn, athlete_id: int, access_token: str, start_date: datetime, end_date: datetime) -> int:
    """
    Fetch and store activities for a given athlete between the specified dates.
    Returns the number of activities inserted or updated.
    """
    activities = fetch_activities_between(access_token, start_date, end_date)
    if not activities:
        print(f"ℹ️ No activities found for athlete {athlete_id} between {start_date.date()} and {end_date.date()}")
        return 0

    count = upsert_activities(conn, athlete_id, activities)
    print(f"✅ Synced {count} activities for athlete {athlete_id}")
    return count



def enrich_missing_activities(conn, athlete_id):
    """
    Enriches activities for the specified athlete that are missing detailed information.
    """
    with conn.cursor() as cur:
        # Fetch activity IDs that lack detailed information
        cur.execute("""
            SELECT id FROM activities
            WHERE athlete_id = %s AND detailed IS FALSE
        """, (athlete_id,))
        activity_ids = [row[0] for row in cur.fetchall()]

        enriched_count = 0
        for activity_id in activity_ids:
            # Fetch detailed activity data from Strava API
            # This assumes you have a function fetch_activity_detail defined elsewhere
            detail = fetch_activity_detail(activity_id)
            if detail:
                # Update the activity record with detailed information
                cur.execute("""
                    UPDATE activities
                    SET detailed = TRUE, detail_data = %s
                    WHERE id = %s
                """, (json.dumps(detail), activity_id))
                enriched_count += 1

        conn.commit()
    return enriched_count