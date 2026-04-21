"""
Versioned metric glossary for the coach system prompt (V1.6 §§3–9).

**Purpose (3B.14–3B.16).** Most "what is Z2 / what is HR Drift / what is
Zone Compliance" questions can be answered from prompt memory — no tool
call required. Injecting a compact, spec-anchored glossary keeps the
coach's definitions consistent with
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` and prevents silent drift between
product spec and LLM-facing prompt.

**Single source of truth.** Definitions in this module mirror
``SMARTCOACH_SYSTEM_SPEC_V1.md`` §§3–9. When the spec changes, bump
:data:`GLOSSARY_VERSION` and update the block here; downstream prompt
tests assert the version tag.

**Scope.** Zone labels (Z1–Z5), core and type-specific KPIs
(Zone Compliance, HR Drift, Aerobic Efficiency, Pace Consistency),
``deviation_direction`` enum values, and weekly adherence bands. No
thresholds or numbers that could drift from the spec — only the
definitions themselves.

The block is emitted once per turn as its own system-prompt section so
experiments (``SMARTCOACH_EXPERIMENT_MINIMAL_BASE`` etc.) can keep it
regardless of which base is active.
"""

from __future__ import annotations

GLOSSARY_VERSION = 1

# Spec-anchored. Each bullet is short enough to fit in the prompt
# budget yet explicit enough that the model does not need to guess or
# call a tool to answer a bare "what is X?" question. Wording mirrors
# ``SMARTCOACH_SYSTEM_SPEC_V1.md`` §§3–9 so the prompt is a single
# source of truth with the spec — tests lock the key phrases.
METRIC_GLOSSARY_BLOCK = (
    "## Metric glossary (V1.6 §§3–9)\n"
    f"<!-- glossary_version: {GLOSSARY_VERSION} -->\n"
    'Answer bare concept questions ("what is Z2?", "what is HR drift?") '
    "**from prompt memory, without a tool call**. For the runner's own "
    "numbers, still call the relevant tool — these definitions never "
    "replace tool data.\n"
    "\n"
    "**HR zones (§3–§4, soft guardrails).**\n"
    "- **Z1** — Recovery: very easy, short; easier than Easy.\n"
    "- **Z2** — Aerobic base / Easy: conversational, full sentences; target "
    "for Easy and Long runs.\n"
    "- **Z3** — Tempo: comfortably hard, short phrases only.\n"
    "- **Z4** — Lactate threshold: hard aerobic; target for the Tempo main block.\n"
    "- **Z5** — Above threshold: only brief spikes acceptable.\n"
    "\n"
    "**KPIs (§7, §9).**\n"
    "- **Zone Compliance** — % of run time in the target HR zone; "
    "**primary scoring driver** for all types.\n"
    "- **HR Drift** — rate of HR rise over time; refinement signal for Easy / Long.\n"
    "- **Aerobic Efficiency** — pace-to-HR trend; trend refinement for Easy / Long.\n"
    "- **Pace Consistency** — variance across the **main block**; refinement "
    "signal for Tempo / Steady.\n"
    "- **Recovery runs** — Zone Compliance only; strict Z1 adherence is the point.\n"
    "\n"
    "**`deviation_direction` (§5, deterministic).** Computed by the system "
    "from time-above / time-below target zone. The LLM **must not** compute, "
    "override, or contradict it.\n"
    "- `too_hard` — time above target exceeded the threshold.\n"
    "- `too_easy` — time below target exceeded the threshold.\n"
    "- `on_target` — neither threshold exceeded.\n"
    "- `null` — omitted when HR stream missing, `duration_seconds < 600`, "
    "or `planned_type = Steady` (deferred to V1.7).\n"
    "\n"
    "**Adherence bands (§7, weekly).** `adherence_runs_pct = "
    "completed_runs / planned_runs`; a run counts only when "
    "`completion_miles_pct ≥ 0.50`. Drives **adaptation**, not per-run scoring.\n"
    "- **Low** `< 70 %` — reduce load; prioritize consistency.\n"
    "- **Medium** `70 %–90 %` — maintain load.\n"
    "- **High** `> 90 %` — safe to progress within §16 caps.\n"
)


def metric_glossary_section() -> str:
    """Return the versioned metric glossary block for the system prompt."""
    return METRIC_GLOSSARY_BLOCK
