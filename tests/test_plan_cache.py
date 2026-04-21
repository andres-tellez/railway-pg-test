"""
V1.6 Phase B 3B.8 — per-request dedup + plan-regen invalidation tests
for :mod:`src.smartcoach_mobile_coach.plan_cache`.

Covers:

* Cache module primitives (``set_cached`` / ``get_cached`` / TTL /
  ``invalidate_user_plan_cache`` / non-caching of error envelopes /
  schema-version bump).
* Key isolation across tools, weeks, phases, timezones, and users
  (different ``kind`` / ``extra`` / ``tz`` / ``user`` entries coexist
  and are independently evictable).
* Tool-boundary wiring — second call within the same
  ``(user, kind, tz, today, extra)`` window is a hit and the service
  builder is NOT invoked again.
* Day-rollover is a natural cache miss — different ``today`` ⇒ new
  cache key.
* Invalidation on plan regen — ``tool_generate_training_plan`` drops
  every plan-tool entry for the user.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.smartcoach_mobile_coach import agent_tools, plan_cache


FIXED_USER_ID = "0b5e5a42-0000-4000-8000-000000008008"
OTHER_USER_ID = "0b5e5a42-0000-4000-8000-0000000080ff"


@pytest.fixture(autouse=True)
def _clear_plan_cache():
    """Each test gets a clean module-global dict."""
    plan_cache.clear_all()
    yield
    plan_cache.clear_all()


# ---------------------------------------------------------------------------
# Module primitives
# ---------------------------------------------------------------------------


def test_set_then_get_returns_same_payload():
    payload = {"schema_version": 1, "week_start": "2026-04-20"}
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    hit = plan_cache.get_cached(
        "weekly_plan",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    assert hit == payload


def test_get_returns_none_on_miss():
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        is None
    )


def test_error_envelopes_are_not_cached():
    """Transient ``no_plan`` / ``invalid_user_id`` must NOT be cached."""
    err = {"error": "no_plan", "message": "..."}
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        err,
        tz="UTC",
        today_iso="2026-04-22",
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        is None
    )


def test_ttl_zero_disables_caching():
    payload = {"schema_version": 1}
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        ttl_sec=0,
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        is None
    )


def test_ttl_expiry_evicts_entry():
    payload = {"schema_version": 1}
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        ttl_sec=1,
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        == payload
    )
    time.sleep(1.1)
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        is None
    )


def test_invalidate_user_clears_every_kind_and_key_for_that_user():
    payload = {"schema_version": 1}
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-27",
    )
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
    )
    plan_cache.set_cached(
        "phase_analysis",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="base",
    )
    plan_cache.set_cached(
        "weekly_plan",
        OTHER_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )

    dropped = plan_cache.invalidate_user_plan_cache(FIXED_USER_ID)
    assert dropped == 4
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        is None
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        is None
    )
    assert (
        plan_cache.get_cached(
            "phase_analysis",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="base",
        )
        is None
    )
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            OTHER_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        == payload
    )


def test_invalidate_returns_zero_when_nothing_to_drop():
    assert plan_cache.invalidate_user_plan_cache("no-such-user") == 0
    assert plan_cache.invalidate_user_plan_cache("") == 0


def test_schema_version_bump_is_a_cache_miss(monkeypatch):
    """Key embeds PLAN_CACHE_SCHEMA_VERSION so a deploy-bump is a natural miss."""
    payload = {"schema_version": 1}
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        payload,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        == payload
    )
    monkeypatch.setattr(plan_cache, "PLAN_CACHE_SCHEMA_VERSION", 99)
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        is None
    )


# ---------------------------------------------------------------------------
# Key isolation
# ---------------------------------------------------------------------------


def test_different_kinds_are_isolated():
    p_weekly = {"kind": "weekly"}
    p_overview = {"kind": "overview"}
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        p_weekly,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        p_overview,
        tz="UTC",
        today_iso="2026-04-22",
    )
    assert (
        plan_cache.get_cached(
            "weekly_plan",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
            extra="2026-04-20",
        )
        == p_weekly
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="UTC",
            today_iso="2026-04-22",
        )
        == p_overview
    )


def test_different_weeks_are_isolated():
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        {"w": 1},
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    )
    plan_cache.set_cached(
        "weekly_plan",
        FIXED_USER_ID,
        {"w": 2},
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-27",
    )
    assert plan_cache.get_cached(
        "weekly_plan",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-20",
    ) == {"w": 1}
    assert plan_cache.get_cached(
        "weekly_plan",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
        extra="2026-04-27",
    ) == {"w": 2}


def test_different_phases_are_isolated():
    plan_cache.set_cached(
        "phase_analysis",
        FIXED_USER_ID,
        {"p": "base"},
        tz="UTC",
        today_iso="2026-04-22",
        extra="base",
    )
    plan_cache.set_cached(
        "phase_analysis",
        FIXED_USER_ID,
        {"p": "build"},
        tz="UTC",
        today_iso="2026-04-22",
        extra="build",
    )
    assert plan_cache.get_cached(
        "phase_analysis",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
        extra="base",
    ) == {"p": "base"}
    assert plan_cache.get_cached(
        "phase_analysis",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
        extra="build",
    ) == {"p": "build"}


def test_different_timezones_are_isolated():
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        {"tz": "UTC"},
        tz="UTC",
        today_iso="2026-04-22",
    )
    assert (
        plan_cache.get_cached(
            "plan_overview",
            FIXED_USER_ID,
            tz="America/New_York",
            today_iso="2026-04-22",
        )
        is None
    )


def test_different_users_are_isolated():
    plan_cache.set_cached(
        "plan_overview",
        FIXED_USER_ID,
        {"u": "a"},
        tz="UTC",
        today_iso="2026-04-22",
    )
    plan_cache.set_cached(
        "plan_overview",
        OTHER_USER_ID,
        {"u": "b"},
        tz="UTC",
        today_iso="2026-04-22",
    )
    assert plan_cache.get_cached(
        "plan_overview",
        FIXED_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
    ) == {"u": "a"}
    assert plan_cache.get_cached(
        "plan_overview",
        OTHER_USER_ID,
        tz="UTC",
        today_iso="2026-04-22",
    ) == {"u": "b"}


# ---------------------------------------------------------------------------
# Tool-boundary wiring — dedup on repeat call
# ---------------------------------------------------------------------------


def _patch_today(monkeypatch, iso: str = "2026-04-22"):
    """Pin the resolved ``today`` for each cached tool.

    Each tool re-imports ``get_today_date_in_timezone`` via its service
    module's binding (same pattern tests for ``get_weekly_plan`` /
    ``get_plan_overview`` / ``get_phase_analysis`` already use), so we
    patch every service binding at once.
    """
    from datetime import date

    y, m, d = (int(p) for p in iso.split("-"))
    fn = lambda _tz: date(y, m, d)
    monkeypatch.setattr("src.services.plan.weekly_plan.get_today_date_in_timezone", fn)
    monkeypatch.setattr(
        "src.services.plan.plan_overview.get_today_date_in_timezone", fn
    )
    monkeypatch.setattr(
        "src.services.plan.phase_analysis.get_today_date_in_timezone", fn
    )


def test_weekly_plan_tool_second_call_is_cache_hit(monkeypatch):
    _patch_today(monkeypatch)
    payload = {"schema_version": 1, "week_start": "2026-04-20"}

    with patch(
        "src.services.plan.weekly_plan.build_weekly_plan_payload",
        return_value=payload,
    ) as builder:
        first = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-20",
        )
        second = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-20",
        )

    assert first == payload
    assert second == payload
    assert builder.call_count == 1


def test_plan_overview_tool_second_call_is_cache_hit(monkeypatch):
    _patch_today(monkeypatch)
    payload = {"schema_version": 1, "total_weeks": 12}

    with patch(
        "src.services.plan.plan_overview.build_plan_overview_payload",
        return_value=payload,
    ) as builder:
        first = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )
        second = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )

    assert first == payload
    assert second == payload
    assert builder.call_count == 1


def test_phase_analysis_tool_second_call_is_cache_hit(monkeypatch):
    _patch_today(monkeypatch)
    payload = {"schema_version": 1, "phase_id": "Base"}

    with patch(
        "src.services.plan.phase_analysis.build_phase_analysis_payload",
        return_value=payload,
    ) as builder:
        first = agent_tools.tool_get_phase_analysis(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            phase_id="Base",
        )
        second = agent_tools.tool_get_phase_analysis(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            phase_id="Base",
        )

    assert first == payload
    assert second == payload
    assert builder.call_count == 1


def test_phase_analysis_case_insensitive_cache_key(monkeypatch):
    """``"Base"`` and ``"base"`` should hit the same cache entry."""
    _patch_today(monkeypatch)
    payload = {"schema_version": 1, "phase_id": "Base"}

    with patch(
        "src.services.plan.phase_analysis.build_phase_analysis_payload",
        return_value=payload,
    ) as builder:
        agent_tools.tool_get_phase_analysis(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            phase_id="Base",
        )
        agent_tools.tool_get_phase_analysis(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            phase_id="base",
        )

    assert builder.call_count == 1


def test_weekly_plan_errors_are_not_cached(monkeypatch):
    """A ``no_plan`` envelope must miss again on the second call."""
    _patch_today(monkeypatch)
    err = {"error": "no_plan", "message": "..."}
    good = {"schema_version": 1}

    with patch(
        "src.services.plan.weekly_plan.build_weekly_plan_payload",
        side_effect=[err, good],
    ) as builder:
        first = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-20",
        )
        second = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-20",
        )

    assert first == err
    assert second == good
    assert builder.call_count == 2


def test_weekly_plan_invalid_user_short_circuits_before_cache():
    out = agent_tools.tool_get_weekly_plan(
        session=object(),
        internal_user_id="not-a-uuid",
        week_start_iso="2026-04-20",
    )
    assert out["error"] == "invalid_user_id"


def test_phase_analysis_missing_phase_id_short_circuits_before_cache():
    out = agent_tools.tool_get_phase_analysis(
        session=object(),
        internal_user_id=FIXED_USER_ID,
    )
    assert out["error"] == "missing_phase_id"


def test_plan_overview_day_rollover_is_cache_miss(monkeypatch):
    """Different ``today`` ⇒ new cache key ⇒ rebuild."""
    _patch_today(monkeypatch, "2026-04-22")
    payload_day1 = {"schema_version": 1, "day": 1}
    payload_day2 = {"schema_version": 1, "day": 2}

    with patch(
        "src.services.plan.plan_overview.build_plan_overview_payload",
        side_effect=[payload_day1, payload_day2],
    ) as builder:
        first = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )
        _patch_today(monkeypatch, "2026-04-23")
        second = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )

    assert first == payload_day1
    assert second == payload_day2
    assert builder.call_count == 2


def test_weekly_plan_different_week_is_separate_cache_key(monkeypatch):
    _patch_today(monkeypatch)
    payload_a = {"w": "a"}
    payload_b = {"w": "b"}
    with patch(
        "src.services.plan.weekly_plan.build_weekly_plan_payload",
        side_effect=[payload_a, payload_b],
    ) as builder:
        a = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-20",
        )
        b = agent_tools.tool_get_weekly_plan(
            session=object(),
            internal_user_id=FIXED_USER_ID,
            week_start_iso="2026-04-27",
        )
    assert a == payload_a
    assert b == payload_b
    assert builder.call_count == 2


def test_invalidation_drops_cached_entry_and_triggers_rebuild(monkeypatch):
    """Simulates plan-regen: cached entry is dropped and next call rebuilds."""
    _patch_today(monkeypatch)
    before = {"phase": "Base"}
    after = {"phase": "Build"}

    with patch(
        "src.services.plan.plan_overview.build_plan_overview_payload",
        side_effect=[before, after],
    ) as builder:
        first = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )
        assert first == before

        plan_cache.invalidate_user_plan_cache(FIXED_USER_ID)

        second = agent_tools.tool_get_plan_overview(
            session=object(),
            internal_user_id=FIXED_USER_ID,
        )
        assert second == after
        assert builder.call_count == 2
