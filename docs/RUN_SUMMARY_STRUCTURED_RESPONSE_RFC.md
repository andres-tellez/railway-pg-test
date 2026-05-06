# RFC: Structured `run_summary` responses (`CoachTurnSections` on the wire)

| Field | Value |
|-------|--------|
| **Status** | Draft — design only; not implemented |
| **Authors** | Engineering (SmartCoach) |
| **Applies to** | `POST /api/conversations/:id/agent-messages`, persisted assistant payloads |
| **Repos** | **`railway-pg-test`** (primary), **`smartcoach_app`** (client parsing / rendering) |

---

## Where this doc lives (vs other docs)

**Standalone RFC** — This file is the **normative design** for optional structured sections on **`run_summary`** payloads. It intentionally does **not** duplicate:

| Document | Role |
|----------|------|
| [`SMARTCOACH_SYSTEM_SPEC_V1.md`](./SMARTCOACH_SYSTEM_SPEC_V1.md) | Product rules §19, plan vs actual, coach behavior |
| [`API_DOCUMENTATION.md`](./API_DOCUMENTATION.md) | HTTP surface; update when implementation ships |
| [`DOCUMENTATION_GOVERNANCE.md`](./DOCUMENTATION_GOVERNANCE.md) | How docs relate |
| Mobile [`coach-contract.md`](https://github.com/andres-tellez/smartcoach_mobile/blob/main/smartcoach_app/docs/coach-contract.md) (conceptual) | `CoachTurnSections` semantics and render order for **deterministic** copy + LLM alignment goals |

**Relationship:** `coach-contract.md` defines the **semantic shape**. This RFC defines **how that shape may be represented in JSON** for **`run_summary`** so enforcement can move beyond prompt-only alignment.

---

## 1. Problem statement

Today, agent **`run_summary`** replies expose coaching prose as a **single Markdown string** in **`content`**. Product rules and prompts ask the LLM to follow **`CoachTurnSections`** order (interpretation → grounding → nudge → close), but:

- There is **no wire-level schema** for those sections.
- Clients (`AssistantResponsePayload`) only normalize **`type`**, **`content`**, and **`data`**.
- **Prompt tuning alone cannot enforce** structure; models drift, merge sections, or repeat card stats despite instructions.

We need **optional, validated structured fields** while preserving **backward-compatible** delivery for older clients and a single transcript string for logging and history.

---

## 2. Goals

1. **Enforceable structure** for `run_summary` insight text aligned with **`CoachTurnSections`** (`interpretation`, `grounding[]`, optional `nudge`, optional `close`).
2. **Backward compatibility:** existing clients continue to work using **`content`** (and **`data`** for the card).
3. **Single source of truth for prose ordering** when sections are present: **`content`** must be **derivable** from **`sections`** via the same join rule as mobile `renderCoachTurnToText`.
4. **Explicit validation + fallback** when structured output is missing or invalid.
5. **Phased rollout** (backend first, then mobile prefers sections when present).

---

## 3. Non-goals

- **No full Coach chat UI redesign** in Phase 1–2 (same bubble + Markdown under the card unless product explicitly adds section styling later).
- **No change** to **`data`** shape for the **RunSummaryCard** (still canonical `get_run_summary` payload).
- **No generalization** to all assistant payload types in v1 of this RFC (scope is **`type === "run_summary"`** only).
- **No requirement** that every turn produces **`sections`** (optional feature with fallback).

---

## 4. Current state

| Layer | Behavior |
|-------|----------|
| **Backend** | Orchestrator / fastpath return `{"type":"run_summary","content":string,"data":object}`. Assistant row stores **JSON** of that object (`routes.py`). |
| **Mobile** | `normalizeResponseValue` keeps **`type` / `content` / `data`** only. `coach-transcript.tsx` renders **`run_summary`** insight from **`payload.content`** under the card. |
| **Contract docs** | `CoachTurnSections` used for **deterministic** messages; LLM asked to match **conceptually** (`coach-contract.md`). |

---

## 5. Proposed state

### 5.1 Payload shape

```json
{
  "type": "run_summary",
  "content": "<Markdown string — always present when insight text is returned>",
  "data": { },
  "sections": {
    "interpretation": "string",
    "grounding": ["string"],
    "nudge": "string",
    "close": "string"
  }
}
```

| Field | Required | Notes |
|-------|----------|--------|
| **`type`** | Yes | `"run_summary"` |
| **`data`** | Yes | Unchanged card payload |
| **`content`** | Yes | When **`sections`** present: **derived** via same ordering as `renderCoachTurnToText` (interpretation → each grounding → nudge → close), `\n\n` between paragraphs. When **`sections`** absent: model-produced Markdown as today. |
| **`sections`** | **Optional** | If present, must pass validation; **`nudge`** / **`close`** may be omitted or empty after trim. |

### 5.2 Old clients

Clients that ignore unknown keys see **unchanged** behavior: render **`content`** + card from **`data`**.

### 5.3 Ownership model (who fills what)

| Component | Role |
|-----------|------|
| **LLM (structured JSON mode or tool)** | May emit **`sections`** fields (full or partial depending on hybrid strategy). |
| **Deterministic builder** | Recommended for **`grounding[]`** lines sourced from **`coach_prose_signals`** / tool facts where possible (reduces hallucination). |
| **Validator** | Ensures shape, non-empty rules, length caps; on failure **strip `sections`** and keep **`content`** only. |
| **Server join** | When **`sections`** valid, set **`content = join(sections)`** so **`content`** always matches canonical order. |

**Recommended default for `run_summary`:** **hybrid** — deterministic **`grounding`** where signals exist; LLM for **`interpretation`**, optional **`nudge`**, optional **`close`** (smaller schema than asking the model for all four).

---

## 6. Validation

| Check | Action on failure |
|-------|-------------------|
| JSON / schema parse | Omit **`sections`**; use model **`content`** only. |
| **`interpretation`** non-empty when **`sections`** present | Drop **`sections`** or reject turn (policy: prefer drop + log). |
| **`grounding`** is array of strings | Drop **`sections`**. |
| Optional max lengths / denylist (e.g. headline stat patterns) | Configurable; Phase 3 tighten. |

Existing **`validate_coach_response`** (observability) remains; optional **section-specific** metrics in **`meta`**.

---

## 7. Backend touchpoints (implementation reference — not done yet)

| Area | Responsibility |
|------|----------------|
| **`orchestrator.py` / fastpath** | Produce optional **`sections`**; compute **`content`** from **`sections`** when valid. |
| **`routes.py`** | Persistence already stores full dict JSON — **`sections`** ride along automatically. |
| **`thread_derived_context.py`** | Continues to use **`data`** for **`activity_id`**; no change required for v1. |
| **`_llm_plain_text_from_stored_message`** | Ensure history uses plain **`content`** for model-facing replay. |

---

## 8. Mobile touchpoints (implementation reference — not done yet)

| File | Change |
|------|--------|
| **`lib/api/chat.ts`** | Extend **`AssistantResponsePayload`** and **`normalizeResponseValue`** to pass **`sections`**. |
| **`coach-transcript.tsx`** | Phase 2: if **`sections`** present, prefer **`renderCoachTurnToText(sections)`** for display (or trust **`content`** if server guarantees derive). |
| **`coach-turn-sections.ts`** | Single **`renderCoachTurnToText`** — shared semantics with server join. |

---

## 9. Rollout phases

| Phase | Backend | Mobile | Quality gate |
|-------|---------|--------|----------------|
| **1** | Emit **`content`** always; optional **`sections`** behind flag; **`content`** derived when **`sections`** valid | Parse-through optional; UI still uses **`content`** | Fixtures, staging logs |
| **2** | Enable flag in prod | Prefer structured rendering when **`sections`** present | UI snapshots |
| **3** | Stricter validation; optional metrics/alerts | Optional per-section styling if product wants | Contract tests, monitoring |

---

## 10. Risks

| Risk | Mitigation |
|------|------------|
| **LLM JSON parse failures** | Retry / omit **`sections`**; **`content`** fallback. |
| **`content` vs `sections` mismatch** | Server-only derives **`content`** from **`sections`** when sections enabled. |
| **Payload size** | **`sections`** are small vs **`data`**; monitor DB row size. |
| **Prompt conflicts** | Update orchestrator copy that says “plain `content` only” to allow **wire** **`sections`** while user-visible prose remains in **`content`**. |

**Compared to prompt-only tuning:** higher engineering cost; **gain** is measurable, testable compliance with **`CoachTurnSections`**.

---

## 11. Future direction — generalized “CoachTurnSections platform”

1. Reuse the same **`sections`** shape for other structured assistant types (e.g. weekly insight recap) if product wants.
2. Optional **typed discriminated union** on `response` for multiple coach surfaces (version field on payload).
3. **Server–client shared package** for `renderCoachTurnToText` (TS + Python) to eliminate drift — separate initiative.

---

## 12. Open questions

- Exact **JSON schema** for LLM (strict vs flexible optional fields).
- Feature flag name and default (**off** in prod until Phase 2).
- Whether **`sections`** should ever be returned **without** re-derived **`content`** (this RFC recommends **always derive** for consistency).

---

## 13. Decision log

| Date | Outcome |
|------|---------|
| *TBD* | RFC accepted / revised / superseded |

---

## Related links

- Mobile: [`coach-contract.md`](https://github.com/andres-tellez/smartcoach_mobile/blob/main/smartcoach_app/docs/coach-contract.md) — semantic contract.
- Backend: [`src/smartcoach_mobile_coach/README.md`](./smartcoach_mobile_coach/README.md) (if present) — agent module overview.
