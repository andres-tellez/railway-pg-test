"""Post-deploy smoke: refresh_runner_profile and verify zone consistency."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.local")

db_url = os.environ.get("PROD_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not db_url:
    print("ERROR: set PROD_DATABASE_URL or DATABASE_URL")
    sys.exit(1)

os.environ["DATABASE_URL"] = db_url

from src.db.db_session import get_session  # noqa: E402
from src.smartcoach_mobile_coach.db_helpers import (
    fetch_user_hr_profile_for_coach,
)  # noqa: E402
from src.smartcoach_mobile_coach.runner_profile import (  # noqa: E402
    get_runner_profile,
    refresh_runner_profile,
)
from src.smartcoach_mobile_coach.runner_profile.api_schema import (  # noqa: E402
    runner_zone_profile_payload,
)
from src.smartcoach_mobile_coach.runner_profile.service import (  # noqa: E402
    get_runner_training_pace_recommendations,
    get_runner_zone_string_for_run_type,
)
from src.smartcoach_mobile_coach.runner_profile.training_target_context import (  # noqa: E402
    _profile_hr_zones_payload,
)
from src.services.training_plan.recalculate_hr_zones_service import (  # noqa: E402
    recalculate_hr_zones_for_user,
)

ZONE_KEYS = ("z1", "z2", "z3", "z4", "z5")


def _bands_from_profile(profile) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for key in ZONE_KEYS:
        band = getattr(profile, f"hr_{key}", None)
        if band is not None:
            out[key] = {"low": int(band.low), "high": int(band.high)}
    return out


def _overlap_issues(zones: dict[str, dict[str, int]]) -> list[str]:
    keys = [k for k in ZONE_KEYS if k in zones]
    issues: list[str] = []
    for i in range(len(keys) - 1):
        lo_key, hi_key = keys[i], keys[i + 1]
        if zones[lo_key]["high"] >= zones[hi_key]["low"]:
            issues.append(
                f"{lo_key}.high={zones[lo_key]['high']} overlaps "
                f"{hi_key}.low={zones[hi_key]['low']}"
            )
    return issues


def _pick_user_id(session) -> str:
    row = session.execute(
        text(
            """
            SELECT user_id::text
            FROM runner_zone_profiles
            WHERE zone_method = 'karvonen' AND hr_z2_low IS NOT NULL
            ORDER BY computed_at DESC
            LIMIT 1
            """
        )
    ).first()
    if row is None:
        row = session.execute(
            text(
                """
                SELECT user_id::text
                FROM runner_zone_profiles
                WHERE hr_z2_low IS NOT NULL
                ORDER BY computed_at DESC
                LIMIT 1
                """
            )
        ).first()
    if row is None:
        raise RuntimeError("No calibrated runner_zone_profiles row found")
    return str(row[0])


def main() -> int:
    session = get_session()
    failures: list[str] = []
    try:
        user_id = _pick_user_id(session)
        print(f"user_id={user_id}")

        profile = refresh_runner_profile(session, user_id)
        if not profile.calibrated:
            failures.append("profile not calibrated after refresh")
            return 1

        bands = _bands_from_profile(profile)
        print("profile_bands:", json.dumps(bands, indent=2))

        overlap = _overlap_issues(bands)
        if overlap:
            failures.extend(overlap)
        print("non_overlapping:", not overlap)

        recs = get_runner_training_pace_recommendations(
            session, user_id, target_time=None, race_distance=None, profile=profile
        )
        api = runner_zone_profile_payload(profile, training_pace_recommendations=recs)
        api_zones = api.get("hr_zones") or {}
        for key in bands:
            if api_zones.get(key) != bands[key]:
                failures.append(
                    f"API hr_zones.{key} mismatch: {api_zones.get(key)} vs {bands[key]}"
                )
        print("api_zones_match:", not any("API hr_zones" in f for f in failures))

        z2, z3 = profile.hr_z2, profile.hr_z3
        plan_easy = get_runner_zone_string_for_run_type(session, user_id, "easy")
        plan_tempo = get_runner_zone_string_for_run_type(session, user_id, "tempo")
        exp_easy = f"Z2 ({z2.low}\u2013{z2.high} bpm)" if z2 else ""
        exp_tempo = f"Z3 ({z3.low}\u2013{z3.high} bpm)" if z3 else ""
        print("plan_easy:", plan_easy)
        print("plan_tempo:", plan_tempo)
        if plan_easy != exp_easy:
            failures.append(f"plan easy mismatch: {plan_easy!r} vs {exp_easy!r}")
        if plan_tempo != exp_tempo:
            failures.append(f"plan tempo mismatch: {plan_tempo!r} vs {exp_tempo!r}")

        recalc = recalculate_hr_zones_for_user(session, user_id)
        print("plan_recalc:", recalc)

        stored = session.execute(
            text(
                """
            SELECT run_type_key, target_hr
            FROM plan_workouts pw
            JOIN plans p ON p.id = pw.plan_id
            WHERE p.user_id = CAST(:uid AS uuid)
              AND target_hr IS NOT NULL AND target_hr <> ''
            ORDER BY pw.date DESC
            LIMIT 5
            """
            ),
            {"uid": user_id},
        ).fetchall()
        print("stored_target_hr_sample:")
        for run_type, target_hr in stored:
            print(f"  {run_type}: {target_hr}")
            if z2 and run_type == "easy" and target_hr != exp_easy:
                failures.append(f"stored easy target_hr {target_hr!r} != {exp_easy!r}")
            if z3 and run_type == "tempo" and target_hr != exp_tempo:
                failures.append(
                    f"stored tempo target_hr {target_hr!r} != {exp_tempo!r}"
                )

        coach = fetch_user_hr_profile_for_coach(session, user_id)
        if coach is None:
            failures.append("coach user_hr_profile is None")
        else:
            coach_z2 = coach["zones_bpm"]["z2"]
            exp_coach = {"low": float(z2.low), "high": float(z2.high)} if z2 else None
            print("coach_z2:", coach_z2)
            if coach_z2 != exp_coach:
                failures.append(f"coach z2 mismatch: {coach_z2} vs {exp_coach}")

        ctx_zones = _profile_hr_zones_payload(profile)
        ctx_z2 = (ctx_zones or {}).get("z2")
        print("ctx_z2:", ctx_z2)
        if z2 and ctx_z2 != {"low": z2.low, "high": z2.high}:
            failures.append(f"context z2 mismatch: {ctx_z2}")

        print("profile_card_lines (mobile formatHrBandBpm):")
        for key in ZONE_KEYS:
            if key not in bands:
                continue
            b = bands[key]
            print(f"  {key.upper()} · {b['low']}\u2013{b['high']} bpm")

        if failures:
            print("\nFAILURES:")
            for f in failures:
                print(" -", f)
            return 1

        print("\nSMOKE OK")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
