"""User-facing Runner Analysis display (Phase 5 — no policy engine)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set

from src.coaching_intelligence.policy.policy_table import (
    competitive_marathon_max_seconds as _COMPETITIVE_MARATHON_MAX_SECONDS,
)
from src.coaching_intelligence.readiness_constants import (
    ACTION_ADJUST_GOAL,
    ACTION_ADD_RUNNING_DAY,
    ACTION_ADJUST_TIMELINE,
    ACTION_BUILD_BASE_FIRST,
    ACTION_CONTINUE_WITH_WARNING,
    ACTION_CREATE_PLAN,
    ACTION_INGEST_MORE_ACTIVITY,
    ACTION_PROVIDE_ALIGNMENT_ANSWERS,
    CATEGORY_TRAINING_AVAILABILITY,
    DECISION_ALLOW,
    GOAL_PROFILE_COMPETITIVE_PERFORMANCE,
    GOAL_PROFILE_COMPLETION,
    GOAL_PROFILE_MODERATE_PERFORMANCE,
    LEVEL_INSUFFICIENT_DATA,
    LEVEL_READY,
    LEVEL_STRETCH,
    PATH_ADD_RUNNING_DAY,
    PATH_ADJUST_GOAL,
    PATH_ADJUST_TIMELINE,
    PATH_BUILD_BASE_FIRST,
    PATH_CREATE_PLAN,
    RULE_MODERATE_PERFORMANCE_PACE_GAP,
    _DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE,
)
from src.coaching_intelligence.time_clock import (
    parse_clock_seconds as _parse_clock_seconds,
)


def _fmt_pace_min_mi(sec_per_mi: float) -> str:
    if sec_per_mi <= 0 or sec_per_mi > 3600:
        return "—"
    m = int(sec_per_mi // 60)
    s = int(round(sec_per_mi % 60))
    if s >= 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}/mi"


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


RUNNER_ANALYSIS_DISPLAY_SCHEMA = "runner_analysis_display.v2"
GOAL_DIRECTION_DISPLAY_SCHEMA = "goal_direction_display.v1"

_GOAL_DIRECTION_PRIMARY_LABELS: Dict[str, str] = {
    ACTION_ADJUST_GOAL: "Update my marathon goal",
    ACTION_CREATE_PLAN: "Create my plan",
    ACTION_ADD_RUNNING_DAY: "Add another training day",
    ACTION_ADJUST_TIMELINE: "Move my goal race farther out",
    ACTION_BUILD_BASE_FIRST: "Build base first",
    ACTION_PROVIDE_ALIGNMENT_ANSWERS: "Answer alignment questions",
    ACTION_INGEST_MORE_ACTIVITY: "Sync more activity / add training history",
    ACTION_CONTINUE_WITH_WARNING: "Continue with current goal (acknowledge risk)",
}


def _pick_goal_direction_action_id(
    allowed: Sequence[str], preferences: Sequence[str]
) -> str:
    s = [str(x).strip() for x in allowed if str(x).strip()]
    for pref in preferences:
        if pref in s:
            return pref
    return s[0] if s else ACTION_ADJUST_GOAL


def _goal_direction_primary_action(
    allowed: Sequence[str], preferences: Sequence[str]
) -> Dict[str, str]:
    action_id = _pick_goal_direction_action_id(allowed, preferences)
    label = _GOAL_DIRECTION_PRIMARY_LABELS.get(action_id) or action_id.replace("_", " ")
    return {"id": action_id, "label": label}


def _build_goal_direction_display(
    plan_generation_readiness: Dict[str, Any],
    *,
    digest: Dict[str, Any],
    goal_profile: str,
    aggressive: bool,
    sub3: bool,
    codes: Set[str],
    n_run_days: int,
    allowed_actions: Sequence[str],
) -> Dict[str, Any]:
    """Qualitative, developmental goal guidance for Runner Analysis (no engine band labels)."""
    _ = (codes, n_run_days)
    decision = str(plan_generation_readiness.get("decision") or "").strip()
    lvl = str(plan_generation_readiness.get("readiness_level") or "").strip()
    when = _race_month_year_phrase(digest)
    allowed = [str(x).strip() for x in allowed_actions if str(x).strip()]
    allowed_set = set(allowed)

    def reassess_bullet() -> str:
        return (
            "When you change your goal here, the next coach reply re-runs this read automatically — "
            "same inputs, fresh snapshot."
        )

    # --- insufficient / gate paths (still developmental, not "validation failed")
    if lvl == LEVEL_INSUFFICIENT_DATA:
        if ACTION_PROVIDE_ALIGNMENT_ANSWERS in allowed_set:
            primary_prefs = [
                ACTION_PROVIDE_ALIGNMENT_ANSWERS,
                ACTION_INGEST_MORE_ACTIVITY,
                ACTION_ADJUST_GOAL,
            ]
        else:
            primary_prefs = [
                ACTION_INGEST_MORE_ACTIVITY,
                ACTION_ADJUST_GOAL,
                ACTION_ADJUST_TIMELINE,
            ]
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "clarify_training_picture",
            "headline": "Sharpen the picture before we commit the plan",
            "framing": (
                "I don’t yet have a solid enough read on your training context to recommend **how** we should "
                "frame this cycle. A few intake answers or a bit more synced history usually clears that up — "
                "then we can name a honest direction for **this** race."
            ),
            "next_steps": [
                "Resolve the open intake questions (or sync more runs) so this read is grounded in real weeks.",
                "Once that lands, we’ll re-shape the goal language around what your schedule and logs support.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(allowed, primary_prefs),
        }

    if decision == DECISION_ALLOW:
        if lvl == LEVEL_STRETCH:
            if goal_profile == GOAL_PROFILE_COMPLETION:
                hid = "patient_completion_build"
                hl = "Patient completion-strong cycle"
                fr = (
                    f"For **{when}**, a **finish-strong** plan is still appropriate — it just deserves a **patient** build: "
                    "durability and consistency ahead of hero weeks. You’re choosing clarity over rushing the ramp."
                )
                nxt = [
                    "Keep the finish line in view, and let weekly rhythm + long runs earn confidence.",
                    "Use the plan to **absorb** volume before any late push.",
                    reassess_bullet(),
                ]
            elif goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE:
                if RULE_MODERATE_PERFORMANCE_PACE_GAP in codes:
                    hid = "moderate_marathon_developmental_pace"
                    hl = "Developmental moderate performance build"
                    fr = _DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE
                    nxt = [
                        "Prioritize **easy volume**, steadier weeks, and **repeatable long runs** before leaning on race pace.",
                        "Expect this block to feel like **earning the clock**, not assuming it — that’s normal for this evidence.",
                        reassess_bullet(),
                    ]
                else:
                    hid = "patient_moderate_build"
                    hl = "Patient moderate-goal build"
                    fr = (
                        "Your current setup can move toward this target, but it sits on the **outer edge** of what I’d "
                        f"stack for **{when}**. The developmental play is steady frequency, breathable volume, and "
                        "repeatable long efforts — not forcing pace before the base is honest."
                    )
                    nxt = [
                        "Lock the plan with eyes open to the ambitious edge you’re choosing, and keep easy days **actually easy**.",
                        "Protect the long run as your primary durability lever this block.",
                        reassess_bullet(),
                    ]
            else:
                hid = "patient_performance_build"
                hl = "Patient performance build"
                fr = (
                    "This target can stay on the radar, but for **this** cycle I’d treat it as an **ambitious edge** — "
                    f"earned week‑by‑week for **{when}**, not assumed on paper. We’ll prioritize frequency, "
                    "absorbable volume, and long-run durability before we talk sharp sharpening."
                )
                nxt = [
                    "Proceed with the plan only if you’re willing to treat the first phase as **foundation**, not proof.",
                    "Expect check-ins as fitness shows up — we adjust load before we chase pace.",
                    reassess_bullet(),
                ]
            return {
                "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
                "direction_id": hid,
                "headline": hl,
                "framing": fr,
                "next_steps": nxt,
                "primary_action": _goal_direction_primary_action(
                    allowed, [ACTION_CREATE_PLAN, ACTION_CONTINUE_WITH_WARNING]
                ),
            }

        if goal_profile == GOAL_PROFILE_COMPLETION:
            return {
                "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
                "direction_id": "strong_completion_focus",
                "headline": "Strong completion-focused cycle",
                "framing": (
                    f"For **{when}**, the coaching recommendation for this block is a **healthy, finish-line plan** — "
                    "fitness that shows up on the day, not a numbers chase. Your goal reads as **completion-first**, "
                    "and that’s a respectable way to run a first or return marathon."
                ),
                "next_steps": [
                    "Use the plan to **build durability** you can repeat, not spikes you survive.",
                    "Keep the emphasis on **steady weeks** and a long run you can recover from.",
                    reassess_bullet(),
                ],
                "primary_action": _goal_direction_primary_action(
                    allowed, [ACTION_CREATE_PLAN]
                ),
            }

        if goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE:
            return {
                "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
                "direction_id": "moderate_performance_build",
                "headline": "Moderate marathon performance build",
                "framing": (
                    f"For **{when}**, a **moderate performance** arc fits: race-day execution built on consistent "
                    "aerobic work, not a reckless sprint to peak. I’d coach this cycle around **repeatable quality** "
                    "and pacing maturity — the things that move a mid-pack target over time."
                ),
                "next_steps": [
                    "Let the plan connect easy volume, a touch of quality, and long-run strength.",
                    "Treat race pace as **something you grow into**, not something you force early.",
                    reassess_bullet(),
                ],
                "primary_action": _goal_direction_primary_action(
                    allowed, [ACTION_CREATE_PLAN]
                ),
            }

        # Competitive / aggressive time goals that clear the ready bar
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "ready_performance_build",
            "headline": "Performance build for this goal",
            "framing": (
                f"Based on what we can see, **this cycle can plan forward** toward **{when}** with a performance lens — "
                "still earned on frequency, volume, and long-run durability. The work ahead is **developmental**: "
                "stack honest weeks, then sharpen only when the base holds."
            ),
            "next_steps": [
                "Use the generated plan as your **structure**, not a wish list — protect consistency.",
                "Let checkpoints confirm you’re absorbing load before any late push.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(
                allowed, [ACTION_CREATE_PLAN]
            ),
        }

    # --- defer / not-yet paths
    if aggressive and sub3:
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "long_term_sub3_development",
            "headline": "Long-term sub-3 development",
            "framing": (
                "For this cycle, I would not build around a sub-3 target yet. The better coaching move is to update "
                "this race goal and use the plan to build the foundation that could make sub-3 realistic later."
            ),
            "next_steps": [
                "Update the marathon goal for this race.",
                "Build toward higher running frequency and sustainable mileage.",
                "Reassess the sub-3 trajectory after another training block.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(
                allowed,
                [
                    ACTION_ADJUST_GOAL,
                    ACTION_ADD_RUNNING_DAY,
                    ACTION_BUILD_BASE_FIRST,
                    ACTION_ADJUST_TIMELINE,
                ],
            ),
        }

    if aggressive and not sub3:
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "competitive_time_goal_development",
            "headline": "Competitive time-goal — earn the cycle first",
            "framing": (
                "For **this** marathon cycle, I wouldn’t anchor the plan to this time target yet — the healthier move "
                "is to **reset the goal language**, then build the frequency, volume, and long-run durability that "
                f"make a strong race at **{when}** believable. Think **earn the standard**, then re-choose the clock."
            ),
            "next_steps": [
                "Update the marathon goal or target time to something this block can honestly serve.",
                "Put **weekly structure** and **repeatable long runs** ahead of pace obsession.",
                "After a foundation phase, re-open the performance conversation with fresh data.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(
                allowed,
                [
                    ACTION_ADJUST_GOAL,
                    ACTION_ADD_RUNNING_DAY,
                    ACTION_BUILD_BASE_FIRST,
                    ACTION_ADJUST_TIMELINE,
                ],
            ),
        }

    if goal_profile == GOAL_PROFILE_MODERATE_PERFORMANCE:
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "moderate_goal_recentering",
            "headline": "Recenter the moderate performance target",
            "framing": (
                "I’d pause before locking a plan to this moderate time goal — not because you lack heart, but because "
                "the **week-to-week picture** still needs to support it for **this race**. The coaching move is to "
                "**soften or shift the target**, then build the cycle that earns a better ask next time."
            ),
            "next_steps": [
                "Adjust the marathon goal or timeline so the block matches your real training bandwidth.",
                "Rebuild easy frequency and long-run rhythm before we chase pace.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(
                allowed,
                [
                    ACTION_ADJUST_GOAL,
                    ACTION_ADJUST_TIMELINE,
                    ACTION_ADD_RUNNING_DAY,
                    ACTION_BUILD_BASE_FIRST,
                ],
            ),
        }

    if goal_profile == GOAL_PROFILE_COMPLETION:
        return {
            "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
            "direction_id": "completion_goal_recentering",
            "headline": "Protect the finish-line goal",
            "framing": (
                f"For **{when}**, the kindest coaching move is to **protect a finish-line plan** — adjust timeline or "
                "expectations so we’re not compressing health into a short ramp. Completion is still a **big** outcome; "
                "it deserves breathing room in the calendar and in weekly volume."
            ),
            "next_steps": [
                "Move the race farther out or simplify what “success” means for this cycle.",
                "Stack **gentle consistency** before any late sharpening.",
                reassess_bullet(),
            ],
            "primary_action": _goal_direction_primary_action(
                allowed,
                [
                    ACTION_ADJUST_TIMELINE,
                    ACTION_ADJUST_GOAL,
                    ACTION_ADD_RUNNING_DAY,
                    ACTION_BUILD_BASE_FIRST,
                ],
            ),
        }

    return {
        "schema_version": GOAL_DIRECTION_DISPLAY_SCHEMA,
        "direction_id": "grounded_next_steps",
        "headline": "Line up the plan with real training bandwidth",
        "framing": (
            "Before we generate a plan, I’d get your **goal language** and **weekly reality** pointing the same "
            f"direction for **{when}**. Small intake changes here are how we keep the block developmental — not "
            "binary pass/fail."
        ),
        "next_steps": [
            "Pick the lever you can honestly change: goal, timeline, or weekly structure.",
            "Come back once that’s updated — this read refreshes on the next coach reply.",
        ],
        "primary_action": _goal_direction_primary_action(
            allowed,
            [
                ACTION_ADJUST_GOAL,
                ACTION_ADD_RUNNING_DAY,
                ACTION_ADJUST_TIMELINE,
                ACTION_BUILD_BASE_FIRST,
                ACTION_PROVIDE_ALIGNMENT_ANSWERS,
                ACTION_INGEST_MORE_ACTIVITY,
            ],
        ),
    }


def _goal_profile_label_for_user(goal_profile: str) -> str:
    return {
        GOAL_PROFILE_COMPLETION: "Finish-the-race focus",
        GOAL_PROFILE_MODERATE_PERFORMANCE: "Moderate performance goal",
        GOAL_PROFILE_COMPETITIVE_PERFORMANCE: "High-demand marathon time goal",
    }.get(goal_profile, "Your stated goal")


def _is_sub3_marathon_digest(digest: Dict[str, Any]) -> bool:
    rd = str(digest.get("race_distance") or "").lower()
    if "marathon" not in rd or "half" in rd:
        return False
    secs = _parse_clock_seconds(digest.get("target_time"))
    return secs is not None and secs <= 3 * 3600


def _aggressive_marathon_goal(digest: Dict[str, Any], goal_profile: str) -> bool:
    if goal_profile == GOAL_PROFILE_COMPETITIVE_PERFORMANCE:
        return True
    secs = _parse_clock_seconds(digest.get("target_time"))
    if secs is None:
        return False
    rd = str(digest.get("race_distance") or "").lower()
    return (
        "marathon" in rd
        and "half" not in rd
        and secs <= _COMPETITIVE_MARATHON_MAX_SECONDS
    )


def _safe_float_fact(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _mileage_interpretation(mpw: float, *, sub3: bool, aggressive: bool) -> str:
    if sub3:
        if mpw < 30:
            return (
                f"At ~{mpw:.0f} mi/week recently, you’re below the kind of chronic weekly load most "
                "sub-3 builds need later in a cycle—not a verdict, just a gap to respect."
            )
        if mpw < 50:
            return (
                f"~{mpw:.0f} mi/week is a workable starting point, but sub-3 training usually trends "
                "toward **meaningfully higher sustainable volume** over many weeks, earned carefully."
            )
        return (
            f"~{mpw:.0f} mi/week gives something to build from, but frequency and durability still have "
            "to catch up to what this time goal asks for."
        )
    if aggressive:
        if mpw < 25:
            return (
                "Weekly volume looks modest for a punchy marathon time goal—you’ll likely need "
                "more consistent miles over time."
            )
        return "Volume is part of the picture; we still need the schedule and endurance side to match the goal."
    if mpw < 15:
        return "Weekly mileage is on the low side for most marathon plans—we’d plan a patient build."
    return "We’ll use this snapshot to shape a sensible progression."


def _long_run_interpretation(miles: float, *, sub3: bool) -> str:
    if miles <= 0:
        return "No reliable long-run signal in the recent window we used."
    if sub3:
        if miles < 10:
            return (
                f"Your longest recent run (~{miles:.0f} mi) is still far from the long-run "
                "durability sub-3 plans typically grow into."
            )
        if miles < 16:
            return (
                f"A ~{miles:.0f} mi long run is a start; this goal usually demands **much more** "
                "marathon-specific endurance over months, not a quick jump."
            )
        return f"A ~{miles:.0f} mi long run is meaningful, but it’s only one piece of the durability picture."
    if miles < 8:
        return "Long runs are still short relative to many marathon builds—expect gradual extension over time."
    return "Long-run exposure will guide how aggressively we can progress."


def _race_month_year_phrase(digest: Dict[str, Any]) -> str:
    """User-facing race timing, e.g. ``October 2026`` — display only."""
    raw = digest.get("race_date")
    if raw is None:
        return "this goal race"
    try:
        if isinstance(raw, str) and len(raw.strip()) >= 10:
            d = datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
            return d.strftime("%B %Y")
    except ValueError:
        pass
    return "this goal race"


def _compact_pace_and_pattern_facts(digest: Dict[str, Any]) -> List[Dict[str, str]]:
    """Single-line fact rows only (no coaching notes)."""
    rows: List[Dict[str, str]] = []
    gp = _safe_float_fact(digest.get("goal_marathon_pace_sec_per_mi"))
    if gp is not None:
        rows.append(
            {
                "title": "Goal marathon pace (from target time)",
                "summary": f"~{_fmt_pace_min_mi(gp)}",
            }
        )
    easy = _safe_float_fact(digest.get("typical_easy_pace_sec_per_mi"))
    if easy is not None:
        rows.append(
            {"title": "Typical training pace", "summary": f"~{_fmt_pace_min_mi(easy)}"}
        )
    sustained = _safe_float_fact(digest.get("best_sustained_endurance_pace_sec_per_mi"))
    if sustained is not None:
        rows.append(
            {
                "title": "Best sustained pace (8+ mi)",
                "summary": f"~{_fmt_pace_min_mi(sustained)}",
            }
        )
    n10 = digest.get("long_runs_ge_10_mi_count")
    ww = digest.get("weeks_with_long_run_10plus")
    if n10 is not None and ww is not None:
        rows.append(
            {
                "title": "Long-run pattern",
                "summary": f"{n10} runs ≥10 mi across {ww} calendar week(s)",
            }
        )
    elif n10 is not None:
        rows.append(
            {"title": "Long-run pattern", "summary": f"{n10} runs ≥10 mi (lookback)"}
        )
    pr = digest.get("pace_reliability")
    if pr and str(pr) in ("none", "low"):
        rows.append(
            {
                "title": "Pace data reliability",
                "summary": f"Limited ({pr}) — fewer usable pace samples in sync",
            }
        )
    return rows


def _main_reason_perf_gap_codes(codes: Set[str]) -> Set[str]:
    """Pace/capability signal codes for ordering main reasons (excludes data-thin alone)."""
    out = {
        c
        for c in codes
        if c.startswith("RULE_PERFORMANCE_") and c != "RULE_PERFORMANCE_PACE_DATA_THIN"
    }
    if RULE_MODERATE_PERFORMANCE_PACE_GAP in codes:
        out.add(RULE_MODERATE_PERFORMANCE_PACE_GAP)
    return out


def _main_reason_longrun_codes(codes: Set[str]) -> Set[str]:
    return codes & {
        "RULE_LONG_RUN_PATTERN_THIN",
        "RULE_LONG_RUN_FREQUENCY_LOW",
        "RULE_LONG_RUN_RECENT_REGRESSION",
        "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN",
    }


def _main_reason_frequency_codes(codes: Set[str]) -> Set[str]:
    return codes & {
        "RULE_SUB3_THREE_DAYS_HIGH_RISK",
        "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE",
    }


def _bullet_performance_alignment(
    codes: Set[str], digest: Dict[str, Any]
) -> Optional[str]:
    gp = _safe_float_fact(digest.get("goal_marathon_pace_sec_per_mi"))
    pace_bit = (
        f"**~{_fmt_pace_min_mi(gp)}**" if gp is not None else "**goal marathon pace**"
    )

    if RULE_MODERATE_PERFORMANCE_PACE_GAP in codes:
        return (
            f"This target is **more realistic** than sub-3 class goals, but your **observed paces** still sit **behind** "
            f"{pace_bit} — expect a **developmental** build, not an on-paper match yet."
        )

    if codes & {
        "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
    }:
        return f"Your observed paces are still **far** from the {pace_bit} pace this goal requires."
    if codes & {
        "RULE_PERFORMANCE_MODERATE_GAP_EASY_VS_GOAL_PACE",
        "RULE_PERFORMANCE_STRETCH_SUSTAINED_VS_GOAL",
    }:
        return f"Your observed paces are still **well behind** the {pace_bit} this goal points toward."
    perf_rest = _main_reason_perf_gap_codes(codes)
    if perf_rest:
        return f"Performance alignment against {pace_bit} still shows a **meaningful gap** in what we can see."
    return None


def _bullet_longrun_durability(codes: Set[str]) -> Optional[str]:
    if not _main_reason_longrun_codes(codes):
        return None
    return "Your long-run **durability** is still developing for this standard."


def _bullet_training_structure(
    codes: Set[str], *, aggressive: bool, sub3: bool, n_run_days: int, softer_also: bool
) -> Optional[str]:
    three = "RULE_SUB3_THREE_DAYS_HIGH_RISK" in codes or (
        aggressive and sub3 and n_run_days > 0 and n_run_days <= 3
    )
    four = "RULE_SUB3_FOUR_DAYS_WEAK_BASELINE" in codes or (
        aggressive and sub3 and n_run_days == 4
    )
    if three:
        if softer_also:
            return "Three running days/week **also** limits the volume and repeatability needed for a serious sub-3 build."
        return "**Three** running days/week is **too low** for this standard."
    if four:
        return "**Four** days/week is usually **still short** for this standard."
    return None


def _bullet_timeline_or_data(codes: Set[str], *, aggressive: bool) -> Optional[str]:
    if "RULE_SUB3_SHORT_TIMELINE" in codes or (
        "RULE_MARATHON_TIME_TARGET_SHORT_TIMELINE" in codes
    ):
        return "**Timeline** to the race is **tight** for earning this goal safely."
    if "RULE_PERFORMANCE_PACE_DATA_THIN" in codes and aggressive:
        return "Pace signal from synced runs is still **thin** for a full read."
    if "RULE_MARATHON_TIME_TARGET_THIN_BASELINE" in codes or (
        "RULE_SUB3_BASELINE_NOT_ESTABLISHED" in codes
    ):
        return "Aerobic **base volume** is still **light** for this target."
    if "RULE_SUB3_VERY_LOW_MILEAGE_AND_SHORT_LONG_RUN" in codes:
        if "RULE_LONG_RUN_PATTERN_THIN" not in codes and (
            "RULE_LONG_RUN_FREQUENCY_LOW" not in codes
        ):
            return "**Volume** and **long run** are both far below this demand."
    if "RULE_EFFORT_CONTROL_DOMINANT_TOO_HARD" in codes:
        return "Recent running skews **too hard** for easy aerobic development."
    return None


def _main_reason_bullets(
    codes: Set[str],
    digest: Dict[str, Any],
    *,
    aggressive: bool,
    sub3: bool,
    n_run_days: int,
) -> List[str]:
    """Max 3 bullets; display order: performance → durability → structure → timeline/data."""
    out: List[str] = []

    def push(line: Optional[str]) -> None:
        if not line or len(out) >= 3:
            return
        key = line.strip().lower()
        if any(key == o.strip().lower() for o in out):
            return
        out.append(line.strip())

    perf_gaps = bool(_main_reason_perf_gap_codes(codes))
    lr_gaps = bool(_main_reason_longrun_codes(codes))
    push(_bullet_performance_alignment(codes, digest))
    push(_bullet_longrun_durability(codes))
    softer_freq = perf_gaps or lr_gaps
    push(
        _bullet_training_structure(
            codes,
            aggressive=aggressive,
            sub3=sub3,
            n_run_days=n_run_days,
            softer_also=softer_freq,
        )
    )
    if len(out) < 3:
        push(_bullet_timeline_or_data(codes, aggressive=aggressive))
    return out[:3]


def _strip_md_for_compare(s: str) -> str:
    return re.sub(r"\*+", "", s).lower()


def _dedupe_bullets_vs_verdict(verdict: str, bullets: Sequence[str]) -> List[str]:
    """Drop bullets that largely repeat the verdict (display-only de-duplication)."""
    v = _strip_md_for_compare(verdict)
    vwords = {w for w in re.findall(r"[a-z0-9]+", v) if len(w) > 2}
    out: List[str] = []
    for b in bullets:
        bb = _strip_md_for_compare(str(b))
        if not bb.strip():
            continue
        tier_keep = (
            bb.startswith("your observed paces are still")
            or ("your long-run durability is still" in bb)
            or ("this target is **more realistic** than sub-3" in bb)
        )
        if tier_keep:
            out.append(str(b).strip())
            if len(out) >= 3:
                break
            continue
        if bb in v:
            continue
        bwords = {w for w in re.findall(r"[a-z0-9]+", bb) if len(w) > 2}
        if bwords and vwords and len(bwords & vwords) / len(bwords) >= 0.55:
            continue
        out.append(str(b).strip())
        if len(out) >= 3:
            break
    return out


def _display_recommended_path(
    rp: Dict[str, Any],
    *,
    aggressive: bool,
    sub3: bool,
    codes: Set[str],
    n_run_days: int,
) -> Dict[str, str]:
    _ = (codes, n_run_days)
    ptype = str(rp.get("type") or "").strip()
    lead = ""
    support = ""

    if ptype == PATH_ADD_RUNNING_DAY and aggressive and sub3:
        lead = (
            "**Not a one-extra-day fix.** Earn **5–6 easy running days/week over time**, "
            "**sustainable mileage**, repeated **quality long runs**, and a smaller **pace gap** — then "
            "**reassess** the time goal."
        )
    elif ptype == PATH_ADD_RUNNING_DAY and aggressive:
        lead = "**Frequency first** — sustained weekly structure, not one cosmetic extra easy day."
    elif ptype == PATH_BUILD_BASE_FIRST and aggressive and sub3:
        lead = (
            "**Base phase first**: easy volume, steadier weeks, and **repeatable long runs** before this "
            "time target is grounded."
        )
    elif ptype == PATH_BUILD_BASE_FIRST and aggressive:
        lead = "**Build base first**: more easy aerobic volume and steadier weeks before this time goal is realistic."
    elif ptype == PATH_ADJUST_GOAL and aggressive and sub3:
        lead = "If structure and timeline won’t move, **the time goal** has to — sub-3 won’t bend to thin weeks."
    elif ptype == PATH_ADJUST_GOAL and aggressive:
        lead = "**Adjust the time goal** (or timeline/frequency) so the plan matches what training can support."
    elif ptype == PATH_ADJUST_TIMELINE and aggressive:
        lead = "**More runway** before the race is a clean lever — extra weeks to earn fitness safely."
    elif ptype == PATH_CREATE_PLAN:
        lead = str(rp.get("message") or "").strip()
    else:
        lead = str(rp.get("message") or "").strip()

    if not lead:
        lead = (
            "Pick what you’re willing to change below, then we can build responsibly."
        )

    out: Dict[str, str] = {"lead": lead}
    if support:
        out["support"] = support
    return out


def _coach_verdict_user(
    r: Dict[str, Any],
    digest: Dict[str, Any],
    *,
    aggressive: bool,
    sub3: bool,
    codes: Set[str],
    n_run_days: int,
) -> str:
    _ = n_run_days
    decision = str(r.get("decision") or "").strip()
    lvl = str(r.get("readiness_level") or "").strip()
    gp_label = _goal_profile_label_for_user(str(r.get("goal_profile") or ""))
    when = _race_month_year_phrase(digest)

    if decision == DECISION_ALLOW and lvl == LEVEL_READY:
        return (
            f"Based on what we can see, you’re **reasonable to plan forward** for this marathon "
            f"({when}). ({gp_label})"
        )

    if decision == DECISION_ALLOW and lvl == LEVEL_STRETCH:
        gp_prof = str(r.get("goal_profile") or "").strip()
        if (
            gp_prof == GOAL_PROFILE_MODERATE_PERFORMANCE
            and RULE_MODERATE_PERFORMANCE_PACE_GAP in codes
        ):
            return _DEVELOPMENTAL_MODERATE_MARATHON_PATH_MESSAGE
        if sub3 and aggressive:
            return (
                f"This is a **serious stretch** for {when}. We can still build a plan — treat it as "
                "**patient development** on frequency, volume, durability, and pace, not a quick bridge."
            )
        return (
            "This goal is a **stretch** from your current baseline — expect a **consistency-first** build "
            f"for {when}."
        )

    if decision != DECISION_ALLOW and aggressive and sub3:
        s1 = f"You are **not** currently in **sub-3 marathon shape** for **{when}**."
        s2 = (
            "The gap is **structural**: aerobic development, weekly frequency, long-run durability, "
            "and observed pace — not a small schedule tweak."
        )
        s3 = (
            "Treat **sub-3 as a longer-term target** for this cycle unless you **change the race goal** "
            "or **move the race**."
        )
        if "RULE_PERFORMANCE_PACE_DATA_THIN" in codes and not (
            codes
            & {
                "RULE_PERFORMANCE_LARGE_GAP_EASY_VS_GOAL_PACE",
                "RULE_PERFORMANCE_NO_SUSTAINED_PACE_NEAR_GOAL",
            }
        ):
            return f"{s1} {s2} Pace data is still **limited** — I’ll weight rhythm and volume until it firms up. {s3}"
        return f"{s1} {s2} {s3}"

    if decision != DECISION_ALLOW and aggressive:
        return (
            f"You’re **not** lined up with this **aggressive marathon time goal** for **{when}** yet. "
            "The levers are **frequency**, **durability**, **base volume**, and **pace evidence** — "
            "**adjust goal, timeline, or weekly structure** before locking a plan."
        )

    rp = (
        r.get("recommended_path") if isinstance(r.get("recommended_path"), dict) else {}
    )
    fallback = str(rp.get("message") or "").strip()
    if fallback:
        return fallback
    return "Let’s adjust a few inputs before we generate your plan."


def _runner_analysis_chips_from_suggestions(suggestions: Any) -> List[Dict[str, Any]]:
    """Normalized chip rows for ``runner_analysis_display.v2`` (id, label, optional proposed_value)."""
    if not isinstance(suggestions, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in suggestions:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        label = str(row.get("label") or "").strip()
        if not cid or not label:
            continue
        chip: Dict[str, Any] = {"id": cid, "label": label}
        pv = row.get("proposed_value")
        if pv is not None and str(pv).strip():
            chip["proposed_value"] = str(pv).strip()
        out.append(chip)
    return out


def build_runner_analysis_display(
    plan_generation_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic, user-facing Runner Analysis only—no engine enums or RULE_* labels."""

    if not isinstance(plan_generation_readiness, dict):
        return {
            "schema_version": RUNNER_ANALYSIS_DISPLAY_SCHEMA,
            "error": "invalid_readiness",
        }

    digest = plan_generation_readiness.get("inputs_digest") or {}
    digest = digest if isinstance(digest, dict) else {}
    goal_profile = str(plan_generation_readiness.get("goal_profile") or "").strip()
    reason_codes = list(plan_generation_readiness.get("reason_codes") or [])
    codes = {str(c).strip() for c in reason_codes if str(c).strip()}
    rp_raw = plan_generation_readiness.get("recommended_path")
    rp = rp_raw if isinstance(rp_raw, dict) else {}

    aggressive = _aggressive_marathon_goal(digest, goal_profile)
    sub3 = _is_sub3_marathon_digest(digest)

    n_days = int(_safe_int(digest.get("training_day_count")) or 0)
    run_days_list: List[str] = []
    for row in plan_generation_readiness.get("category_assessments") or []:
        if not isinstance(row, dict):
            continue
        if row.get("category_id") != CATEGORY_TRAINING_AVAILABILITY:
            continue
        fu = row.get("facts_used") if isinstance(row.get("facts_used"), dict) else {}
        td = fu.get("training_days")
        if isinstance(td, list):
            run_days_list = [str(d).strip() for d in td if str(d).strip()]
        break
    if n_days <= 0 and run_days_list:
        n_days = len(run_days_list)

    mpw = _safe_float_fact(digest.get("avg_miles_per_week_approx"))
    longest = _safe_float_fact(digest.get("longest_run_miles"))
    weeks = digest.get("weeks_to_race")
    activities = digest.get("activities_found")
    lookback = digest.get("lookback_weeks")
    active = digest.get("active_weeks")

    goal_line_parts: List[str] = []
    rd = digest.get("race_distance")
    if rd:
        goal_line_parts.append(str(rd))
    pg = digest.get("primary_goal")
    if pg:
        goal_line_parts.append(str(pg))
    tt = digest.get("target_time")
    if tt:
        goal_line_parts.append(f"target {tt}")
    goal_summary = " — ".join(goal_line_parts) if goal_line_parts else ""

    facts: List[Dict[str, str]] = []
    if goal_summary:
        facts.append({"title": "Goal", "summary": goal_summary})

    sched_summary = (
        f"{n_days} running days per week" if n_days else "Training days not set"
    )
    if run_days_list:
        sched_summary += f" ({', '.join(run_days_list)})"
    facts.append({"title": "Training rhythm", "summary": sched_summary})

    if mpw is not None:
        facts.append(
            {
                "title": "Recent weekly volume",
                "summary": f"~{mpw:.1f} mi/week (recent snapshot)",
            }
        )
    if longest is not None and longest > 0:
        facts.append(
            {
                "title": "Longest recent run",
                "summary": f"~{longest:.1f} mi",
            }
        )
    if aggressive:
        facts.extend(_compact_pace_and_pattern_facts(digest))
    if weeks is not None and str(weeks).strip():
        facts.append(
            {
                "title": "Timeline",
                "summary": f"{weeks} week(s) to race",
            }
        )
    if activities is not None and str(activities).strip():
        cov = f"{activities} logged runs in the lookback we used"
        if active is not None and lookback is not None:
            cov += f" · {active} active week(s) in ~{lookback} week window"
        facts.append(
            {
                "title": "Recent logs",
                "summary": cov,
            }
        )

    facts = facts[:12]

    coach_read = _coach_verdict_user(
        plan_generation_readiness,
        digest,
        aggressive=aggressive,
        sub3=sub3,
        codes=codes,
        n_run_days=n_days,
    )
    raw_bullets = _main_reason_bullets(
        codes,
        digest,
        aggressive=aggressive,
        sub3=sub3,
        n_run_days=n_days,
    )
    why = _dedupe_bullets_vs_verdict(coach_read, raw_bullets)
    path_ui = _display_recommended_path(
        rp,
        aggressive=aggressive,
        sub3=sub3,
        codes=codes,
        n_run_days=n_days,
    )
    actions = [
        str(x)
        for x in (plan_generation_readiness.get("allowed_user_actions") or [])
        if str(x).strip()
    ]

    goal_direction = _build_goal_direction_display(
        plan_generation_readiness,
        digest=digest,
        goal_profile=goal_profile,
        aggressive=aggressive,
        sub3=sub3,
        codes=codes,
        n_run_days=n_days,
        allowed_actions=actions,
    )

    sugg_raw = plan_generation_readiness.get("suggestions")
    chips = _runner_analysis_chips_from_suggestions(sugg_raw)

    out: Dict[str, Any] = {
        "schema_version": RUNNER_ANALYSIS_DISPLAY_SCHEMA,
        "verdict": {"narrative": coach_read},
        "chips": chips,
        "coach_read": coach_read,
        "why_concerned": why,
        "facts": facts,
        "recommended_path": path_ui,
        "recommended_actions": actions,
        "goal_direction": goal_direction,
    }
    deficits_raw = plan_generation_readiness.get("deficits")
    if isinstance(deficits_raw, dict):
        out["deficits"] = deficits_raw
    if isinstance(sugg_raw, list):
        out["suggestions"] = sugg_raw

    pv = plan_generation_readiness.get("policy_version")
    if pv is not None and str(pv).strip():
        out["policy_version"] = str(pv)
    tid = plan_generation_readiness.get("trace_id")
    if tid is not None and str(tid).strip():
        out["trace_id"] = str(tid)

    return out
