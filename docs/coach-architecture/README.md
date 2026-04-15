# Coach architecture documentation (v2 / experimental track)

**This directory is not the specification for the production mobile Coach tab chat agent.**

The **shipped** Coach tab backend lives under `src/smartcoach_mobile_coach/`. Its canonical architecture and HTTP contract are documented here:

- **[`docs/smartcoach_mobile_coach/README.md`](../smartcoach_mobile_coach/README.md)** — full breakdown (tool loop vs fastpaths, modules, env, PR maintenance rule).
- **[`docs/SMARTCOACH_MOBILE_COACH.md`](../SMARTCOACH_MOBILE_COACH.md)** — short ops entry (route, eval, deploy notes).

---

## What `docs/coach-architecture/` is for

- **Phase-0 / roadmap / reviews** for a modular **`coach/`** package (`coach/builders`, `coach/orchestrator.py`, etc.) and **`tests/coach/`**.
- Process and standards (observability, rollback, shadow mode, cost) that may **reuse** if you revive or merge that program into production.

If you only care about **what runs in production for the mobile app Coach tab**, start with **`docs/smartcoach_mobile_coach/README.md`** and ignore this tree until you actively work on the v2 program.
