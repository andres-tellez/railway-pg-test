"""
V1.6 Phase 3D — contract tests for the parallel tool dispatcher.

Covers:

* ``dispatch_tool_batch`` behavior on sequential and parallel paths.
* Cache hit short-circuits (no DB session touched).
* Stateful-tool batches forced onto the sequential path.
* Env toggle (`SMARTCOACH_TOOL_DISPATCH_PARALLEL=0`) disables
  parallelism even for otherwise-safe batches.
* Exception isolation — a failing tool does not poison siblings;
  the dispatcher returns an error envelope for the failing call
  and real outputs for the others.
* Per-call timing fields (`ms`, `json_serialize_ms`, `parallel`,
  `cached`) are present on every record in the caller's preferred
  order.
* Orchestrator wiring — the dispatcher is imported and called from
  the agent loop exactly once.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from src.smartcoach_mobile_coach import tool_dispatch
from src.smartcoach_mobile_coach.tool_dispatch import (
    STATEFUL_TOOLS,
    dispatch_tool_batch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tc(
    name: str, arguments: str = "{}", tc_id: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "id": tc_id or f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class _RecordingExecutor:
    """Stand-in for `execute_tool` that tracks call ordering / threading."""

    def __init__(
        self,
        handler_ms: float = 20.0,
        outputs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self.handler_ms = handler_ms
        self.outputs = outputs or {}
        self.calls: List[Dict[str, Any]] = []
        self.threads: List[str] = []
        self._lock = threading.Lock()

    def __call__(
        self,
        session: Any,
        internal_user_id: str,
        name: str,
        arguments: str,
        *,
        anchor_local_date: Optional[str] = None,
        plan_intake_state: Optional[Dict[str, Any]] = None,
        source_user_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        tname = threading.current_thread().name
        start = time.perf_counter()
        # Simulate I/O without burning CPU time under the pytest runner.
        time.sleep(self.handler_ms / 1000.0)
        with self._lock:
            self.calls.append(
                {
                    "name": name,
                    "arguments": arguments,
                    "thread": tname,
                    "started_at": start,
                    "ended_at": time.perf_counter(),
                }
            )
            self.threads.append(tname)
        return self.outputs.get(name, {"ok": True, "name": name})


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_stateful_tools_set_contains_expected_entries() -> None:
    assert "update_plan_intake" in STATEFUL_TOOLS
    assert "generate_training_plan" in STATEFUL_TOOLS
    assert "apply_plan_adjustments" in STATEFUL_TOOLS
    # Defensive — tools we expect to be read-only must NOT be marked stateful.
    for read_only in (
        "get_weekly_plan",
        "get_plan_overview",
        "get_phase_analysis",
        "get_user_context",
        "get_run_summary",
        "find_runs_by_date",
        "search_runs",
        "aggregate_runs_in_range",
        "get_training_kpis",
        "get_marathon_projection",
        "get_run_splits",
    ):
        assert (
            read_only not in STATEFUL_TOOLS
        ), f"read-only tool {read_only!r} was incorrectly marked stateful"


# ---------------------------------------------------------------------------
# Cache hit fast-path
# ---------------------------------------------------------------------------


def test_cache_hits_short_circuit_without_touching_execute_tool() -> None:
    cache: Dict[Tuple[str, str], Dict[str, Any]] = {
        ("get_user_context", "{}"): {"cached": "ctx"},
        ("get_weekly_plan", "{}"): {"cached": "plan"},
    }
    fake_execute = MagicMock()
    with patch("src.smartcoach_mobile_coach.agent_tools.execute_tool", fake_execute):
        out = dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[_make_tc("get_user_context"), _make_tc("get_weekly_plan")],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache=cache,
        )
    assert fake_execute.called is False
    names = [e["name"] for e in out]
    assert names == ["get_user_context", "get_weekly_plan"]
    for e in out:
        assert e["cached"] is True
        assert e["ms"] == 0.0
        assert e["parallel"] is False
        assert "tool_content" in e


# ---------------------------------------------------------------------------
# Sequential path — stateful / singleton batches
# ---------------------------------------------------------------------------


def test_single_call_runs_sequentially_on_shared_session() -> None:
    recorder = _RecordingExecutor(handler_ms=5.0)
    cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    shared_session = MagicMock(name="shared_session")
    with patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        dispatch_tool_batch(
            session=shared_session,
            internal_user_id="u-1",
            calls=[_make_tc("get_weekly_plan")],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache=cache,
        )
    assert len(recorder.calls) == 1
    assert recorder.threads[0] == threading.current_thread().name


def test_batch_with_stateful_tool_forces_sequential_and_shared_session() -> None:
    recorder = _RecordingExecutor(handler_ms=5.0)
    cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    shared_session = MagicMock(name="shared_session")
    with patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        out = dispatch_tool_batch(
            session=shared_session,
            internal_user_id="u-1",
            calls=[
                _make_tc("update_plan_intake", '{"updates": {"training_days": 4}}'),
                _make_tc("get_weekly_plan"),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache=cache,
        )
    # All calls must have landed on the caller's thread (sequential path).
    main_thread = threading.current_thread().name
    assert [c["thread"] for c in recorder.calls] == [main_thread, main_thread]
    for e in out:
        assert e["parallel"] is False


# ---------------------------------------------------------------------------
# Parallel path — read-only batches
# ---------------------------------------------------------------------------


def test_parallel_batch_runs_on_worker_threads_with_fresh_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", raising=False)
    recorder = _RecordingExecutor(handler_ms=20.0)
    fresh_sessions: List[MagicMock] = []

    def _session_factory() -> MagicMock:
        s = MagicMock(name=f"parallel_session_{len(fresh_sessions)}")
        fresh_sessions.append(s)
        return s

    cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with patch("src.db.db_session.SessionLocal", _session_factory), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        out = dispatch_tool_batch(
            session=MagicMock(name="caller_session"),
            internal_user_id="u-1",
            calls=[
                _make_tc("get_user_context"),
                _make_tc("get_weekly_plan"),
                _make_tc("get_plan_overview"),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache=cache,
        )
    # Three fresh sessions, each closed after its task.
    assert len(fresh_sessions) == 3
    for s in fresh_sessions:
        s.close.assert_called_once()
    # Calls ran on non-main threads (ThreadPoolExecutor workers).
    main_thread = threading.current_thread().name
    off_main = [c for c in recorder.calls if c["thread"] != main_thread]
    assert (
        len(off_main) == 3
    ), f"expected all 3 tasks on worker threads; calls={recorder.calls}"
    # Each record reports parallel=True and non-zero ms.
    for e in out:
        assert e["parallel"] is True
        assert e["cached"] is False
        assert e["ms"] > 0.0
        assert "tool_content" in e


def test_parallel_batch_total_time_beats_sequential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three 80ms tools on a thread pool must finish in much less than 3×80ms."""
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", raising=False)
    recorder = _RecordingExecutor(handler_ms=80.0)

    with patch("src.db.db_session.SessionLocal", lambda: MagicMock(name="s")), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        t0 = time.perf_counter()
        dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[
                _make_tc("get_user_context"),
                _make_tc("get_weekly_plan"),
                _make_tc("get_plan_overview"),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
        wall_ms = (time.perf_counter() - t0) * 1000.0
    # Sequential would be ≥ 240ms. Parallel should land well under that
    # (loose bound to avoid CI flake — the key property is "not linear").
    assert (
        wall_ms < 200.0
    ), f"parallel dispatch did not beat sequential: wall_ms={wall_ms:.1f}"


def test_env_flag_disables_parallel_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", "0")
    recorder = _RecordingExecutor(handler_ms=5.0)
    with patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[
                _make_tc("get_user_context"),
                _make_tc("get_weekly_plan"),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
    main_thread = threading.current_thread().name
    assert [c["thread"] for c in recorder.calls] == [main_thread, main_thread]


# ---------------------------------------------------------------------------
# Exception isolation
# ---------------------------------------------------------------------------


def test_parallel_task_exception_does_not_poison_siblings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", raising=False)

    def _raising_execute(
        session: Any,
        internal_user_id: str,
        name: str,
        arguments: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if name == "get_weekly_plan":
            raise RuntimeError("simulated db failure")
        time.sleep(0.01)
        return {"ok": True, "name": name}

    with patch("src.db.db_session.SessionLocal", lambda: MagicMock(name="s")), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool",
        side_effect=_raising_execute,
    ):
        out = dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[
                _make_tc("get_user_context"),
                _make_tc("get_weekly_plan"),
                _make_tc("get_plan_overview"),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
    by_name = {e["name"]: e for e in out}
    assert by_name["get_user_context"]["out"] == {
        "ok": True,
        "name": "get_user_context",
    }
    assert by_name["get_plan_overview"]["out"] == {
        "ok": True,
        "name": "get_plan_overview",
    }
    assert by_name["get_weekly_plan"]["out"]["error"] == "tool_execution_failed"


# ---------------------------------------------------------------------------
# Per-call timing / result envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "calls,expected_order",
    [
        (
            [_make_tc("get_user_context"), _make_tc("get_weekly_plan")],
            ["get_user_context", "get_weekly_plan"],
        ),
        (
            [
                _make_tc("get_plan_overview"),
                _make_tc("get_phase_analysis"),
                _make_tc("get_user_context"),
            ],
            ["get_plan_overview", "get_phase_analysis", "get_user_context"],
        ),
    ],
)
def test_output_order_matches_input_order(
    calls: List[Dict[str, Any]],
    expected_order: List[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", raising=False)
    recorder = _RecordingExecutor(handler_ms=5.0)
    with patch("src.db.db_session.SessionLocal", lambda: MagicMock(name="s")), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        out = dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=calls,
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
    assert [e["name"] for e in out] == expected_order


def test_result_envelope_has_all_required_fields() -> None:
    recorder = _RecordingExecutor(handler_ms=5.0)
    with patch("src.db.db_session.SessionLocal", lambda: MagicMock(name="s")), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        out = dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[_make_tc("get_user_context"), _make_tc("get_weekly_plan")],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
    for e in out:
        for key in (
            "tc",
            "name",
            "arguments",
            "out",
            "cached",
            "ms",
            "json_serialize_ms",
            "tool_content",
            "parallel",
        ):
            assert key in e, f"missing field {key!r} in dispatcher envelope"


def test_cache_populated_after_dispatch_with_same_keys_as_legacy_path() -> None:
    recorder = _RecordingExecutor(handler_ms=5.0)
    cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with patch("src.db.db_session.SessionLocal", lambda: MagicMock(name="s")), patch(
        "src.smartcoach_mobile_coach.agent_tools.execute_tool", side_effect=recorder
    ):
        dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[
                _make_tc("get_user_context", '{"arg":1}'),
                _make_tc("get_weekly_plan", '{"arg":2}'),
            ],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache=cache,
        )
    assert ("get_user_context", '{"arg":1}') in cache
    assert ("get_weekly_plan", '{"arg":2}') in cache


def test_empty_call_list_returns_empty_list() -> None:
    assert (
        dispatch_tool_batch(
            session=MagicMock(),
            internal_user_id="u-1",
            calls=[],
            anchor_local_date="2026-04-21",
            plan_intake_state=None,
            source_user_message=None,
            tool_result_cache={},
        )
        == []
    )


# ---------------------------------------------------------------------------
# Env / knob helpers
# ---------------------------------------------------------------------------


def test_max_workers_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_MAX_WORKERS", "2")
    assert tool_dispatch._parallel_max_workers() == 2
    monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_MAX_WORKERS", "99")
    # Hard clamp at 8 to prevent operators from stampeding the DB pool.
    assert tool_dispatch._parallel_max_workers() == 8
    monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_MAX_WORKERS", "bad")
    assert tool_dispatch._parallel_max_workers() == tool_dispatch._DEFAULT_MAX_WORKERS
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_MAX_WORKERS", raising=False)
    assert tool_dispatch._parallel_max_workers() == tool_dispatch._DEFAULT_MAX_WORKERS


def test_parallel_enabled_default_on_and_respects_falsy_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", raising=False)
    assert tool_dispatch._parallel_enabled() is True
    for val in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", val)
        assert tool_dispatch._parallel_enabled() is False
    monkeypatch.setenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL", "1")
    assert tool_dispatch._parallel_enabled() is True


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_orchestrator_imports_and_calls_dispatcher_exactly_once() -> None:
    from src.smartcoach_mobile_coach import orchestrator

    assert orchestrator.dispatch_tool_batch is dispatch_tool_batch
    src = Path("src/smartcoach_mobile_coach/orchestrator.py").read_text(
        encoding="utf-8"
    )
    # Exactly one dispatch_tool_batch(…) call from the agent loop.
    assert src.count("dispatch_tool_batch(\n") == 1
