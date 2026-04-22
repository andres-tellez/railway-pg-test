"""
V1.6 Phase 3D — parallel tool dispatcher for the mobile coach loop.

**Why.** The OpenAI agent loop in :mod:`orchestrator` frequently emits
multiple independent tool calls in a single round (classic example:
``get_user_context`` + ``get_weekly_plan`` on an opening turn; or
``find_runs_by_date`` + ``get_run_summary`` when resolving "today's
run"). The original implementation executed them **serially** inside a
``for`` loop, which means a round with 3 pure-read tool calls takes
``tool1_ms + tool2_ms + tool3_ms`` instead of ``max(…)``.

This module extracts the tool-execution step into a small batch
dispatcher that can run independent calls in parallel on a thread pool.
It intentionally preserves the existing sequential semantics for any
call that touches shared mutable state.

**Design constraints.**

* SQLAlchemy ``Session`` instances are **not thread-safe**; concurrent
  use of a single session across threads corrupts state. Every parallel
  task therefore opens its own fresh session via
  :func:`src.db.db_session.SessionLocal` and closes it deterministically.
* ``update_plan_intake`` and ``generate_training_plan`` are explicitly
  **ordered** by :func:`orchestrator._ordered_plan_tool_calls` — the
  second reads state produced by the first — so batches containing any
  of them stay on the sequential code path with the shared caller
  session.
* ``tool_result_cache`` (per-turn dedup keyed by ``(name, args_json)``)
  must behave identically whether a batch is parallelized or not; the
  dispatcher checks the cache first and only queues cache misses.
* The dispatcher never changes the public return shape of
  ``execute_tool``; it only reshuffles *when* the call happens.

**Observability.** Each dispatched call produces a ``timing`` entry
compatible with the shape ``loop_entry["tools"]`` used today
(``name`` / ``ms`` / ``cached`` / ``json_serialize_ms``), plus a new
``parallel`` flag set to ``True`` whenever the call ran inside the
thread pool so a slow-turn investigation can immediately see whether
parallelism kicked in.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Tools whose execution mutates state later calls in the same batch
# depend on. The orchestrator already sorts these first via
# ``_ordered_plan_tool_calls``; here we refuse to parallelize any batch
# that contains them so the ordering is trivially preserved.
STATEFUL_TOOLS: FrozenSet[str] = frozenset(
    {
        "update_plan_intake",
        "generate_training_plan",
    }
)

# Hard cap on worker threads. The coach rarely emits >3 tool calls in
# one round; higher caps just add thread-startup overhead without a
# parallelism win.
_DEFAULT_MAX_WORKERS = 4


def _parallel_max_workers() -> int:
    """Return the effective thread-pool size, respecting env override."""
    raw = os.getenv("SMARTCOACH_TOOL_DISPATCH_MAX_WORKERS", "").strip()
    if not raw:
        return _DEFAULT_MAX_WORKERS
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_WORKERS
    if parsed < 1:
        return 1
    if parsed > 8:
        return 8
    return parsed


def _parallel_enabled() -> bool:
    """Disable flag so operators can force sequential dispatch for debugging."""
    raw = (os.getenv("SMARTCOACH_TOOL_DISPATCH_PARALLEL") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _batch_is_parallelizable(names: List[str]) -> bool:
    """True when the batch is safe to run on a thread pool."""
    if not _parallel_enabled():
        return False
    if len(names) < 2:
        return False
    return not any(n in STATEFUL_TOOLS for n in names)


def _execute_one_isolated(
    internal_user_id: str,
    name: str,
    arguments: str,
    anchor_local_date: Optional[str],
    plan_intake_state: Optional[Dict[str, Any]],
    source_user_message: Optional[str],
) -> Dict[str, Any]:
    """Run a single tool on a fresh session and close it.

    Sessions are **not thread-safe** so every parallel task must own
    its session. ``SessionLocal`` is imported lazily to avoid coupling
    this module to flask/sqlalchemy at import time (keeps the unit
    tests light and the dispatcher easy to mock).
    """
    from src.db.db_session import SessionLocal
    from src.smartcoach_mobile_coach.agent_tools import execute_tool

    session: Session = SessionLocal()
    try:
        return execute_tool(
            session,
            internal_user_id,
            name,
            arguments,
            anchor_local_date=anchor_local_date,
            plan_intake_state=plan_intake_state,
            source_user_message=source_user_message,
        )
    finally:
        try:
            session.close()
        except Exception:
            logger.debug("[tool_dispatch] session.close failed; ignoring")


def dispatch_tool_batch(
    session: Session,
    internal_user_id: str,
    calls: List[Dict[str, Any]],
    *,
    anchor_local_date: Optional[str],
    plan_intake_state: Optional[Dict[str, Any]],
    source_user_message: Optional[str],
    tool_result_cache: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Execute one round of tool calls, parallelizing when safe.

    ``calls`` is the list of tool-call descriptors from the OpenAI
    response (already sorted by the caller via
    :func:`_ordered_plan_tool_calls`). Returns one record per input
    call in the **same order**:

    .. code-block:: python

        [
            {
                "tc": <tool_call dict, unchanged>,
                "name": <str>,
                "arguments": <json string>,
                "out": <tool output dict>,
                "cached": <bool>,
                "ms": <float>,           # wall-clock inside execute_tool (0 for cache hits)
                "json_serialize_ms": <float>,
                "tool_content": <serialized JSON string>,
                "parallel": <bool>,
            },
            ...
        ]

    Guarantees:

    * Cache hits are resolved synchronously and return ``ms == 0``.
    * Cache misses populate ``tool_result_cache`` once the call
      completes (mirrors the legacy code path's ordering — the cache
      sees the same ``(name, arguments)`` keys it saw before).
    * When the batch is parallelizable, cache-miss calls run on a
      shared :class:`ThreadPoolExecutor`; otherwise the legacy
      sequential path executes against the shared caller session.
    * JSON serialization runs on the caller thread regardless —
      ``json.dumps`` of a Python dict is CPU-only and cheap; moving it
      off-thread offers no benefit and complicates timing.
    """
    if not calls:
        return []

    # Pre-resolve names + args so the parallel decision is based on the
    # full batch, not a partially-processed one.
    entries: List[Dict[str, Any]] = []
    for tc in calls:
        fn = tc.get("function") or {}
        entries.append(
            {
                "tc": tc,
                "name": str(fn.get("name") or ""),
                "arguments": str(fn.get("arguments") or "{}"),
            }
        )

    names = [e["name"] for e in entries]
    go_parallel = _batch_is_parallelizable(names)

    # --- Pass 1: resolve cache hits, queue misses ----------------------
    pending: List[Tuple[int, Dict[str, Any]]] = []
    for idx, e in enumerate(entries):
        sig = (e["name"], e["arguments"])
        if sig in tool_result_cache:
            e["out"] = tool_result_cache[sig]
            e["cached"] = True
            e["ms"] = 0.0
            e["parallel"] = False
        else:
            pending.append((idx, e))

    # --- Pass 2: execute misses ---------------------------------------
    if pending:
        if go_parallel and len(pending) >= 2:
            _run_pending_in_parallel(
                internal_user_id,
                pending,
                anchor_local_date=anchor_local_date,
                plan_intake_state=plan_intake_state,
                source_user_message=source_user_message,
            )
        else:
            _run_pending_sequential(
                session,
                internal_user_id,
                pending,
                anchor_local_date=anchor_local_date,
                plan_intake_state=plan_intake_state,
                source_user_message=source_user_message,
            )

        # Populate per-turn cache deterministically in input order so
        # callbacks that inspect the cache (validator, tests) see the
        # same keys as the legacy sequential code path.
        for _, e in pending:
            tool_result_cache[(e["name"], e["arguments"])] = e["out"]

    # --- Pass 3: serialize payloads for the OpenAI tool role ----------
    for e in entries:
        _tj0 = time.perf_counter()
        e["tool_content"] = json.dumps(e["out"])
        e["json_serialize_ms"] = round((time.perf_counter() - _tj0) * 1000, 2)

    return entries


def _run_pending_sequential(
    session: Session,
    internal_user_id: str,
    pending: List[Tuple[int, Dict[str, Any]]],
    *,
    anchor_local_date: Optional[str],
    plan_intake_state: Optional[Dict[str, Any]],
    source_user_message: Optional[str],
) -> None:
    """Legacy path: execute each pending call on the shared session."""
    from src.smartcoach_mobile_coach.agent_tools import execute_tool

    for _, e in pending:
        tt0 = time.perf_counter()
        e["out"] = execute_tool(
            session,
            internal_user_id,
            e["name"],
            e["arguments"],
            anchor_local_date=anchor_local_date,
            plan_intake_state=plan_intake_state,
            source_user_message=source_user_message,
        )
        e["ms"] = round((time.perf_counter() - tt0) * 1000, 2)
        e["cached"] = False
        e["parallel"] = False


def _run_pending_in_parallel(
    internal_user_id: str,
    pending: List[Tuple[int, Dict[str, Any]]],
    *,
    anchor_local_date: Optional[str],
    plan_intake_state: Optional[Dict[str, Any]],
    source_user_message: Optional[str],
) -> None:
    """Thread-pool dispatch; one fresh DB session per task.

    Thread pool is built just-in-time (no long-lived executor) so
    ``SessionLocal``'s engine pool can retire idle connections between
    turns. This is fine because tool calls are bursts, not a constant
    stream.
    """
    max_workers = min(_parallel_max_workers(), len(pending))
    with ThreadPoolExecutor(
        max_workers=max_workers, thread_name_prefix="coach-tool"
    ) as pool:
        futures: List[Tuple[Dict[str, Any], float, Future[Dict[str, Any]]]] = []
        for _, e in pending:
            t0 = time.perf_counter()
            fut = pool.submit(
                _execute_one_isolated,
                internal_user_id,
                e["name"],
                e["arguments"],
                anchor_local_date,
                plan_intake_state,
                source_user_message,
            )
            futures.append((e, t0, fut))

        for e, t0, fut in futures:
            try:
                e["out"] = fut.result()
            except Exception as exc:
                logger.exception(
                    "[tool_dispatch] parallel tool %s failed: %s", e["name"], exc
                )
                e["out"] = {
                    "error": "tool_execution_failed",
                    "message": f"Tool '{e['name']}' failed during parallel dispatch.",
                }
            e["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            e["cached"] = False
            e["parallel"] = True
