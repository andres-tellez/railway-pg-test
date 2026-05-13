from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.smartcoach_mobile_coach import readiness_gate


@dataclass
class _FakeAssessment:
    payload: Dict[str, Any]

    def as_api_dict(self) -> Dict[str, Any]:
        return dict(self.payload)


def _state(*, with_prior_readiness: bool = False) -> Dict[str, Any]:
    ux: Dict[str, Any] = {}
    if with_prior_readiness:
        ux["plan_generation_readiness"] = {
            "trace_id": "tr-prior",
            "policy_version": "policy.v1.0",
            "decision": "allow",
            "readiness_level": "ready",
            "evidence_snapshot_id": "ev-001",
        }
    return {
        "draft": {
            "race_distance": "Marathon",
            "race_date": "2026-10-11",
            "primary_goal": "Target Time",
            "target_time": "3:30:00",
            "training_days": ["Mon", "Wed", "Sat"],
        },
        "ux": ux,
    }


def _plan_request() -> Dict[str, Any]:
    return {
        "race_distance": "Marathon",
        "race_date": "2026-10-11",
        "primary_goal": "Target Time",
        "target_time": "3:30:00",
        "training_days": ["Mon", "Wed", "Sat"],
    }


def test_get_or_compute_readiness_gate_cache_hit_reuses_snapshot(monkeypatch):
    readiness_gate._clear_readiness_gate_cache_for_tests()
    calls = {"build": 0, "eval": 0}

    def _build(*_args, **_kwargs):
        calls["build"] += 1
        return _FakeAssessment(
            {
                "evidence_snapshot_id": "ev-001",
                "activity_summary": {"activities_found": 5},
            }
        )

    def _eval(*_args, **_kwargs):
        calls["eval"] += 1
        return {
            "trace_id": "tr-001",
            "policy_version": "policy.v1.0",
            "decision": "allow",
            "readiness_level": "ready",
            "evidence_snapshot_id": "ev-001",
            "reason_codes": [],
        }

    monkeypatch.setattr(
        readiness_gate, "build_pre_generation_runner_assessment", _build
    )
    monkeypatch.setattr(readiness_gate, "evaluate_plan_generation_readiness", _eval)

    first = readiness_gate.get_or_compute_readiness_gate(
        session=object(),
        internal_user_id="u-1",
        plan_request=_plan_request(),
        plan_intake_state=_state(with_prior_readiness=True),
        alignment_enabled=True,
    )
    second = readiness_gate.get_or_compute_readiness_gate(
        session=object(),
        internal_user_id="u-1",
        plan_request=_plan_request(),
        plan_intake_state=_state(with_prior_readiness=True),
        alignment_enabled=True,
    )

    assert first.cache_status == "miss"
    assert second.cache_status == "hit"
    assert calls == {"build": 1, "eval": 1}
    assert first.readiness_api["trace_id"] == second.readiness_api["trace_id"]
    assert (
        first.readiness_api["evidence_snapshot_id"]
        == second.readiness_api["evidence_snapshot_id"]
    )


def test_get_or_compute_readiness_gate_cache_expiry_recomputes(monkeypatch):
    readiness_gate._clear_readiness_gate_cache_for_tests()
    monkeypatch.setenv("SMARTCOACH_READINESS_GATE_CACHE_TTL_SEC", "5")

    import src.smartcoach_mobile_coach.intake.readiness_cache as readiness_rc

    calls = {"build": 0, "eval": 0}

    def _build(*_args, **_kwargs):
        calls["build"] += 1
        return _FakeAssessment(
            {
                "evidence_snapshot_id": f"ev-{calls['build']}",
                "activity_summary": {"activities_found": 5},
            }
        )

    def _eval(*_args, **_kwargs):
        calls["eval"] += 1
        return {
            "trace_id": f"tr-{calls['eval']}",
            "policy_version": "policy.v1.0",
            "decision": "allow",
            "readiness_level": "ready",
            "evidence_snapshot_id": f"ev-{calls['eval']}",
            "reason_codes": [],
        }

    now = {"value": 100.0}

    def _mono() -> float:
        return now["value"]

    monkeypatch.setattr(readiness_rc.time, "monotonic", _mono)
    monkeypatch.setattr(
        readiness_gate, "build_pre_generation_runner_assessment", _build
    )
    monkeypatch.setattr(readiness_gate, "evaluate_plan_generation_readiness", _eval)

    first = readiness_gate.get_or_compute_readiness_gate(
        session=object(),
        internal_user_id="u-1",
        plan_request=_plan_request(),
        plan_intake_state=_state(with_prior_readiness=True),
        alignment_enabled=True,
    )
    now["value"] = 106.0
    second = readiness_gate.get_or_compute_readiness_gate(
        session=object(),
        internal_user_id="u-1",
        plan_request=_plan_request(),
        plan_intake_state=_state(with_prior_readiness=True),
        alignment_enabled=True,
    )

    assert first.cache_status == "miss"
    assert second.cache_status == "miss"
    assert calls == {"build": 2, "eval": 2}
    assert first.readiness_api["trace_id"] != second.readiness_api["trace_id"]
