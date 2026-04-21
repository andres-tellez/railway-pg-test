"""
V1.6 Phase C 3C.8 + 3C.9 — post-response validator (observability only).

**Purpose.**

* **3C.8 (§19.9 read-only field check).** The six deterministic
  V1.6 fields are authored by the backend. The coach **must not**
  invent, override, or disagree with any of them. This validator
  scans the assistant's final reply for **direct-label
  contradictions** — places where the response asserts a
  classification word (*"too hard"*, *"missed"*, *"insufficient
  baseline"*, *"high adherence"*, …) that contradicts the value the
  tool payload returned for the same field.

* **3C.9 (§19.1 numeric grounding).** The LLM may only use numeric
  values present in the payload. This validator extracts
  **metric-shaped tokens** from the reply (percentages, HR in bpm,
  pace in M:SS/mi, distance in miles) and confirms each one appears
  *somewhere* in the collected payload text pool (raw values or
  pre-formatted ``display`` strings emitted by 3B.7).

**Design contract.**

* **Observability first, never blocks.** Both checks return
  structured findings attached to ``meta["validator"]``; they do
  not rewrite, redact, or reject the response. Blocking behavior is
  a separate future step (tracked in §19 follow-up work) — V1
  establishes the measurement so false-positive rates can be
  calibrated before anything is enforced.
* **High precision over high recall.** Every detector is tuned to
  fire only on an unambiguous contradiction or ungrounded token.
  Fuzzy natural-language contradictions (e.g. coach "feels too
  optimistic") are intentionally out of scope.
* **Single source of payload truth.** The validator reads whatever
  the tools returned in this turn; it never re-derives a metric
  itself. If a tool never emitted a field, that field is simply not
  checked — absent is not the same as contradicted (see §19
  ``null`` vs absent convention).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

COACH_RESPONSE_VALIDATOR_VERSION = 1

# Read-only fields from §19.9. Keep this list in lockstep with the
# spec — the orchestrator wiring relies on the field names being
# spellable exactly as the backend emits them.
READ_ONLY_FIELDS: Tuple[str, ...] = (
    "deviation_direction",
    "plan_status",
    "baseline_status",
    "phase_kpi_priority",
    "adherence_runs_pct",
    "violated_rest_day",
)

# Valid enum values per §5 / §6 / §7 / §12. Used both for collection
# (to filter noise) and for emitting contradictions that target only
# canonical values (not typos in upstream data).
_DEVIATION_DIRECTION_VALUES: Tuple[str, ...] = ("too_hard", "too_easy", "on_target")
_PLAN_STATUS_VALUES: Tuple[str, ...] = (
    "planned_only",
    "in_progress",
    "executed",
    "missed",
    "unplanned",
)
_BASELINE_STATUS_VALUES: Tuple[str, ...] = ("insufficient", "thin", "strong")

# Adherence-band thresholds from §7 — kept here (not imported from a
# separate module) so the validator has **one** place to edit if the
# bands ever move. Mirrored verbatim in §19.8 / coach_tone_contract.
_ADHERENCE_BAND_LOW_MAX = 0.70  # strict <
_ADHERENCE_BAND_MEDIUM_MAX = 0.90  # inclusive upper bound of medium


# ---------------------------------------------------------------------------
# Collection — walk tool payloads to gather observed read-only values +
# the grounded numeric-token pool used by 3C.9.
# ---------------------------------------------------------------------------


def _walk_values(node: Any) -> Iterable[Tuple[str, Any]]:
    """Yield ``(key, value)`` pairs for every mapping entry reachable.

    Lists / tuples are descended into without producing a key (their
    items are yielded under the enclosing mapping's key via recursion).
    Non-container leaves are ignored at this layer — callers only
    want the field-name → value shape.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k), v
            yield from _walk_values(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_values(item)


def collect_readonly_field_observations(
    tool_outputs: Iterable[Any],
) -> Dict[str, List[Any]]:
    """Return every observed value for each §19.9 read-only field.

    Lists are preserved (e.g. multiple runs in a weekly payload each
    contribute their own ``plan_status``). The validator then applies
    contradiction rules across **all** observed values — a response
    that says *"you missed Tuesday"* is a violation if any run in
    the payload has ``plan_status == "executed"`` on Tuesday, but
    we intentionally do not track per-day provenance at V1 because
    the coach-side directive is "narrate what the backend said, do
    not invert it" regardless of which day it was said about.
    """
    observations: Dict[str, List[Any]] = {name: [] for name in READ_ONLY_FIELDS}
    for out in tool_outputs:
        for key, value in _walk_values(out):
            if key in observations:
                observations[key].append(value)
    return observations


_NUMERIC_LITERAL_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _stringify_value(value: Any) -> List[str]:
    """Return every string form of ``value`` worth matching against.

    For numeric values we emit both the raw ``str(value)`` and a
    zero-decimal / one-decimal / two-decimal variant so that "5",
    "5.0", "5.00" all satisfy grounding when any of them appears in
    the payload. For strings we emit the stripped literal plus each
    embedded numeric run (so ``"5.00 mi"`` contributes the tokens
    ``"5.00 mi"``, ``"5.00"``, and ``"5"``).
    """
    out: List[str] = []
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            return out
        out.append(str(value))
        out.append(f"{as_float:.0f}")
        out.append(f"{as_float:.1f}")
        out.append(f"{as_float:.2f}")
        return out
    if isinstance(value, str):
        s = value.strip()
        if s:
            out.append(s)
            for m in _NUMERIC_LITERAL_RE.findall(s):
                out.append(m)
        return out
    return out


def collect_grounded_token_pool(tool_outputs: Iterable[Any]) -> Set[str]:
    """Return the pool of strings a response number is grounded against.

    Includes raw numeric values, pre-formatted ``display`` block
    strings, and every substring numeric run found inside string
    values. Callers never pay a per-request re-computation cost
    because the pool is rebuilt only once per turn by the
    orchestrator.
    """
    pool: Set[str] = set()

    def _add_all(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                _add_all(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _add_all(item)
        else:
            for s in _stringify_value(node):
                if s:
                    pool.add(s)

    for out in tool_outputs:
        _add_all(out)
    return pool


# ---------------------------------------------------------------------------
# 3C.8 — read-only field contradiction detectors
# ---------------------------------------------------------------------------


def _text_contains_phrase(text_lower: str, *phrases: str) -> Optional[str]:
    """Return the first phrase hit, or ``None``. Case-insensitive."""
    for p in phrases:
        if p in text_lower:
            return p
    return None


def _deviation_direction_contradictions(
    text_lower: str, observed: List[Any]
) -> List[Dict[str, Any]]:
    """§5 ``deviation_direction``: coach must not flip the label.

    ``null`` and absent are tolerated — Steady runs, short runs, and
    runs without HR data omit the value and the coach must not
    fabricate one either way. We only fire when the payload
    *definitively* states a canonical direction and the text asserts
    a *different* one.
    """
    actual = {v for v in observed if v in _DEVIATION_DIRECTION_VALUES}
    if not actual:
        return []
    # Text labels the coach might use (both snake_case and prose).
    label_phrases = {
        "too_hard": ("too hard", "ran it too hard", "way too hard"),
        "too_easy": ("too easy", "ran it too easy", "under-effort"),
        "on_target": ("on target", "on-target", "right on target"),
    }
    violations: List[Dict[str, Any]] = []
    for said_label, phrases in label_phrases.items():
        hit = _text_contains_phrase(text_lower, *phrases)
        if hit and said_label not in actual:
            violations.append(
                {
                    "field": "deviation_direction",
                    "payload_values": sorted(actual),
                    "response_phrase": hit,
                    "response_asserts": said_label,
                    "reason": "coach asserted a deviation_direction label not present in any tool payload",
                }
            )
    return violations


def _plan_status_contradictions(
    text_lower: str, observed: List[Any]
) -> List[Dict[str, Any]]:
    """§6 ``plan_status``: coach must not flip executed/missed/etc."""
    actual = {v for v in observed if v in _PLAN_STATUS_VALUES}
    if not actual:
        return []
    violations: List[Dict[str, Any]] = []
    # Only fire when payload unambiguously says EXECUTED but the text
    # claims the run was missed. The inverse (payload MISSED but text
    # says "you ran") is the second check.
    if actual == {"executed"} and _text_contains_phrase(
        text_lower, "you missed", "you didn't run", "you did not run"
    ):
        violations.append(
            {
                "field": "plan_status",
                "payload_values": ["executed"],
                "response_phrase": "you missed / you didn't run",
                "response_asserts": "missed",
                "reason": "payload reports plan_status=executed but response asserts the run was missed",
            }
        )
    if actual == {"missed"} and _text_contains_phrase(
        text_lower,
        "you ran it",
        "your execution was",
        "you completed the run",
    ):
        violations.append(
            {
                "field": "plan_status",
                "payload_values": ["missed"],
                "response_phrase": "you ran / executed / completed",
                "response_asserts": "executed",
                "reason": "payload reports plan_status=missed but response asserts execution",
            }
        )
    # §19.7: unplanned runs must be acknowledged. Firing rule here is
    # narrow — coach explicitly calling the run "scheduled" when the
    # payload says unplanned.
    if actual == {"unplanned"} and _text_contains_phrase(
        text_lower,
        "was on your plan",
        "was scheduled",
        "this was planned",
    ):
        violations.append(
            {
                "field": "plan_status",
                "payload_values": ["unplanned"],
                "response_phrase": "was scheduled / was on your plan",
                "response_asserts": "planned",
                "reason": "payload reports plan_status=unplanned but response frames the run as scheduled",
            }
        )
    return violations


def _baseline_status_contradictions(
    text_lower: str, observed: List[Any]
) -> List[Dict[str, Any]]:
    """§12 ``baseline_status``: three-value enum."""
    actual = {v for v in observed if v in _BASELINE_STATUS_VALUES}
    if not actual:
        return []
    violations: List[Dict[str, Any]] = []
    if actual == {"insufficient"} and _text_contains_phrase(
        text_lower, "strong baseline", "solid baseline"
    ):
        violations.append(
            {
                "field": "baseline_status",
                "payload_values": ["insufficient"],
                "response_phrase": "strong baseline / solid baseline",
                "response_asserts": "strong",
                "reason": "payload reports baseline_status=insufficient but response asserts a strong baseline",
            }
        )
    if actual == {"strong"} and _text_contains_phrase(
        text_lower, "insufficient baseline", "no baseline yet", "too thin"
    ):
        violations.append(
            {
                "field": "baseline_status",
                "payload_values": ["strong"],
                "response_phrase": "insufficient / too thin",
                "response_asserts": "insufficient",
                "reason": "payload reports baseline_status=strong but response asserts an insufficient baseline",
            }
        )
    return violations


def _violated_rest_day_contradictions(
    text_lower: str, observed: List[Any]
) -> List[Dict[str, Any]]:
    """§6 ``violated_rest_day``: boolean flag with coaching weight."""
    bools = [v for v in observed if isinstance(v, bool)]
    if not bools:
        return []
    violations: List[Dict[str, Any]] = []
    if any(bools) and _text_contains_phrase(
        text_lower, "it was a rest day that you honored", "you took your rest"
    ):
        violations.append(
            {
                "field": "violated_rest_day",
                "payload_values": [True],
                "response_phrase": "you honored / took your rest day",
                "response_asserts": "rest day honored",
                "reason": "payload reports violated_rest_day=true but response claims the rest day was honored",
            }
        )
    if all(not b for b in bools) and _text_contains_phrase(
        text_lower, "you violated your rest day", "you skipped the rest day"
    ):
        violations.append(
            {
                "field": "violated_rest_day",
                "payload_values": [False],
                "response_phrase": "you violated / skipped the rest day",
                "response_asserts": "rest day violated",
                "reason": "payload reports violated_rest_day=false but response claims the rest day was violated",
            }
        )
    return violations


def _adherence_band_contradictions(
    text_lower: str, observed: List[Any]
) -> List[Dict[str, Any]]:
    """§7 adherence bands: low / medium / high.

    Fires on direct band-word contradictions only (the band the coach
    names must match the numeric band the payload reports). Coaches
    may still use nuanced language ("consistency is still coming
    together") without tripping this check.
    """
    numeric = [
        v for v in observed if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not numeric:
        return []
    min_v = min(numeric)
    max_v = max(numeric)
    # If payloads disagree on the band, skip — we don't want to pick
    # an arbitrary "truth" value.
    if _band(min_v) != _band(max_v):
        return []
    band = _band(min_v)
    violations: List[Dict[str, Any]] = []
    if band == "low" and _text_contains_phrase(
        text_lower, "adherence is high", "high adherence"
    ):
        violations.append(
            {
                "field": "adherence_runs_pct",
                "payload_values": [min_v, max_v],
                "response_phrase": "high adherence",
                "response_asserts": "high",
                "reason": "payload reports adherence_runs_pct in low band (<70%) but response asserts high adherence",
            }
        )
    if band == "high" and _text_contains_phrase(
        text_lower, "adherence is low", "low adherence"
    ):
        violations.append(
            {
                "field": "adherence_runs_pct",
                "payload_values": [min_v, max_v],
                "response_phrase": "low adherence",
                "response_asserts": "low",
                "reason": "payload reports adherence_runs_pct in high band (>90%) but response asserts low adherence",
            }
        )
    return violations


def _band(value: float) -> str:
    """Return ``low`` / ``medium`` / ``high`` per §7 adherence bands."""
    if value < _ADHERENCE_BAND_LOW_MAX:
        return "low"
    if value <= _ADHERENCE_BAND_MEDIUM_MAX:
        return "medium"
    return "high"


def check_readonly_field_contradictions(
    response_text: str,
    observations: Dict[str, List[Any]],
) -> List[Dict[str, Any]]:
    """Aggregate all §19.9 read-only contradictions for a response."""
    text_lower = response_text.lower()
    violations: List[Dict[str, Any]] = []
    violations.extend(
        _deviation_direction_contradictions(
            text_lower, observations.get("deviation_direction", [])
        )
    )
    violations.extend(
        _plan_status_contradictions(text_lower, observations.get("plan_status", []))
    )
    violations.extend(
        _baseline_status_contradictions(
            text_lower, observations.get("baseline_status", [])
        )
    )
    violations.extend(
        _violated_rest_day_contradictions(
            text_lower, observations.get("violated_rest_day", [])
        )
    )
    violations.extend(
        _adherence_band_contradictions(
            text_lower, observations.get("adherence_runs_pct", [])
        )
    )
    # phase_kpi_priority is an ordered list — a "contradiction" needs
    # day-of-week / KPI-name resolution that is out of scope for V1
    # detection. We surface the observed list in meta via
    # `validate_coach_response` so operators can still diff.
    return violations


# ---------------------------------------------------------------------------
# 3C.9 — numeric grounding
# ---------------------------------------------------------------------------


# Metric-shaped token patterns. Each group captures the whole metric
# claim ("72 %", "142 bpm", "8:30/mi", "5.00 mi").
_METRIC_TOKEN_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("percent", re.compile(r"\d+(?:\.\d+)?\s*%")),
    ("bpm", re.compile(r"\d+\s*bpm", re.IGNORECASE)),
    ("pace", re.compile(r"\d+:\d{2}(?:\s*/\s*mi)?", re.IGNORECASE)),
    ("miles", re.compile(r"\d+(?:\.\d+)?\s*mi(?:les)?\b", re.IGNORECASE)),
)


def _normalize_token(s: str) -> str:
    """Collapse whitespace so ``"72 %"`` matches ``"72%"``."""
    return re.sub(r"\s+", "", s).lower()


def _token_is_grounded(token: str, pool: Set[str]) -> bool:
    """Return True if ``token`` appears in any pool string.

    Matches along three axes, in order of strictness:

    1. Whitespace-collapsed literal match (``"72 %"`` ↔ ``"72%"``).
    2. Bare numeric substring present in the pool as-is.
    3. Numeric-value equivalence: if the token's numeric part
       (e.g. ``"5"`` from ``"5 miles"``) equals the numeric value of
       any pool string by float comparison (e.g. ``"5.00"``), the
       token is grounded. This is required because the 3B.7 display
       block emits two-decimal miles (``"5.00 mi"``) while coaches
       naturally paraphrase to integers (``"5 miles"``).

    The three-axis match keeps the grounded set conservative without
    being brittle about cosmetic formatting.
    """
    normalized = _normalize_token(token)
    numeric_only = re.sub(r"[^\d.]", "", token)
    normalized_pool = {_normalize_token(p) for p in pool}
    if normalized in normalized_pool:
        return True
    if numeric_only and numeric_only in pool:
        return True
    # Numeric-value fallback. Cast once and compare as floats — avoids
    # the cosmetic "5" ≠ "5.00" string mismatch.
    if numeric_only:
        try:
            token_num = float(numeric_only)
        except ValueError:
            return False
        for p in pool:
            try:
                if float(p) == token_num:
                    return True
            except ValueError:
                continue
    return False


def check_numeric_grounding(response_text: str, pool: Set[str]) -> List[Dict[str, Any]]:
    """Return ungrounded metric-shaped tokens found in the response.

    Each finding carries the raw token (as written by the coach), the
    :attr:`kind` (percent / bpm / pace / miles), and the offset so
    operators can eyeball the response. Calls without any tool output
    (the pool is empty) skip grounding: a response produced from pure
    memory is **already** a §19.1 violation at the glossary layer,
    not a numeric one.
    """
    if not pool:
        return []
    findings: List[Dict[str, Any]] = []
    for kind, pat in _METRIC_TOKEN_PATTERNS:
        for match in pat.finditer(response_text):
            token = match.group(0)
            if _token_is_grounded(token, pool):
                continue
            findings.append(
                {
                    "kind": kind,
                    "token": token,
                    "offset": match.start(),
                    "reason": "metric-shaped token not found in any tool payload value",
                }
            )
    return findings


# ---------------------------------------------------------------------------
# Public entry point — run both checks and produce the meta envelope
# ---------------------------------------------------------------------------


def validate_coach_response(
    response_text: str,
    tool_outputs: Iterable[Any],
) -> Dict[str, Any]:
    """Run both 3C.8 + 3C.9 checks and return a single report.

    The return shape is stable and versioned so downstream dashboards
    (and future enforcement layers) can consume it without guessing:

    .. code-block:: python

        {
            "version": 1,
            "readonly_violations": [ ... ],
            "ungrounded_numbers": [ ... ],
            "observed_readonly": { field: [values...] },
            "total_findings": int,
        }

    Empty text or no tool outputs → empty findings, not an error.
    The validator is defensive about every shape it receives because
    it runs on the hot path of every assistant turn.
    """
    outputs_list = list(tool_outputs)
    observations = collect_readonly_field_observations(outputs_list)
    readonly_violations = (
        check_readonly_field_contradictions(response_text, observations)
        if response_text
        else []
    )
    grounded_pool = collect_grounded_token_pool(outputs_list)
    ungrounded_numbers = (
        check_numeric_grounding(response_text, grounded_pool) if response_text else []
    )
    return {
        "version": COACH_RESPONSE_VALIDATOR_VERSION,
        "readonly_violations": readonly_violations,
        "ungrounded_numbers": ungrounded_numbers,
        "observed_readonly": {
            name: observations.get(name, []) for name in READ_ONLY_FIELDS
        },
        "total_findings": len(readonly_violations) + len(ungrounded_numbers),
    }
