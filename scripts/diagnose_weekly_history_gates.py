"""Read-only: simulate weekly-history + mobile Insights gates for prod user(s)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local")
os.environ["DATABASE_URL"] = (
    os.environ.get("PROD_DATABASE_URL") or os.environ["DATABASE_URL"]
)
if not os.environ.get("DATABASE_URL"):
    sys.exit("DATABASE_URL missing")

from sqlalchemy import text  # noqa: E402

from src.db.db_session import get_session  # noqa: E402
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_weekly_insight_history,
)  # noqa: E402


def mobile_gates(payload: dict) -> dict:
    systems = payload.get("systems") or {}
    easy = systems.get("easy") or {}
    tempo = systems.get("tempo") or {}
    weekly_easy = easy.get("weekly_data") or []
    pace_target = (easy.get("pace_target_display") or "").strip() or None
    hr_target = (easy.get("hr_target_display") or "").strip() or None
    subtitle = (
        (easy.get("insights_easy_banner") or {}).get("subtitle") or ""
    ).strip() or None
    easy_banner = bool(pace_target and hr_target and subtitle)
    show_easy_charts = len(weekly_easy) >= 1
    tempo_banner = bool(
        ((tempo.get("insights_tempo_banner") or {}).get("subtitle") or "").strip()
        and (tempo.get("pace_target_display") or "").strip()
    )
    show_shell = bool(
        payload.get("latest_week")
        or len(weekly_easy) >= 1
        or easy_banner
        or tempo_banner
    )
    easy_empty = show_shell and not easy_banner and not show_easy_charts
    return {
        "has_history": payload.get("has_history"),
        "message": payload.get("message"),
        "has_systems_easy": "easy" in systems,
        "easy_weekly_points": len(weekly_easy),
        "pace_target_display": pace_target,
        "hr_target_display": hr_target,
        "easy_banner": easy_banner,
        "show_easy_charts": show_easy_charts,
        "show_insights_shell": show_shell,
        "mobile_easy_empty_state": easy_empty,
    }


def main() -> None:
    emails = sys.argv[1:] or ["andres.tellez@gmail.com"]
    with get_session() as session:
        for email in emails:
            row = session.execute(
                text(
                    "SELECT user_id::text FROM user_identity WHERE email = :e LIMIT 1"
                ),
                {"e": email},
            ).fetchone()
            if not row:
                print(f"NO USER {email}")
                continue
            user_id = row[0]
            payload = get_weekly_insight_history(session, user_id, weeks=6)
            print(f"=== {email} ({user_id}) ===")
            print(json.dumps(mobile_gates(payload), indent=2))
            plan = session.execute(
                text(
                    """
                    SELECT id, race_distance, target_time, primary_goal, is_active
                    FROM plans
                    WHERE user_id = :uid
                    ORDER BY is_active DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"uid": user_id},
            ).fetchone()
            print("active_plan:", dict(plan._mapping) if plan else None)
            wti = session.execute(
                text(
                    """
                    SELECT COUNT(*) AS n,
                           COUNT(*) FILTER (WHERE hr_drift_pct IS NOT NULL) AS with_drift
                    FROM weekly_training_insights
                    WHERE user_id = :uid
                    """
                ),
                {"uid": user_id},
            ).fetchone()
            print("weekly_training_insights:", dict(wti._mapping) if wti else None)


if __name__ == "__main__":
    main()
