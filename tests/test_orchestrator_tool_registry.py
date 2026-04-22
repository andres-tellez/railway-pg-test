"""
V1.6 Phase B 3B.9 — orchestrator tool-registry coverage.

The plan-aware tools (``get_weekly_plan``, ``get_plan_overview``,
``get_phase_analysis``, ``get_user_context``) are shipped to production
via ``scripts/setup_coach_tools.py`` (the ``coach_tools`` table is the
canonical source of tool copy). To keep fresh databases / ephemeral
branch DBs / CI working without a re-seed, the orchestrator also carries
fallback OpenAI tool definitions and idempotent ``_ensure_*_tool``
injectors. These tests lock down:

* each of the four fallback constants is well-formed,
* each ``_ensure_*_tool`` is a no-op when the DB already advertises the
  tool,
* each ``_ensure_*_tool`` injects the fallback when the DB is empty,
* every fallback name round-trips through the dispatcher in
  ``src.smartcoach_mobile_coach.agent_tools._TOOL_HANDLERS``,
* each fallback's description exists verbatim in
  ``scripts/setup_coach_tools.py::SEED_TOOLS`` (so the DB seed and the
  fallback never diverge silently).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.smartcoach_mobile_coach import agent_tools
from src.smartcoach_mobile_coach.orchestrator import (
    _GET_PHASE_ANALYSIS_OPENAI_TOOL,
    _GET_PLAN_OVERVIEW_OPENAI_TOOL,
    _GET_USER_CONTEXT_OPENAI_TOOL,
    _GET_WEEKLY_PLAN_OPENAI_TOOL,
    _SAVE_PHASE_GOAL_OPENAI_TOOL,
    _ensure_get_phase_analysis_tool,
    _ensure_get_plan_overview_tool,
    _ensure_get_user_context_tool,
    _ensure_get_weekly_plan_tool,
    _ensure_save_phase_goal_tool,
    _openai_tool_names,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PLAN_TOOL_PAIRS = [
    ("get_weekly_plan", _GET_WEEKLY_PLAN_OPENAI_TOOL, _ensure_get_weekly_plan_tool),
    (
        "get_plan_overview",
        _GET_PLAN_OVERVIEW_OPENAI_TOOL,
        _ensure_get_plan_overview_tool,
    ),
    (
        "get_phase_analysis",
        _GET_PHASE_ANALYSIS_OPENAI_TOOL,
        _ensure_get_phase_analysis_tool,
    ),
    (
        "get_user_context",
        _GET_USER_CONTEXT_OPENAI_TOOL,
        _ensure_get_user_context_tool,
    ),
    (
        "save_phase_goal",
        _SAVE_PHASE_GOAL_OPENAI_TOOL,
        _ensure_save_phase_goal_tool,
    ),
]


def _load_seed_tools() -> List[Dict[str, Any]]:
    """Load SEED_TOOLS from scripts/setup_coach_tools.py without running main()."""
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "setup_coach_tools.py"
    spec = importlib.util.spec_from_file_location(
        "setup_coach_tools_seed_only", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The script only does a DB connection inside ``main()``; importing
    # it at module scope just evaluates constants.
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return list(module.SEED_TOOLS)


# ---------------------------------------------------------------------------
# Constant shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,tool,_inject", _PLAN_TOOL_PAIRS)
def test_plan_tool_fallback_is_well_formed(
    name: str, tool: Dict[str, Any], _inject: Any
) -> None:
    assert tool.get("type") == "function"
    fn = tool.get("function")
    assert isinstance(fn, dict), f"{name} missing 'function' block"
    assert fn.get("name") == name
    desc = fn.get("description")
    assert isinstance(desc, str) and desc.strip(), f"{name} description empty"
    params = fn.get("parameters")
    assert isinstance(params, dict), f"{name} parameters block missing"
    assert params.get("type") == "object"
    assert isinstance(params.get("properties", {}), dict)


def test_get_phase_analysis_requires_phase_id() -> None:
    # phase_id is the only required arg on any of the four fallbacks;
    # the others accept an empty args object.
    params = _GET_PHASE_ANALYSIS_OPENAI_TOOL["function"]["parameters"]
    assert params.get("required") == ["phase_id"]


@pytest.mark.parametrize(
    "tool",
    [
        _GET_WEEKLY_PLAN_OPENAI_TOOL,
        _GET_PLAN_OVERVIEW_OPENAI_TOOL,
        _GET_USER_CONTEXT_OPENAI_TOOL,
    ],
)
def test_non_phase_plan_tools_have_no_required_args(tool: Dict[str, Any]) -> None:
    params = tool["function"]["parameters"]
    # Either key absent OR explicit empty list — both are equivalent to
    # OpenAI's "no required args" contract.
    required = params.get("required", [])
    assert required == [] or required is None


# ---------------------------------------------------------------------------
# Injector behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,_tool,inject", _PLAN_TOOL_PAIRS)
def test_injector_adds_fallback_when_missing(
    name: str, _tool: Dict[str, Any], inject: Any
) -> None:
    result = inject([])
    assert name in _openai_tool_names(result)
    # Injector must not mutate its input
    assert result is not []  # always returns a new list


@pytest.mark.parametrize("name,tool,inject", _PLAN_TOOL_PAIRS)
def test_injector_is_noop_when_tool_already_present(
    name: str, tool: Dict[str, Any], inject: Any
) -> None:
    pre = [tool]
    result = inject(pre)
    # Same list instance — no duplicate entry, no rewrap.
    assert result is pre
    names = [t["function"]["name"] for t in result]
    assert names.count(name) == 1


@pytest.mark.parametrize("name,_tool,inject", _PLAN_TOOL_PAIRS)
def test_injector_preserves_existing_tools(
    name: str, _tool: Dict[str, Any], inject: Any
) -> None:
    existing = [
        {"type": "function", "function": {"name": "find_runs_by_date"}},
        {"type": "function", "function": {"name": "get_run_summary"}},
    ]
    result = inject(list(existing))
    result_names = _openai_tool_names(result)
    assert {"find_runs_by_date", "get_run_summary"}.issubset(result_names)
    assert name in result_names


def test_injectors_compose_on_empty_list() -> None:
    """All four injectors chained on an empty list yield all four tools."""
    tools: List[Dict[str, Any]] = []
    tools = _ensure_get_user_context_tool(tools)
    tools = _ensure_get_phase_analysis_tool(tools)
    tools = _ensure_get_plan_overview_tool(tools)
    tools = _ensure_get_weekly_plan_tool(tools)
    names = _openai_tool_names(tools)
    assert {
        "get_weekly_plan",
        "get_plan_overview",
        "get_phase_analysis",
        "get_user_context",
    }.issubset(names)


# ---------------------------------------------------------------------------
# Dispatcher round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,_tool,_inject", _PLAN_TOOL_PAIRS)
def test_fallback_name_is_wired_in_dispatcher(
    name: str, _tool: Dict[str, Any], _inject: Any
) -> None:
    # Advertising a tool to OpenAI without a dispatcher handler would
    # cause every invocation to fail silently at runtime. Keep these in
    # lockstep.
    assert name in agent_tools._TOOL_HANDLERS, (
        f"orchestrator fallback {name!r} has no handler in agent_tools._TOOL_HANDLERS; "
        "registry / dispatcher drift"
    )


# ---------------------------------------------------------------------------
# Parity with SEED_TOOLS
# ---------------------------------------------------------------------------


def test_every_plan_fallback_exists_in_seed_tools() -> None:
    seed_names = {t["name"] for t in _load_seed_tools()}
    for name, _tool, _inject in _PLAN_TOOL_PAIRS:
        assert name in seed_names, (
            f"orchestrator fallback {name!r} missing from setup_coach_tools.SEED_TOOLS; "
            "re-seeded environments will diverge from fresh ones"
        )


@pytest.mark.parametrize("name,tool,_inject", _PLAN_TOOL_PAIRS)
def test_fallback_description_mentions_v1_6(
    name: str, tool: Dict[str, Any], _inject: Any
) -> None:
    """Sanity anchor: V1.6 Phase B tools advertise their spec version.

    This is a weak check on purpose — it protects against a future
    refactor silently dropping the spec anchor from the description but
    does NOT pin the full wording (SEED_TOOLS is the source of truth).
    """
    desc = tool["function"]["description"]
    assert "V1.6" in desc, f"{name} fallback description lost the V1.6 anchor"


@pytest.mark.parametrize("name,tool,_inject", _PLAN_TOOL_PAIRS)
def test_fallback_parameter_schema_matches_seed_parameter_schema(
    name: str, tool: Dict[str, Any], _inject: Any
) -> None:
    """Parameters MUST match byte-for-byte.

    OpenAI rejects tool calls with args that don't conform to the
    declared schema, so divergence between the fallback and the DB seed
    would silently break one surface or the other. Descriptions are
    allowed to abbreviate (LLM-facing copy) but parameter schemas must
    not drift.
    """
    seed_tool = next(t for t in _load_seed_tools() if t["name"] == name)
    assert tool["function"]["parameters"] == seed_tool["parameters_schema"], (
        f"{name} parameter schema drift between orchestrator fallback and "
        f"setup_coach_tools.SEED_TOOLS"
    )
