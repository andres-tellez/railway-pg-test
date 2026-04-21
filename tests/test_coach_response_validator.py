"""
V1.6 Phase C 3C.8 + 3C.9 — coach response validator tests.

Covers both halves of the post-response validator:

* **3C.8** read-only field contradictions for the six §19.9 fields
  (``deviation_direction``, ``plan_status``, ``baseline_status``,
  ``phase_kpi_priority``, ``adherence_runs_pct``,
  ``violated_rest_day``). Each detector is tested with a
  contradiction case (must fire) AND an agreement case (must NOT
  fire) to guard against false positives.
* **3C.9** numeric grounding: metric-shaped tokens (percent, bpm,
  pace, miles) are flagged when they cannot be traced back to any
  tool payload value, and silently accepted when they can.
* End-to-end :func:`validate_coach_response` entry point: stable
  report shape, safe handling of empty text / empty payloads, and
  observability-only semantics (no response rewriting).
* Orchestrator wiring: import, single call site under an env flag,
  meta envelope shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from src.smartcoach_mobile_coach import coach_response_validator
from src.smartcoach_mobile_coach.coach_response_validator import (
    COACH_RESPONSE_VALIDATOR_VERSION,
    READ_ONLY_FIELDS,
    check_numeric_grounding,
    check_readonly_field_contradictions,
    collect_grounded_token_pool,
    collect_readonly_field_observations,
    validate_coach_response,
)


# ---------------------------------------------------------------------------
# Module surface & version
# ---------------------------------------------------------------------------


def test_validator_version_is_int_and_v1() -> None:
    assert isinstance(COACH_RESPONSE_VALIDATOR_VERSION, int)
    assert COACH_RESPONSE_VALIDATOR_VERSION == 1


def test_read_only_fields_are_exactly_the_six_spec_fields() -> None:
    # §19.9 lists six fields. Drift here means the validator is
    # either missing a field or checking something the spec doesn't
    # mandate — both are real bugs.
    assert set(READ_ONLY_FIELDS) == {
        "deviation_direction",
        "plan_status",
        "baseline_status",
        "phase_kpi_priority",
        "adherence_runs_pct",
        "violated_rest_day",
    }


def test_module_surface_exports_expected_names() -> None:
    for name in (
        "COACH_RESPONSE_VALIDATOR_VERSION",
        "READ_ONLY_FIELDS",
        "validate_coach_response",
        "collect_readonly_field_observations",
        "collect_grounded_token_pool",
        "check_readonly_field_contradictions",
        "check_numeric_grounding",
    ):
        assert hasattr(
            coach_response_validator, name
        ), f"public API symbol {name!r} disappeared"


# ---------------------------------------------------------------------------
# collect_readonly_field_observations
# ---------------------------------------------------------------------------


def test_collect_finds_nested_readonly_fields() -> None:
    # The observation walker must reach fields at arbitrary depth
    # inside lists + dicts (e.g. weekly plan → days[] → actual →
    # deviation_direction).
    tool_outputs = [
        {
            "week": {
                "adherence_runs_pct": 0.55,
                "phase_kpi_priority": ["HR Drift", "Aerobic Efficiency"],
                "days": [
                    {
                        "planned": {"plan_status": "executed"},
                        "actual": {
                            "deviation_direction": "too_hard",
                            "violated_rest_day": False,
                        },
                    },
                    {
                        "planned": {"plan_status": "missed"},
                    },
                ],
            }
        },
        {"user": {"baseline_status": "thin"}},
    ]
    obs = collect_readonly_field_observations(tool_outputs)
    assert obs["deviation_direction"] == ["too_hard"]
    assert sorted(obs["plan_status"]) == ["executed", "missed"]
    assert obs["baseline_status"] == ["thin"]
    assert obs["phase_kpi_priority"] == [["HR Drift", "Aerobic Efficiency"]]
    assert obs["adherence_runs_pct"] == [0.55]
    assert obs["violated_rest_day"] == [False]


def test_collect_returns_empty_lists_for_absent_fields() -> None:
    # Absent is NOT the same as contradicted — §19 ``null`` vs absent
    # convention. The observer MUST return an empty list so downstream
    # checks simply skip, rather than inventing a default value.
    obs = collect_readonly_field_observations([{"irrelevant": 1}])
    for field in READ_ONLY_FIELDS:
        assert obs[field] == []


def test_collect_handles_non_dict_tool_outputs_defensively() -> None:
    # Some tools return lists, strings, or scalars (error envelopes,
    # simple values). The walker must not crash.
    obs = collect_readonly_field_observations(
        [None, "ok", 42, [{"plan_status": "executed"}]]
    )
    assert obs["plan_status"] == ["executed"]


# ---------------------------------------------------------------------------
# 3C.8 — deviation_direction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,observed,should_fire",
    [
        # Payload says too_hard; coach says on target → contradiction.
        ("Compared to plan, you ran it on target.", ["too_hard"], True),
        # Agreement case — must not fire.
        ("Compared to plan, you ran it too hard.", ["too_hard"], False),
        # Payload says on_target; coach says too_easy → contradiction.
        ("Honestly, you ran it too easy.", ["on_target"], True),
        # Null / absent → validator must not fire (§5 Steady / missing HR).
        ("On target today.", [None], False),
    ],
)
def test_deviation_direction_detector_fires_on_flip_only(
    text: str, observed: list, should_fire: bool
) -> None:
    violations = check_readonly_field_contradictions(
        text, {"deviation_direction": observed}
    )
    fired = any(v["field"] == "deviation_direction" for v in violations)
    assert fired is should_fire


# ---------------------------------------------------------------------------
# 3C.8 — plan_status
# ---------------------------------------------------------------------------


def test_plan_status_executed_but_text_says_missed_fires() -> None:
    # Clear §6 contradiction: coach is ignoring a payload signal the
    # backend explicitly computed. This is the highest-confidence
    # contradiction in the whole validator.
    v = check_readonly_field_contradictions(
        "You missed this workout.", {"plan_status": ["executed"]}
    )
    assert any(x["field"] == "plan_status" for x in v)


def test_plan_status_missed_but_text_says_ran_fires() -> None:
    v = check_readonly_field_contradictions(
        "Your execution was solid.", {"plan_status": ["missed"]}
    )
    assert any(x["field"] == "plan_status" for x in v)


def test_plan_status_unplanned_but_text_says_scheduled_fires() -> None:
    # §19.7 says unplanned runs must be acknowledged. Claiming the
    # run was scheduled is the loudest violation of that rule.
    v = check_readonly_field_contradictions(
        "This run was scheduled for Tuesday.", {"plan_status": ["unplanned"]}
    )
    assert any(x["field"] == "plan_status" for x in v)


def test_plan_status_agreement_does_not_fire() -> None:
    v = check_readonly_field_contradictions(
        "You executed the run well.", {"plan_status": ["executed"]}
    )
    assert not any(x["field"] == "plan_status" for x in v)


# ---------------------------------------------------------------------------
# 3C.8 — baseline_status
# ---------------------------------------------------------------------------


def test_baseline_insufficient_but_text_asserts_strong_fires() -> None:
    v = check_readonly_field_contradictions(
        "You've built a strong baseline.", {"baseline_status": ["insufficient"]}
    )
    assert any(x["field"] == "baseline_status" for x in v)


def test_baseline_strong_but_text_asserts_insufficient_fires() -> None:
    v = check_readonly_field_contradictions(
        "Your baseline is too thin to progress.",
        {"baseline_status": ["strong"]},
    )
    assert any(x["field"] == "baseline_status" for x in v)


def test_baseline_thin_middle_band_does_not_mis_fire() -> None:
    # 'thin' is the middle of the three-value enum. Generic coach
    # language about the runner's baseline should not trip a
    # contradiction, because neither the 'strong' nor the
    # 'insufficient' detector applies.
    v = check_readonly_field_contradictions(
        "Your baseline is still developing.", {"baseline_status": ["thin"]}
    )
    assert not any(x["field"] == "baseline_status" for x in v)


# ---------------------------------------------------------------------------
# 3C.8 — violated_rest_day
# ---------------------------------------------------------------------------


def test_violated_rest_day_true_but_text_claims_honored_fires() -> None:
    v = check_readonly_field_contradictions(
        "Nice work — you took your rest.",
        {"violated_rest_day": [True]},
    )
    assert any(x["field"] == "violated_rest_day" for x in v)


def test_violated_rest_day_false_but_text_claims_violated_fires() -> None:
    v = check_readonly_field_contradictions(
        "You violated your rest day with that run.",
        {"violated_rest_day": [False]},
    )
    assert any(x["field"] == "violated_rest_day" for x in v)


def test_violated_rest_day_agreement_does_not_fire() -> None:
    v = check_readonly_field_contradictions(
        "You ran on a scheduled rest day — let's talk recovery debt.",
        {"violated_rest_day": [True]},
    )
    assert not any(x["field"] == "violated_rest_day" for x in v)


# ---------------------------------------------------------------------------
# 3C.8 — adherence bands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pct,text,should_fire",
    [
        # Low band, coach asserts high → fire.
        (0.55, "Your adherence is high this week.", True),
        # High band, coach asserts low → fire.
        (0.95, "Your adherence is low.", True),
        # Agreement: low band, coach says low → OK.
        (0.55, "Adherence is low right now; let's reduce load.", False),
        # Medium band: neither low nor high detector applies.
        (0.80, "Adherence is high.", False),
    ],
)
def test_adherence_band_detector(pct: float, text: str, should_fire: bool) -> None:
    v = check_readonly_field_contradictions(text, {"adherence_runs_pct": [pct]})
    fired = any(x["field"] == "adherence_runs_pct" for x in v)
    assert fired is should_fire


def test_adherence_band_skipped_when_payload_values_cross_bands() -> None:
    # When the payload emits conflicting values (e.g. two different
    # weeks), we don't pick one arbitrarily — contradiction is not
    # well-defined, so the detector stays silent.
    v = check_readonly_field_contradictions(
        "Your adherence is high.",
        {"adherence_runs_pct": [0.55, 0.95]},  # low AND high
    )
    assert not any(x["field"] == "adherence_runs_pct" for x in v)


# ---------------------------------------------------------------------------
# 3C.8 — phase_kpi_priority is informational only (no contradiction)
# ---------------------------------------------------------------------------


def test_phase_kpi_priority_surfaces_in_observations_but_never_triggers_violations() -> (
    None
):
    observations = collect_readonly_field_observations(
        [{"phase_kpi_priority": ["HR Drift", "Aerobic Efficiency"]}]
    )
    v = check_readonly_field_contradictions(
        "This week we're going to lean into Tempo consistency instead.",
        observations,
    )
    assert not any(x["field"] == "phase_kpi_priority" for x in v)
    # But the observation itself is preserved so dashboards can diff.
    assert observations["phase_kpi_priority"] == [["HR Drift", "Aerobic Efficiency"]]


# ---------------------------------------------------------------------------
# 3C.9 — numeric grounding
# ---------------------------------------------------------------------------


def test_grounding_pool_collects_display_strings_and_numeric_substrings() -> None:
    # The 3B.7 display block emits strings like "5.00 mi" / "142 bpm"
    # / "72 %". The pool must capture both the full display string
    # AND its embedded numeric substrings so coaches can paraphrase
    # ("142bpm") without tripping grounding. Integer-vs-decimal
    # paraphrasing ("5" ↔ "5.00") is handled by the numeric-value
    # fallback in `_token_is_grounded` rather than pool membership.
    pool = collect_grounded_token_pool(
        [{"display": {"miles": "5.00 mi", "pace": "8:30/mi", "hr": "142 bpm"}}]
    )
    assert "5.00 mi" in pool
    assert "5.00" in pool
    assert "8:30/mi" in pool
    assert "142 bpm" in pool
    assert "142" in pool


def test_grounded_percent_token_is_not_flagged() -> None:
    pool = collect_grounded_token_pool([{"display": {"zc": "72 %"}}])
    findings = check_numeric_grounding("Zone compliance was 72%.", pool)
    assert findings == []


def test_ungrounded_percent_token_is_flagged() -> None:
    pool = collect_grounded_token_pool([{"display": {"zc": "72 %"}}])
    findings = check_numeric_grounding("Zone compliance was 84%.", pool)
    assert len(findings) == 1
    assert findings[0]["kind"] == "percent"
    assert "84" in findings[0]["token"]


def test_grounded_pace_token_is_not_flagged() -> None:
    pool = collect_grounded_token_pool([{"display": {"pace": "8:30/mi"}}])
    findings = check_numeric_grounding(
        "Target pace today is 8:30/mi on the main block.", pool
    )
    assert findings == []


def test_ungrounded_bpm_token_is_flagged() -> None:
    pool = collect_grounded_token_pool([{"display": {"hr": "142 bpm"}}])
    findings = check_numeric_grounding("You drifted to 168 bpm.", pool)
    assert any(f["kind"] == "bpm" for f in findings)
    assert any("168" in f["token"] for f in findings)


def test_grounded_miles_token_is_not_flagged() -> None:
    pool = collect_grounded_token_pool([{"display": {"miles": "5.00 mi"}}])
    findings = check_numeric_grounding("You logged 5 miles today.", pool)
    assert findings == []


def test_empty_pool_skips_grounding_entirely() -> None:
    # A turn with no tool output (pure memory response) is already a
    # §19.1 violation at the glossary layer, not a numeric one. The
    # grounding check intentionally returns no findings so we don't
    # double-flag.
    findings = check_numeric_grounding("Paced the Tempo at 8:30/mi.", set())
    assert findings == []


def test_whitespace_variants_match_pool() -> None:
    # "72 %" vs "72%" vs "72  %" — whitespace normalization keeps
    # coach paraphrasing from tripping the check.
    pool = collect_grounded_token_pool([{"display": {"zc": "72 %"}}])
    for variant in ("72%", "72 %", "72  %"):
        findings = check_numeric_grounding(f"Compliance was {variant}.", pool)
        assert findings == [], f"variant {variant!r} falsely flagged"


# ---------------------------------------------------------------------------
# validate_coach_response — end-to-end
# ---------------------------------------------------------------------------


def test_full_report_shape_is_stable_and_versioned() -> None:
    # Downstream dashboards rely on this envelope. If it changes,
    # bump the version deliberately — don't silently mutate.
    report: Dict[str, Any] = validate_coach_response("hi", [])
    assert report["version"] == 1
    assert set(report.keys()) == {
        "version",
        "readonly_violations",
        "ungrounded_numbers",
        "observed_readonly",
        "total_findings",
    }
    assert set(report["observed_readonly"].keys()) == set(READ_ONLY_FIELDS)
    assert report["total_findings"] == 0


def test_full_report_counts_findings_across_both_checks() -> None:
    # Single response, one §19.9 violation + one ungrounded number.
    report = validate_coach_response(
        "You ran it on target at 168 bpm.",
        [
            {
                "actual": {"deviation_direction": "too_hard"},
                "display": {"hr": "142 bpm"},
            }
        ],
    )
    assert any(
        v["field"] == "deviation_direction" for v in report["readonly_violations"]
    )
    assert any(f["kind"] == "bpm" for f in report["ungrounded_numbers"])
    assert report["total_findings"] == len(report["readonly_violations"]) + len(
        report["ungrounded_numbers"]
    )


def test_empty_response_text_produces_no_findings() -> None:
    report = validate_coach_response("", [{"plan_status": "missed"}])
    assert report["readonly_violations"] == []
    assert report["ungrounded_numbers"] == []
    assert report["total_findings"] == 0


def test_validator_never_mutates_tool_outputs() -> None:
    # Observability only — the validator must NEVER rewrite what the
    # tools returned (that would break the "payload is source of
    # truth" contract from §19.1).
    outputs = [{"plan_status": "executed", "display": {"miles": "5.00 mi"}}]
    snapshot = str(outputs)
    validate_coach_response("You executed it.", outputs)
    assert str(outputs) == snapshot


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_validator() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert hasattr(orchestrator, "validate_coach_response")
    assert orchestrator.validate_coach_response is validate_coach_response


def test_orchestrator_source_calls_validator_exactly_once() -> None:
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    # Exactly one call site = single integration point, no duplicate
    # reports per turn.
    assert src.count("validate_coach_response(") == 1


def test_orchestrator_source_guards_validator_with_env_flag() -> None:
    # §19 observability layer must be togglable off if it ever
    # generates noisy false positives in production; the env var
    # name is the documented contract.
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert "SMARTCOACH_RESPONSE_VALIDATOR_DISABLED" in src


def test_orchestrator_source_attaches_report_to_meta_validator_key() -> None:
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    # Downstream dashboards read meta["validator"]; keep this name
    # stable.
    assert 'meta["validator"]' in src


def test_orchestrator_source_defends_against_validator_exceptions() -> None:
    # A validator bug must never break a turn — wrapped in
    # try/except and logged as a warning, not propagated.
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert "response_validator_error" in src
