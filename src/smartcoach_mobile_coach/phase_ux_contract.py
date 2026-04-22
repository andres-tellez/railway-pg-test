"""
Versioned Phase UX prompt contract for the system prompt (V1.6 Phase D,
§19.4 companion, UX spec locked 2026-04-21).

**Purpose (3D.8).** Phase D landed three new deterministic surfaces:

* ``save_phase_goal`` (3D.2) — behavior/outcome focus, one active row
  per ``(user, plan, phase)``.
* Weekly phase-progress classifier (3D.6) — ``on_track`` / ``close`` /
  ``off_track`` / ``None``.
* Extended ``get_phase_analysis`` payload (3D.3 / 3D.7) —
  ``goal`` + ``weekly_progress[]`` + ``phase_progress_summary``.

3D.8 wires the matching **coach-side** prompt contract so the LLM
structures every phase/plan/progress-related turn in the locked UX
order — **Purpose → Focus → Progress → Action** — and renders the
deterministic progress labels in natural language rather than echoing
enum values.

**Scope gate (user-locked 2026-04-21).** The Phase UX template applies
**only** when the current turn centers on the plan, a phase, or
progress against the plan. Unrelated turns (single-run recap, KPI
definition question, preference update, general chat) MUST stay
conversational — the coach does NOT impose the four-step structure on
a user who just asked *"what's Z2?"*. This is the *"goal proposal
timing"* rule from the locked decisions: trigger only on the first
plan/phase/progress-related turn, do not interrupt unrelated turns.

**Plain-language rule for progress labels.** The weekly progress enum
is a read-only deterministic field (§X.5) — the coach MUST NOT echo it
verbatim. *"You're on_track this week"* is wrong; *"you're landing
the priority work this week"* is right. The enum narrates the
direction of the sentence, never its vocabulary.

**Goal shape.** Goals are **behavior or outcome sentences**, never KPI
thresholds. *"Stay mostly in Zone 2 on long runs so you finish strong"*
is a goal. *"Hit 85 % Z2 compliance"* is a KPI target dressed up as a
goal and is forbidden — 3D.2 validates this at the writer level, 3D.8
reinforces it at the prompt level so the coach never proposes one.

**Single source of truth.** This block mirrors the Phase D locked UX
spec in ``docs/PHASE_3_IMPLEMENTATION_CHECKLIST.md`` §Phase D and the
weekly-progress rule anchored in
``docs/SMARTCOACH_SYSTEM_SPEC_V1.md`` §19.4. When either spec changes,
bump :data:`PHASE_UX_CONTRACT_VERSION` and update the block; the
contract tests assert the version tag and every key phrase so spec ↔
prompt drift fails CI.

The block is emitted once per turn as its own system-prompt section
after :mod:`plan_guidance_contract`. Plan-creation mode skips it —
there is no phase goal or weekly-progress narrative to calibrate
during plan intake.
"""

from __future__ import annotations

PHASE_UX_CONTRACT_VERSION = 1

# Spec-anchored. Every anchor phrase is locked by a contract test so
# the Phase UX template cannot silently drift.
PHASE_UX_CONTRACT_BLOCK = (
    "## Phase UX contract (V1.6 Phase D — Purpose → Focus → Progress → Action)\n"
    f"<!-- phase_ux_contract_version: {PHASE_UX_CONTRACT_VERSION} -->\n"
    "\n"
    "### Scope gate (when to apply this template)\n"
    "Apply the four-step structure **only** when the current turn "
    "centers on the **plan**, a **phase**, or **progress against the "
    "plan** — e.g. *'how is my Base phase going?'*, *'what should I "
    "focus on this block?'*, *'am I on track?'*, or the first turn of "
    "a new phase. Unrelated turns (single-run recap, KPI-definition "
    "question, preference update, general chat) MUST stay "
    "conversational; do NOT impose the Purpose / Focus / Progress / "
    "Action structure on a user who just asked *'what's Z2?'* or "
    "*'how did yesterday's run look?'*.\n"
    "\n"
    "### The four steps (in order)\n"
    "1. **Purpose** — briefly remind the user *why* the current phase "
    "exists (read from `phase_kpi_priority` in the plan payloads + the "
    "phase table in §19.4). One sentence. Skip if the user has heard "
    "it this week and the turn is mid-phase progress.\n"
    "2. **Focus** — the athlete's **active phase goal** read from "
    "`get_phase_analysis.goal.goal_text`. If `goal` is `null`, "
    "propose ONE behavior-or-outcome sentence and save it via the "
    "`save_phase_goal` tool (soft semantics — no hard consent gate). "
    "Goals are **behavior or outcome sentences**, never KPI thresholds. "
    "GOOD: *'Stay mostly in Zone 2 on long runs so you finish strong.'* "
    "BAD (forbidden): *'Hit 85 % Z2 compliance.'* / *'Achieve 300 TSS "
    "per week.'* The `save_phase_goal` tool rejects KPI-threshold text; "
    "do not try to smuggle it through.\n"
    "3. **Progress** — narrate the week(s) in **natural language** "
    "using `weekly_progress[]` and `phase_progress_summary`. The "
    "status enum (`on_track` / `close` / `off_track` / `null`) is a "
    "read-only deterministic label (§X.5); the coach MUST NOT echo it "
    "verbatim. Translate the label into a human sentence that "
    "references the priority run type and adherence band. GOOD: "
    "*'Your Tempo execution has been landing and you hit 4 of 5 runs "
    "— the focus is holding.'* BAD: *'Your status is on_track.'* / "
    "*'phase_progress_summary.dominant_status = close.'* If "
    "`phase_progress_summary.dominant_status` is `null` (no evaluable "
    "weeks yet), say so plainly and pivot to Purpose + Focus.\n"
    "4. **Action** — close with **one next action OR one guiding "
    "question** that reinforces the Focus (§19.6). Never both. Never "
    "an analysis-only response.\n"
    "\n"
    "### Authoritative ordering of deterministic reads\n"
    "- `get_phase_analysis.goal` is the ONLY source for the active "
    "focus. Do not infer a goal from `phase_kpi_priority` alone.\n"
    "- `phase_progress_summary.dominant_status` is the ONLY source for "
    "the phase-level verdict. Do not re-aggregate `weekly_progress[]` "
    "yourself.\n"
    "- `weekly_progress[].status` is the ONLY source for the per-week "
    "verdict. Do not invert it based on a single KPI.\n"
    "The coach MAY surface a tension (*'the week landed close, but "
    "your long run felt hard — want to talk about it?'*) but MUST NOT "
    "flip the label.\n"
    "\n"
    "### Retrospective + new-goal merge rule (phase transition)\n"
    "On the first turn of a new phase (prior phase has `phase_weeks."
    "phase_temporality = past` and the current phase has no active "
    "`goal`), merge **one** coach response: a short retrospective of "
    "the completed phase using its `phase_progress_summary`, followed "
    "by ONE proposed Focus for the new phase. Save the new Focus via "
    "`save_phase_goal` (unconfirmed) in the same turn. Do NOT split "
    "this into two separate turns.\n"
)


def phase_ux_contract_section() -> str:
    """Return the Phase UX contract block for the system prompt.

    Safe to include unconditionally on non-plan-creation turns — the
    block is self-gating via its *"Scope gate"* clause, so turns that
    are not about the plan / phase / progress inherit the
    conversational default without the orchestrator having to classify
    the intent itself. Plan-creation mode skips the block (there is no
    phase goal or weekly-progress narrative during plan intake).
    """
    return PHASE_UX_CONTRACT_BLOCK
