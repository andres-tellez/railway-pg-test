#!/usr/bin/env python3
"""
Reset a SmartCoach user so GET /api/user looks like a first-time runner for mobile QA:

- hasStrava: false   (user_athletes link + Strava tokens removed)
- hasActivities: false (activities deleted for that user)
- hasOnboarded: false if user_profile row is removed

Requires PostgreSQL (e.g. Railway). Load DATABASE_URL from .env / .env.local before running.

Example:
  cd railway-pg-test
  python scripts/reset_user_first_time_testing.py \\
    --user-id e3362637-9045-4aac-83ed-92bc1f2643b9 \\
    --yes

Then on the device: dev build → Coach tab → long-press the "Coach" title → clear local intro,
or reinstall the app to wipe SecureStore.

Options:
  --api-only     Only touch data that affects /api/user (no insights/conversations cleanup).
  --keep-profile Keep user_profile (hasOnboarded may stay true).
  --athlete-id   Strava athlete id if there is no user_athletes row but tokens/activities remain.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_env() -> None:
    root = _repo_root()
    load_dotenv(root / ".env.local", override=False)
    load_dotenv(root / ".env", override=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        required=True,
        help="Internal user_id UUID (user_identity.user_id), same as GET /api/me user_id.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation (avoids accidental runs).",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Only reset Strava link, tokens, sync status, activities, profile (skip insights/conversations).",
    )
    parser.add_argument(
        "--keep-profile",
        action="store_true",
        help="Do not delete user_profile (hasOnboarded may remain true).",
    )
    parser.add_argument(
        "--athlete-id",
        type=int,
        default=None,
        help="Optional Strava athlete_id for deleting tokens when user_athletes row is already gone.",
    )
    args = parser.parse_args()
    if not args.yes:
        print("Refusing to run without --yes (destructive).")
        return 2

    try:
        user_uuid = uuid.UUID(args.user_id.strip())
    except ValueError:
        print(f"Invalid --user-id (expected UUID): {args.user_id!r}")
        return 2
    uid_str = str(user_uuid)

    _load_env()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set.")
        return 1

    engine = create_engine(db_url, future=True)
    SessionFactory = sessionmaker(bind=engine, future=True)
    session: Session = SessionFactory()

    try:
        row = session.execute(
            text("SELECT 1 FROM user_identity WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid_str},
        ).first()
        if not row:
            print(f"No user_identity row for user_id={uid_str}")
            return 1

        link = session.execute(
            text(
                "SELECT athlete_id FROM user_athletes WHERE user_id = CAST(:uid AS uuid)"
            ),
            {"uid": uid_str},
        ).first()
        athlete_id = args.athlete_id
        if link is not None:
            athlete_id = int(link[0])
        elif athlete_id is None:
            print(
                "No user_athletes link; pass --athlete-id to delete tokens, "
                "or link will be absent and tokens may be orphaned."
            )

        if not args.api_only:
            session.execute(
                text(
                    """
                    DELETE FROM conversation_messages
                    WHERE conversation_id IN (
                      SELECT id FROM conversations WHERE user_id = CAST(:uid AS uuid)
                    )
                    """
                ),
                {"uid": uid_str},
            )
            session.execute(
                text("DELETE FROM conversations WHERE user_id = CAST(:uid AS uuid)"),
                {"uid": uid_str},
            )
            session.execute(
                text(
                    "DELETE FROM weekly_training_insights WHERE user_id = CAST(:uid AS uuid)"
                ),
                {"uid": uid_str},
            )
            session.execute(
                text(
                    "DELETE FROM user_coach_preferences WHERE user_id = CAST(:uid AS uuid)"
                ),
                {"uid": uid_str},
            )
            session.execute(
                text("DELETE FROM user_hr_zones WHERE user_id = :uid_text"),
                {"uid_text": uid_str},
            )

        # Core: API-facing status
        deleted_act = session.execute(
            text("DELETE FROM activities WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid_str},
        ).rowcount
        deleted_sync = session.execute(
            text("DELETE FROM strava_sync_status WHERE user_id = :uid_text"),
            {"uid_text": uid_str},
        ).rowcount
        deleted_tokens = 0
        if athlete_id is not None:
            r = session.execute(
                text("DELETE FROM tokens WHERE athlete_id = :aid"),
                {"aid": athlete_id},
            )
            deleted_tokens = r.rowcount or 0
        deleted_link = session.execute(
            text("DELETE FROM user_athletes WHERE user_id = CAST(:uid AS uuid)"),
            {"uid": uid_str},
        ).rowcount
        deleted_profile = 0
        if not args.keep_profile:
            r = session.execute(
                text("DELETE FROM user_profile WHERE user_id = :uid_text"),
                {"uid_text": uid_str},
            )
            deleted_profile = r.rowcount or 0

        session.commit()

        print("Done. Summary:")
        print(f"  user_id:           {uid_str}")
        print(f"  athlete_id used:   {athlete_id}")
        print(f"  activities del:    {deleted_act}")
        print(f"  strava_sync del:   {deleted_sync}")
        print(f"  tokens del:        {deleted_tokens}")
        print(f"  user_athletes del: {deleted_link}")
        print(f"  user_profile del:  {deleted_profile}")
        if args.api_only:
            print(
                "  (--api-only: skipped conversations / weekly insights / coach prefs / hr zones)"
            )
        if args.keep_profile:
            print("  (--keep-profile: user_profile unchanged)")
        print()
        print(
            "Next: long-press Coach title in __DEV__ app to clear local intro, or reinstall."
        )
        return 0
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        return 1
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
