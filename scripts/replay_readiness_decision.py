#!/usr/bin/env python3
"""
Forensic replay: print RunnerEvidence, goal profile, ReadinessVerdict, and
runner_analysis_display using the same production helpers as the readiness gate.

Read-only (no commits). Uses ``DATABASE_URL`` like other dev scripts.

Examples
--------
::

   python scripts/replay_readiness_decision.py --user-id "<UUID>" --anchor-date 2026-05-12

``--anchor-date`` is the athlete local calendar day passed through to
``build_runner_evidence`` / activity window math (matches device anchor when wired).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict


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


def default_replay_plan_intake_state() -> Dict[str, Any]:
    """Minimal committed-shaped state so ``build_plan_request_from_state`` succeeds."""

    return {
        "draft": {
            "race_date": "2026-10-12",
            "race_distance": "Marathon",
            "primary_goal": "Target Time",
            "target_time": "4:00:00",
            "training_days": ["Tue", "Thu", "Sat"],
        },
        "ux": {
            "intake_confirmed": True,
            "runner_review_delivered": True,
        },
        "ready_to_generate": True,
    }


def run_replay(
    *,
    session: Any,
    user_id: str,
    anchor_local_date: date,
    plan_intake_state: Dict[str, Any],
    trace_id: str | None = None,
) -> Dict[str, Any]:
    """Core replay (usable from tests via importlib). Returns a single JSON-serializable dict."""
    from src.coaching_intelligence.plan_generation_readiness import (
        evaluate_plan_generation_readiness,
    )
    from src.coaching_intelligence.pre_generation_runner_assessment import (
        build_pre_generation_runner_assessment,
    )
    from src.smartcoach_mobile_coach.plan_intake_flow import (
        build_plan_request_from_state,
    )

    plan_request = build_plan_request_from_state(plan_intake_state)
    assessment = build_pre_generation_runner_assessment(
        session,
        str(user_id),
        plan_request=plan_request,
        plan_intake_state=plan_intake_state,
        anchor_local_date=anchor_local_date,
    )
    api = assessment.as_api_dict()
    tid = trace_id if trace_id else str(uuid.uuid4())
    readiness = evaluate_plan_generation_readiness(
        plan_request=plan_request,
        assessment_api=api,
        trace_id=tid,
    )
    display = readiness.get("runner_analysis_display")
    return {
        "user_id": str(user_id),
        "anchor_local_date": anchor_local_date.isoformat(),
        "plan_request": plan_request,
        "runner_evidence": api.get("runner_evidence"),
        "goal_profile": readiness.get("goal_profile"),
        "readiness_verdict": readiness,
        "runner_analysis_display": display,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay readiness gate outputs for a user + anchor date (read-only)."
    )
    parser.add_argument("--user-id", required=True, help="Internal user UUID string.")
    parser.add_argument(
        "--anchor-date",
        required=True,
        help="Local anchor calendar date YYYY-MM-DD (activity window boundaries).",
    )
    parser.add_argument(
        "--plan-intake-json",
        default=None,
        help='Optional JSON file: full plan_intake_state or {"draft": {...}}.',
    )
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    ns = parser.parse_args()

    _bootstrap_env()

    try:
        anchor = date.fromisoformat(ns.anchor_date.strip())
    except ValueError:
        print("ERROR: --anchor-date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    if ns.plan_intake_json:
        path = Path(ns.plan_intake_json)
        if not path.is_file():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "draft" in raw:
            plan_intake_state = dict(raw)
        else:
            plan_intake_state = {"draft": raw}
    else:
        plan_intake_state = default_replay_plan_intake_state()

    from src.db.db_session import get_session

    session = get_session()
    try:
        out = run_replay(
            session=session,
            user_id=str(ns.user_id).strip(),
            anchor_local_date=anchor,
            plan_intake_state=plan_intake_state,
        )
    finally:
        session.close()

    indent = 2 if ns.pretty else None
    print(json.dumps(out, indent=indent, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
