# SmartCoach System Spec — Master Specification V1

> **Version:** 1.2
> **Date:** April 2026
> **Status:** Approved — Complete Master Specification
> **Scope:** Globally consistent, adaptive coaching system — based on all architectural decisions made.
> **Note:** Implementation approach to be decided separately based on current codebase state.

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Control Model](#2-control-model)
3. [Run Model](#3-run-model)
4. [Adaptive HR Model](#4-adaptive-hr-model)
5. [Tolerance System](#5-tolerance-system)
6. [Plan vs Execution Model](#6-plan-vs-execution-model)
7. [KPI Framework](#7-kpi-framework)
8. [KPI Aggregation](#8-kpi-aggregation)
9. [Scoring System](#9-scoring-system)
10. [System Loop](#10-system-loop)
11. [Phase Model](#11-phase-model)
12. [Baseline Assessment](#12-baseline-assessment)
13. [Plan Duration Logic](#13-plan-duration-logic)
14. [Weekly Structure Rules](#14-weekly-structure-rules)
15. [Plan Generation](#15-plan-generation)
16. [Adaptation Model](#16-adaptation-model)
17. [Weekly Construction Engine](#17-weekly-construction-engine)
18. [System Principles](#18-system-principles)
19. [Appendix A — Phase Distribution](#appendix-a--phase-appropriate-run-type-distribution)
20. [Appendix B — Deterministic vs LLM Boundary](#appendix-b--deterministic-vs-llm-boundary)

---

## 1. Core Philosophy

The system is built on a single, non-negotiable separation of concerns:

| Layer | Responsibility |
|---|---|
| **System** | Computes truth — data, KPIs, rules, scoring, classification |
| **LLM (Coach)** | Explains truth — coaching, insights, guidance, motivation |

The LLM never invents metrics, overrides zone classifications, or fabricates plan data. Everything it communicates is grounded in what the system measured. The system never explains itself — that is always the coach's job.

### What This System Does Uniquely Well

- Combines real training data with coaching logic
- Tracks execution vs intention — every run, every week
- Measures real improvement per run type, not aggregate noise
- Balances user-facing simplicity with internal precision
- Enforces safety constraints while personalizing within them

---

## 2. Control Model

### Primary Signal: Heart Rate

HR is the single source of truth for effort classification. All run type validation, tolerance measurement, KPI scoring, and plan adherence tracking is HR-first.

### Secondary Reference: Pace

Pace is an optional reference signal. It is:
- Shown to users as context
- Used by the LLM for conversational coaching
- **Never** used as the primary basis for classifying effort or evaluating a run

### Max HR Strategy

| Source | Priority |
|---|---|
| User-provided input | Optional — accepted if given |
| Age-based estimation | Fallback when no input is provided |
| System default estimate | Applied when age is also unavailable |
| Real run data (ongoing) | Always used to continuously refine the estimate |

> **Key Principle:** Max HR is **dynamic, not fixed.** It is continuously refined from actual run data. The system improves its accuracy over time regardless of initial input quality.

---

## 3. Run Model

### Canonical Run Types

There are **five canonical run types**. These are the only types exposed to users. All plan generation, execution analysis, and evaluation uses exactly these types.

| Type | Purpose | HR Target | Effort Description |
|---|---|---|---|
| **Easy** | Aerobic base building | Zone 1–2 | Fully conversational — full sentences, zero effort |
| **Recovery** | Active fatigue reduction | Zone 1 | Easier than Easy — very slow, very short |
| **Steady** | Moderate aerobic development | High Z2 → Low Z3 | Controlled — can talk, but requires mild effort |
| **Tempo** | Hard aerobic / lactate threshold | Zone 3–4 | Comfortably hard — short phrases only |
| **Long** | Endurance / time on feet | Zone 2 | Easy effort, extended duration (90 min+) |

> **Core Principle:** Run = HR + intent (purpose + duration)

#### Qualifying vs. Disqualifying Conditions

| Type | Qualifies If | Does NOT Qualify If |
|---|---|---|
| Easy | HR stays in Z1–Z2 throughout; conversational throughout | HR drifts into Z3+ consistently; any surge or push |
| Recovery | HR stays in Z1; short duration (20–40 min) | HR reaches Z2 for sustained period |
| Steady | HR mostly in high Z2–low Z3; controlled, sustainable effort | HR spikes into Z4; effort is unsustainable |
| Tempo | HR sustains Z3–Z4 for the main block; consistent throughout | HR bounces wildly; cannot maintain target zone |
| Long | Z2 HR sustained over long duration; gradual late-run drift acceptable | HR climbs significantly above Z2 mid-run |

### Modifiers (Not Run Types)

**Strides** are NOT a run type. They are a quality modifier applied to other runs.

- Definition: 4–6 × 20–30 second accelerations at the end of a run, full recovery between each
- Applied to: Easy runs (most common), occasionally Steady
- Plan display: "Easy Run + strides" — card type remains Easy
- HR: Brief Zone 5 spikes acceptable; duration is too short to count against zone compliance
- Recovery impact: None — insufficient duration to accumulate meaningful fatigue

**Other modifiers** (plan flags, not types):
- `marathon_pace_finish` — last 2–4 miles of a Long run at goal race pace (Peak phase only)
- `progression` — controlled, intentional pace increase across the run duration

---

## 4. Adaptive HR Model

### Zone Visibility

HR zones are visible to users. They are presented as a coaching and education tool, not as a rigid pass/fail system.

### Per-Run Zone Structure

Each run uses three values:

| Field | Description |
|---|---|
| `target_zone` | The ideal HR zone for this run type |
| `acceptable_range` | The bounds within which effort is still valid |
| `tolerance` | Type-specific deviation allowance (see Section 5) |

### Zone Flexibility Philosophy

> Zones are **soft guardrails, not rigid rules.**

The system measures compliance quantitatively; the coach communicates deviations qualitatively. A run that misses its target zone is not automatically failed — it is classified, scored, and explained in context.

---

## 5. Tolerance System

This is the critical middle layer between raw HR data and coaching feedback.

### Measurement Basis

All tolerance is measured in **time in zone**, not distance. A 5-mile easy run and a 5-mile tempo run cover the same distance but carry entirely different zone expectations.

### Quantitative Model (Internal)

| Metric | Description |
|---|---|
| `pct_time_in_target_zone` | % of run time spent in the intended HR zone |
| `pct_time_above_zone` | % of run time spent above the target zone |
| `pct_time_below_zone` | % of run time spent below the target zone |

### Type-Specific Tolerance Profiles

| Type | Tolerance Level | Rationale |
|---|---|---|
| Recovery | Very strict | Any HR elevation defeats the physiological purpose of the run |
| Easy | Tighter | Easy runs are the most frequently misexecuted; drift accumulates hidden fatigue |
| Long | Moderate | Duration naturally produces late-run HR drift; expected and acceptable |
| Steady | Moderate | Effort zone is wider by definition |
| Tempo | Consistency-focused | Must sustain the target zone to achieve the lactate threshold adaptation |

### Direction-Aware Deviation

| Direction | Weight | Rationale |
|---|---|---|
| Above target zone | Higher penalty | Running too hard creates hidden fatigue; defeats the intent of recovery and aerobic runs |
| Below target zone | Lower penalty | Running slightly easy rarely causes harm and may indicate appropriate caution |

> **Principle:** Too hard is always more concerning than too easy. Tolerance = soft guardrails, not strict rules.

---

## 6. Plan vs Execution Model

### Dual Tracking

Every completed run has two classifications:

| Field | Definition |
|---|---|
| `planned_type` | The type assigned by the plan (intent) |
| `executed_type` | The type the run actually was, based on HR data (reality) |

Both are stored permanently. Both matter to scoring and coaching.

### System Behavior

When a run is completed, the system:

1. Classifies the run from actual HR data → assigns `executed_type`
2. Compares `executed_type` to `planned_type`
3. Measures deviation using the tolerance model (Section 5)
4. Calculates KPIs and a score for this run (Sections 7–9)
5. Feeds the result into weekly aggregation (Section 8)

### Coaching Model

> **Coaching = the gap between plan and execution.**

The LLM explains that gap in human terms. It does not re-classify runs, override system measurements, or minimize real deviations.

---

## 7. KPI Framework

### Core KPI (All Run Types)

| KPI | Description |
|---|---|
| **Zone Compliance** | % of run time spent in the target HR zone — primary signal for all types |

### Type-Specific KPIs

| Run Type(s) | Additional KPIs |
|---|---|
| Easy / Long | **HR Drift** (rate of HR rise over time) + **Aerobic Efficiency** |
| Tempo / Steady | **Pace Consistency** (variance in effort across the main block) |
| Recovery | Zone Compliance only — strict adherence is the entire point |

### Supporting Detail (Drill-Down Only)

| Detail | Description |
|---|---|
| Time-in-Zone Breakdown | Z1 / Z2 / Z3 distribution across the full run |

> This detail is shown only in the expanded drill-down view — never on the primary run card.

### Adherence / Completion (Separate Dimension)

| Metric | Description |
|---|---|
| **Completion** | Actual miles completed vs planned miles |

> Completion tracks plan adherence. It is **not** part of the performance score. A perfectly executed 4-mile Easy run on a 6-mile Easy day scores on execution quality, not on volume shortfall.

### Explicitly Excluded KPIs (V1)

Intentionally excluded to maintain focus and avoid surfacing noise:

- HR variability
- Duration as a standalone KPI
- RPE (rate of perceived exertion / subjective effort input)

---

## 8. KPI Aggregation

### Evaluation Levels

| Level | Description |
|---|---|
| **Per run** | Immediate post-run score and KPI values |
| **Weekly aggregation** | Patterns and trends across all runs in the week |
| **Per run type trends** | Is Easy compliance improving? Is Tempo consistency building? |

### Improvement Model

> **Improvement is measured per run type over time**, not as a single composite fitness number.

A runner can be improving their Easy execution while still struggling with Tempo consistency. Both signals are tracked and coached independently.

### Aggregation Outputs

| Output | Consumer |
|---|---|
| Per-run score + KPIs | Run card (user-facing) |
| Weekly zone compliance by type | Weekly coaching insight |
| Per-type trend signals | Plan adaptation trigger (system) |
| Structured coaching context | LLM input for explanation |

---

## 9. Scoring System

### Structure

Each run receives:
- A **single summary score** (🟢 / 🟡 / 🔴) — top-level, always visible
- **Detailed KPI breakdown** — available on drill-down, never shown by default

> **Principle:** Compute complex → Present simple.

### Score Levels

| Score | Meaning |
|---|---|
| 🟢 | On target — execution matched intent |
| 🟡 | Needs adjustment — minor deviation, correctable |
| 🔴 | Off plan — significant deviation from intended type |

### Primary Scoring Driver

> **Zone Compliance** is the primary driver of the score for all run types.

### Secondary Refinement Signals

| Signal | Applied To |
|---|---|
| HR Drift | Easy / Long score refinement |
| Pace Consistency | Tempo / Steady score refinement |
| Aerobic Efficiency | Easy / Long trend refinement |
| Deviation direction | All types — above zone always weighted higher |

### Threshold Model

- **V1:** Fixed thresholds per run type, defined at implementation
- **Future:** Tunable based on athlete history and fitness trajectory

### Run-Type-Specific Scoring Criteria

| Run Type | Primary Criterion |
|---|---|
| Easy | HR stays in Z1–Z2; no drift into Z3+ |
| Recovery | HR strictly in Z1; no elevation above very easy effort |
| Long | HR mostly Z2; drift rate monitored as secondary signal |
| Steady | HR in high Z2–low Z3; controlled and sustainable |
| Tempo | HR sustains Z3–Z4 across the main effort block; consistent |

### Scoring Examples

| Scenario | Score |
|---|---|
| Easy — HR in Z2 throughout | 🟢 |
| Easy — HR drifted into Z3 for 40% of run | 🔴 |
| Easy — HR slightly below Z2 throughout | 🟡 |
| Tempo — HR consistent in Z3–Z4 main block | 🟢 |
| Tempo — HR bounced widely, no sustained zone | 🔴 |
| Long — gradual HR drift in the final 20% of run | 🟡 (expected pattern) |
| Recovery — HR crept into Z2 consistently | 🟡–🔴 |

---

## 10. System Loop

### Core Loop

```
Plan → Execute → Analyze → Coach → Adjust
```

| Step | Owner | Description |
|---|---|---|
| **Plan** | System (deterministic) | Generates full plan upfront; assigns run type, miles, phase |
| **Execute** | Runner | Completes the run |
| **Analyze** | System (deterministic) | Classifies execution, measures KPIs, calculates score |
| **Coach** | LLM | Explains results, identifies patterns, motivates next step |
| **Adjust** | System + LLM | LLM proposes adjustments; system validates and applies within defined rules |

### Adaptive Behavior

- Evaluation happens weekly, after the week closes
- Adjustments target **upcoming weeks only** — past weeks are never retroactively modified
- Adjustments are targeted (volume, intensity, structure) — not a full plan rebuild

---

## 11. Phase Model

### Training Phases

Marathon training is organized into four sequential phases. Each phase has a distinct physiological purpose and defines which run types are appropriate.

| Phase | Purpose | Run Type Focus |
|---|---|---|
| **Base** | Aerobic foundation — build capacity safely | Easy, Long, Recovery |
| **Build** | Progressive load — introduce moderate intensity | Easy, Steady, Long, Tempo (introduced) |
| **Peak** | Peak fitness — maximum volume and quality | Easy, Steady, Long, Tempo (regular) |
| **Taper** | Freshness — reduce volume, maintain sharpness | Easy, Long (reduced), Tempo (one tune-up) |

### Phase Behavior (V1)

- **Time-based:** Phase durations are globally defined (not runner-adaptive in V1)
- **Progressive intensity introduction:** Quality work (Tempo) is not present in Base; introduced in Build; regular in Peak; reduced in Taper
- **Phase transitions** are deterministic — the system moves phases on schedule

> **Principle:** Phases define what matters now. Every run type decision flows from the current phase.

---

## 12. Baseline Assessment

### Data Source

The baseline uses **factual, recent data only** — no self-reported inputs, no subjective assessments.

### Inputs

| Input | Window | Purpose |
|---|---|---|
| Weekly mileage | Last 4 weeks | Measures current capacity |
| Longest recent run | Last 4 weeks | Measures current endurance |

> **Principle:** Baseline = capacity + endurance. These two numbers tell the system where the runner is today.

### What Baseline Determines

- Starting point for the plan (Week 1 mileage and long run distance)
- Whether plan compression is safe (see Section 13)
- Phase week allocations (see Section 11)

---

## 13. Plan Duration Logic

### Default Model

- Standard plan duration: **~18 weeks**
- This is the safe, full-preparation window for marathon training

### Compression Rules

Plans may be compressed below 18 weeks only when the runner's baseline demonstrates readiness. Compression is rule-based and tiered.

| Condition | Requirement |
|---|---|
| Compression eligible | BOTH strong weekly mileage AND strong long run required |
| Either condition alone | Not sufficient for compression |

> Compression requires both signals simultaneously. A runner with high weekly mileage but a short long run is not compression-eligible — they lack the endurance foundation.

### Safety Constraint

> **Minimum plan duration = 10–12 weeks, regardless of baseline.**

No runner, regardless of fitness level, can safely compress below this floor. This is a hard system constraint, not a preference.

> **Principle:** Personalization within safe boundaries. The system adapts to the runner; it never overrides safety.

---

## 14. Weekly Structure Rules

### Training Frequency

| Constraint | Value |
|---|---|
| Minimum runs per week | 3 |
| Maximum runs per week | 6 |
| Rest days | ≥ 1 mandatory per week |

### Required Weekly Components

| Component | Requirement |
|---|---|
| Long Run | 1 per week — mandatory |
| Quality runs (Tempo) | 0–2 per week — phase-dependent |
| Rest days | ≥ 1 per week — enforced |

### Placement Rules

These are system-enforced rules, not suggestions:

| Rule | Description |
|---|---|
| Long Run = anchor | All other runs are placed relative to the Long Run |
| Recovery after Long Run | The day after the Long Run is always Recovery or Rest |
| Quality #1 = early week | First quality run placed early in the week (Tuesday/Wednesday) |
| Quality #2 = mid-week | Second quality run (when present) placed mid-week |
| No back-to-back quality | Two quality runs are never placed on consecutive days |

### Flexibility

| Element | Flexibility |
|---|---|
| Long Run day | Flexible — user preference (guided, not locked) |
| Weekly frequency | User preference within bounds (3–6 runs/week) |

> **Principle:** Same structure, different density. A 3-run week and a 6-run week follow the same structural logic — they differ only in how many Easy runs fill the remaining slots.

---

## 15. Plan Generation

### Model

- **Fully deterministic**
- The complete plan is generated upfront at plan creation
- All weeks are computed at generation time; the system does not generate week-by-week on demand

### UX Behavior

| Behavior | Rule |
|---|---|
| Show current week | Always visible |
| Future weeks | Hidden until the relevant Monday |
| Week reveal | Automatic on Monday — no user action required |

> **Principle:** Plan ahead → Focus now. The full plan exists internally; the runner sees only what is actionable today.

---

## 16. Adaptation Model

### Trigger

Weekly evaluation happens after each week closes. The system reviews KPIs, adherence, and trends.

### Inputs to Adaptation

| Input | Description |
|---|---|
| KPIs | Zone compliance, HR drift, pace consistency per run type |
| Adherence | Completion rate — how many planned runs were executed |
| Trends | Per-type improvement or regression signals over multiple weeks |

### Output: Targeted Adjustments

Adaptation modifies upcoming weeks only. The adjustment scope is targeted — never a full plan rebuild:

| Adjustment type | Description |
|---|---|
| Volume | Increase or decrease weekly mileage |
| Intensity | Add, remove, or scale quality work |
| Structure | Shift run type distribution within the week |

### Adjustment Boundary

- LLM identifies signals and proposes adjustments in natural language
- System validates all proposals against safety constraints and phase rules
- Approved adjustments are applied deterministically

> **Principle:** Plans guide — adaptation personalizes. The plan sets the structure; execution data shapes the future.

---

## 17. Weekly Construction Engine

### Anchor

> **The Long Run is the anchor of every training week.** All other runs are placed relative to it.

### Construction Flow

```
1. Place Long Run (on user's preferred long run day)
2. Place Recovery or Rest the day after Long Run
3. Place Quality Run #1 early in the week (if phase-appropriate)
4. Place Quality Run #2 mid-week (if 2 quality runs in this week)
5. Fill remaining slots with Easy or Recovery
```

### Frequency Scaling

| Runs/Week | Structure |
|---|---|
| 3 | Long + 1 Quality + 1 Easy |
| 4 | Long + 1 Quality + 2 Easy |
| 5 | Long + 1–2 Quality + Easy |
| 6 | Long + 2 Quality + Easy/Recovery |

> **Principle:** The Long Run anchors the week. Quality runs frame the week. Easy and Recovery runs fill it.

### Construction Invariants (Never Violated)

- Long Run is always present
- Recovery or Rest always follows the Long Run
- Quality runs are never placed back-to-back
- Phase rules govern whether 0, 1, or 2 quality runs appear

---

## 18. System Principles

These principles govern every implementation decision. When a design question arises, these resolve it.

| Principle | Meaning |
|---|---|
| **Adaptive > rigid** | The system improves with data; nothing is permanently fixed |
| **Behavior > input** | What the runner does matters more than what they say |
| **Intent + execution both matter** | Planned type and executed type are always both tracked |
| **Safety constraints are hard limits** | Compression minimums, quality spacing, and rest days are non-negotiable |
| **KPIs must be meaningful** | Only include metrics that can be measured reliably and acted upon |
| **Simplicity for user, precision internally** | 5 clean types exposed; full taxonomy and scoring computed internally |
| **Deterministic truth, LLM explanation** | The system never guesses; the LLM never invents |
| **Direction-aware evaluation** | Too hard is always more costly than too easy |
| **Compute complex → Present simple** | Rich internal model; clean single-score output to the user |
| **Phases define what matters now** | Run type distribution is always governed by the current phase |
| **Plans guide — adaptation personalizes** | The upfront plan is the structure; execution data shapes the future |

---

## Appendix A — Phase-Appropriate Run Type Distribution

The plan engine enforces these distributions. They are constraints, not suggestions.

| Phase | Run Type Mix | Quality Work | Volume Direction |
|---|---|---|---|
| **Base** | Easy 60–70%, Long 20–25%, Recovery 10% | None | Building |
| **Build** | Easy 40–50%, Steady 20–25%, Long 20%, Tempo 10% | Tempo introduced | Increasing |
| **Peak** | Easy 35–40%, Steady 20%, Long 20%, Tempo 15–20% | Tempo consistent | Highest |
| **Taper** | Easy 60–70%, Long (reduced) 15%, Tempo (one tune-up) | Reduced | Decreasing |
| **Race Week** | Easy, one short Tempo | Minimal | Very low |

---

## Appendix B — Deterministic vs LLM Boundary

A clear, enforceable boundary. This must not drift during implementation.

### Always Deterministic (System Owns)

- Run type canonical definitions and HR zone targets
- Phase-appropriate run type distribution rules
- Weekly construction flow (Long Run anchor, quality placement, rest rules)
- Minimum recovery spacing between quality workouts
- Weekly mileage targets per phase
- Run classification from HR data (`executed_type` derivation)
- Tolerance thresholds and deviation scoring
- KPI calculation and aggregation
- Completion / adherence tracking (separate from performance score)
- Plan duration safety constraints (minimum 10–12 weeks, compression rules)
- Adaptation trigger rules (what signals qualify as excelling or needing recovery)
- Plan adjustment validation (LLM can only propose within system-defined bounds)
- Fixed scoring thresholds (V1)

### Always LLM (Coach Owns)

- Explaining why a run type was assigned in this phase
- Interpreting KPI values and scores in human, motivational terms
- Responding to user-initiated questions and change requests
- Teaching the user what each run type means and how to execute it
- Explaining the tolerance model in plain language ("your Easy runs have been drifting a bit hard")
- Proposing plan adjustments in natural language (system validates)
- Connecting the runner's week-to-week data to their race goal narrative
- Contextualizing good and bad weeks — effort, life, conditions

### Shared (LLM Proposes, System Validates)

- Mileage adjustments based on performance trends
- Phase timing adjustments (extending Base, shortening Taper)
- Recovery week insertion
- Run type swap requests from user ("can I move Thursday's Tempo to Friday?")

---

*SmartCoach System Spec V1.2 — Master Specification. Complete and approved. Implementation decisions to follow based on current codebase inventory.*
