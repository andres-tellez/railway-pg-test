# Design note: structured `run_summary` prose (“How was my run?” only)

| | |
|---|---|
| **Status** | Draft — design only; not implemented |
| **Scope** | **`run_summary`** payloads for **opening run recap** (“How was my run?” / same phrase family). No other assistant shapes, no generalized coach platform. |

**Out of scope:** Weekly summaries, plan chat, other tools, UI redesign, rewriting non–run-summary responses.

---

## 1. Current `run_summary` path

### Fastpath (`run_recap_*`)

- **Trigger:** First user turn in thread + phrase match + `decide_run_recap_fastpath` (see `run_recap_policy.py`).
- **Flow:** Prefetch `search_runs` / `find_runs_by_date` → `tool_get_run_summary` → single `chat_completion` **without tools** (`run_recap_fastpath.py`, orchestrator).
- **HTTP payload:** `{ "type": "run_summary", "content": "<markdown>", "data": <full get_run_summary JSON> }`.
- **Card:** From **`data`** (facts + KPIs for `RunSummaryCard`).
- **Prose:** Single **`content`** string under the card.

### Full agent loop

- **Trigger:** Same user question on **later turns**, blocked phrases, fastpath empty/failure, or env off → multi-step tool loop (`get_run_summary`, etc.).
- **Payload shape:** Same **`type` / `content` / `data`** when a valid tool summary exists (`orchestrator.py`).

### Summary

| Piece | Source |
|-------|--------|
| **Card** | Structured **`data`** from `get_run_summary` |
| **Prose** | Free-form **`content`** only |

---

## 2. Current problem

- **`data`** is structured and renders consistently as **RunSummaryCard**.
- **`content`** is **one Markdown blob**; alignment with **`CoachTurnSections`** (`interpretation` → `grounding[]` → optional `nudge` → optional `close`) is **prompt-only**.
- Prompt tuning + slim appendix improvements **reduce** generic prose but **cannot enforce** section boundaries or stop drift.

**Goal for this note:** optional **`sections`** on **`run_summary`** so opening recap can be **machine-validated** against `CoachTurnSections` without changing **`data`** or breaking older clients.

---

## 3. Proposed API shape (narrow)

Unchanged fields stay authoritative for compatibility:

```json
{
  "type": "run_summary",
  "content": "<markdown string — required when insight text is returned>",
  "data": { }
}
```

**Optional add-on:**

```json
{
  "type": "run_summary",
  "content": "<derived or model prose>",
  "data": { },
  "sections": {
    "interpretation": "string",
    "grounding": ["string"],
    "nudge": "string",
    "close": "string"
  }
}
```

| Field | Rule |
|-------|------|
| **`sections`** | Optional. Omit = today’s behavior. |
| **`content`** | Always present for clients that ignore **`sections`**. When **`sections`** are emitted and valid, **`content`** should be **`renderCoachTurnToText(sections)`** (same order as mobile `coach-turn-sections.ts`) so transcripts stay consistent. |
| **`data`** | Unchanged — full card payload. |

Older apps: ignore **`sections`**, render **`content`** + card from **`data`**.

---

## 4. Backend files likely touched (when implemented)

| File | Why |
|------|-----|
| `src/smartcoach_mobile_coach/orchestrator.py` | Build / attach **`sections`**; derive **`content`**; fallback on validation failure. |
| `src/smartcoach_mobile_coach/run_recap_fastpath.py` | Same for fastpath return dict. |
| `src/smartcoach_mobile_coach/routes.py` | No schema change to persistence — assistant row already stores JSON of the full dict (`json.dumps(gpt_response)`). |
| **New small helper** (optional) | `validate_run_summary_sections`, JSON schema parse; deterministic **`grounding`** lines from existing `coach_prose_signals` / tool payload (hybrid). |

---

## 5. Mobile files likely touched (when implemented)

| File | Why |
|------|-----|
| `smartcoach_app/lib/api/chat.ts` | Extend **`AssistantResponsePayload`**; **`normalizeResponseValue`** must preserve **`sections`**. |
| `smartcoach_app/features/chat/components/coach-transcript.tsx` | **`run_summary`**: if **`sections`** present, render from **`renderCoachTurnToText(sections)`** (or equivalent); else **`content`**. |
| `smartcoach_app/features/chat/coach-turn-sections.ts` | Reuse **`renderCoachTurnToText`** — single ordering rule. |

---

## 6. Rollout phases

| Phase | Work |
|-------|------|
| **1** | Backend: emit **`sections`** + **`content`** (derived when sections valid) behind a flag; optional structured LLM or hybrid builder **only** for opening recap / **`run_summary`**. |
| **2** | Mobile: parse **`sections`**; prefer rendered sections when present; else **`content`**. |
| **3** | Tighten validation, tests, metrics on failures; tune hybrid ownership (LLM vs deterministic grounding). |

---

## 7. Risks and fallback behavior

| Risk | Mitigation |
|------|------------|
| LLM JSON / schema failures | Omit **`sections`**; ship **`content`** only (current behavior). |
| **`content`** vs **`sections`** mismatch | Server derives **`content`** from validated **`sections`** when sections are on. |
| Scope creep | Implement **only** `run_summary` + opening recap first; defer generalization until this path is stable. |

---

## After this ships

Revisit whether to reuse **`sections`** elsewhere — **not** part of this note.
