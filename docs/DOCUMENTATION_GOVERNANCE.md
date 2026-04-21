# Documentation governance

**Status:** Active policy
**Normative product spec:** [`SMARTCOACH_SYSTEM_SPEC_V1.md`](./SMARTCOACH_SYSTEM_SPEC_V1.md)

This file does **not** define product rules. It tells humans and agents how to use the small set of markdown kept under `docs/` so we do not recreate parallel “bibles.”

---

## 1. Single source of truth

| Tier | Role | Path |
|------|------|------|
| **A — Product** | Run types, HR, tolerance, KPI/scoring, plan vs execution, adaptation intent, deterministic vs LLM | `docs/SMARTCOACH_SYSTEM_SPEC_V1.md` |
| **B — Implementation proof** | Checklists tracing to Tier A (pass / partial / gap), not new product law | `docs/PHASE_1_IMPLEMENTATION_CHECKLIST.md`, `docs/PHASE_2_IMPLEMENTATION_CHECKLIST.md` |
| **C — API / integration** | HTTP routes, payloads, auth patterns as implemented | `docs/API_DOCUMENTATION.md` |

**Rule:** If code or an old ticket disagrees with Tier A, **Tier A wins** for intended product behavior unless Tier B explicitly records an intentional deferral.

---

## 2. Legacy material

Long-form guides (Strava submission, coach architecture trees, v3 training-plan hub, ops runbooks, and similar) were **removed from `docs/`** as obsolete relative to the current app. They remain in **git history** if you need to recover wording or checklists:

```bash
git log --diff-filter=D --summary -- docs/
```

Prefer **new** docs anchored in Tier A–C rather than resurrecting deleted files wholesale.

---

## 3. Where to document new work

| Change type | Where it belongs |
|-------------|------------------|
| New or changed product rule | `SMARTCOACH_SYSTEM_SPEC_V1.md` (and bump its version note if you maintain one) |
| Shipped vs not shipped for a phase | `PHASE_*_IMPLEMENTATION_CHECKLIST.md` |
| Endpoint / request / auth details | `API_DOCUMENTATION.md` |
| Module-only internals | `README.md` next to the code, with a one-line pointer to Tier A for anything that sounds like a product rule |

---

*Last updated: 2026-04-22 — `docs/` reduced to Tier A–C files plus this governance note.*
