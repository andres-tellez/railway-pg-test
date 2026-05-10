#!/usr/bin/env python3
"""
TEMPORARY / DEV ONLY — Inspect ``pre_generation_runner_assessment`` JSON using real DB data.

Runs the same pipeline as ``generate_training_plan`` up to (and including)
``build_pre_generation_runner_assessment``. Does **not** call ``run_v2_plan_generation``,
does **not** persist a plan, does **not** mutate production behavior.

Prerequisites
-------------
- Working directory: repository root (``railway-pg-test``).
- ``DATABASE_URL`` set (e.g. via ``.env.local`` or the shell).

Required env
~~~~~~~~~~~~
- ``DATABASE_URL`` — PostgreSQL connection string (same as the API).

Optional env
~~~~~~~~~~~~
- ``SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1`` — when ``--alignment-enabled`` is omitted,
  alignment follows the same truthy rule as ``agent_tools._intake_alignment_enabled``
  (``1`` / ``true`` / ``yes``).

Exact command (PowerShell, from repo root)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    cd path\\to\\railway-pg-test
    python scripts/debug_pre_generation_runner_assessment.py --user-id "<UUID>" --pretty

Example (replace with your internal user UUID)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    python scripts/debug_pre_generation_runner_assessment.py --user-id "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" --pretty

With explicit alignment on/off (overrides env)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    python scripts/debug_pre_generation_runner_assessment.py --user-id "<UUID>" --alignment-enabled true --pretty

Capture JSON to a file (also prints to stdout)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    python scripts/debug_pre_generation_runner_assessment.py --user-id "<UUID>" --alignment-enabled true --pretty -o assessment.json

Optional athlete sanity-check (warns if not primary for user)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    python scripts/debug_pre_generation_runner_assessment.py --user-id "<UUID>" --athlete-id 12345 --pretty

What to inspect first in the JSON
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. ``activity_summary`` — ``avg_miles_per_week_approx``, ``longest_run_miles``, ``activities_found``, calendar-week fields (your Strava-linked signal).
2. If alignment ran: ``ambition_gap.stance``, ``goal_demand``, ``baseline_band``.
3. If alignment ran: ``intake_alignment_state.allowed_question_categories`` and ``generation_ready``.
4. ``coach_memory`` — hints loaded / entry counts (optional).
5. ``plan_request_digest`` — confirms the synthetic intake matches what you intended.

Remove this script when you no longer need local inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _bootstrap_env() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]

    env_local = project_root / ".env.local"
    if load_dotenv:
        if env_local.exists():
            load_dotenv(env_local, override=False)
        load_dotenv(project_root / ".env", override=False)

    if not os.getenv("DATABASE_URL"):
        print(
            "ERROR: DATABASE_URL is not set. Add it to .env.local or the environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    return project_root


def _intake_alignment_enabled_from_env() -> bool:
    return (
        os.getenv("SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1") or ""
    ).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _resolve_alignment_enabled(arg: Optional[str]) -> bool:
    if arg == "true":
        return True
    if arg == "false":
        return False
    return _intake_alignment_enabled_from_env()


def _parse_training_days(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts


def _build_current_state_from_args(ns: argparse.Namespace) -> Dict[str, Any]:
    draft: Dict[str, Any] = {
        "race_date": ns.race_date,
        "race_distance": ns.race_distance,
        "primary_goal": ns.primary_goal,
        "training_days": _parse_training_days(ns.training_days),
    }
    if ns.primary_goal == "Target Time":
        draft["target_time"] = ns.target_time
    if ns.long_run_day and str(ns.long_run_day).strip():
        draft["long_run_day"] = str(ns.long_run_day).strip()
    return {"draft": draft}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print pre_generation_runner_assessment JSON (dev only; no plan generation)."
    )
    parser.add_argument(
        "--user-id",
        required=True,
        help="Internal user UUID (same as generate_training_plan internal_user_id).",
    )
    parser.add_argument(
        "--athlete-id",
        type=int,
        default=None,
        help="Optional: compare to primary athlete_id for this user (warning only).",
    )
    parser.add_argument(
        "--alignment-enabled",
        choices=("true", "false"),
        default=None,
        help="Override env: run ambition+alignment (true) or activity summary only (false). "
        "If omitted, uses SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON (indent=2).",
    )
    parser.add_argument(
        "--output-file",
        "-o",
        type=str,
        default=None,
        metavar="PATH",
        help="Also write the same JSON to PATH (UTF-8). Still prints to stdout.",
    )
    parser.add_argument(
        "--draft-json",
        type=str,
        default=None,
        help='Path to JSON file: either {"draft": {...}} or a draft object alone.',
    )
    parser.add_argument(
        "--race-date",
        default="2026-10-12",
        help="Draft race_date (YYYY-MM-DD) when not using --draft-json.",
    )
    parser.add_argument(
        "--race-distance",
        default="Marathon",
        help="Draft race_distance when not using --draft-json.",
    )
    parser.add_argument(
        "--primary-goal",
        choices=("Target Time", "Just Finish"),
        default="Target Time",
        help="Draft primary_goal when not using --draft-json.",
    )
    parser.add_argument(
        "--target-time",
        default="3:00:00",
        help="Draft target_time when primary_goal is Target Time.",
    )
    parser.add_argument(
        "--training-days",
        default="Tue,Thu,Sat",
        help="Comma-separated weekday abbreviations (DAY_NAMES_ABBREV), e.g. Tue,Thu,Sat.",
    )
    parser.add_argument(
        "--long-run-day",
        default="",
        help="Optional long_run_day (must be in training_days); empty = omit.",
    )

    ns = parser.parse_args()

    _bootstrap_env()

    # Import after DATABASE_URL is available for db_session engine init.
    from src.coaching_intelligence.pre_generation_runner_assessment import (
        build_pre_generation_runner_assessment,
    )
    from src.db.db_session import get_session
    from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
    from src.smartcoach_mobile_coach.plan_intake_flow import (
        build_plan_request_from_state,
    )

    alignment_enabled = _resolve_alignment_enabled(ns.alignment_enabled)

    if ns.draft_json:
        path = Path(ns.draft_json)
        if not path.is_file():
            print(f"ERROR: --draft-json not found: {path}", file=sys.stderr)
            sys.exit(1)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "draft" in raw:
            current_state: Dict[str, Any] = dict(raw)
        else:
            current_state = {"draft": raw}
    else:
        current_state = _build_current_state_from_args(ns)

    session = get_session()
    try:
        if ns.athlete_id is not None:
            primary = get_primary_athlete_id(session, ns.user_id)
            if primary is None:
                print(
                    f"WARNING: no user_athletes row for user_id={ns.user_id}",
                    file=sys.stderr,
                )
            elif int(primary) != int(ns.athlete_id):
                print(
                    f"WARNING: --athlete-id {ns.athlete_id} != primary athlete_id {primary} "
                    f"for this user (activity summary uses user_id only).",
                    file=sys.stderr,
                )

        plan_request = build_plan_request_from_state(current_state)
        assessment = build_pre_generation_runner_assessment(
            session,
            str(ns.user_id),
            plan_request=plan_request,
            plan_intake_state=current_state,
            alignment_enabled=alignment_enabled,
        )
        payload = assessment.as_api_dict()
    finally:
        session.close()

    indent = 2 if ns.pretty else None
    text = json.dumps(payload, indent=indent, default=str)
    if ns.output_file:
        Path(ns.output_file).expanduser().write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
