# SmartCoach mobile Coach (agent) — backend

**Audience:** Mobile app **Coach** tab only (`smartcoach_app`). Web and legacy `POST …/messages` are unchanged.

**Canonical architecture (modules, fastpaths, PR rules):** [`docs/smartcoach_mobile_coach/README.md`](smartcoach_mobile_coach/README.md)
**Not** the experimental `coach/` v2 doc tree: [`docs/coach-architecture/README.md`](coach-architecture/README.md)

---

## Entry point

- **`POST /api/conversations/{conversation_id}/agent-messages`**
- Body (JSON):
  - **`message`** (string, required): user text.
  - **`client_local_date`** or **`clientLocalDate`** (`YYYY-MM-DD`, strongly recommended): device local calendar day for “today” / anchor tools.
  - **`client_timezone`** or **`clientTimezone`** (optional): IANA zone name for the system prompt only.
  - **`last_activity_id`** or **`lastActivityId`** (optional, positive int): hint for **split-detail fastpath** after a structured `run_summary` turn; server may also infer `activity_id` from stored assistant `run_summary` JSON.

## Response

- **`response`**: assistant payload — either a **plain string** or a **structured object** `{ "type": "run_summary", "content": "…", "data": { … } }` (same shape as stored in `ConversationMessage` when structured).
- **`token_usage`**, **`message_id`**, **`response_time`**, etc. — see `src/smartcoach_mobile_coach/routes.py`.

## Code layout (accurate names)

| Path | Role |
|------|------|
| `src/smartcoach_mobile_coach/routes.py` | Flask blueprint, auth, HTTP rate limit, persistence, history + `last_activity_id` hint |
| `src/smartcoach_mobile_coach/orchestrator.py` | Tool loop, fastpaths, system prompt assembly |
| `src/smartcoach_mobile_coach/run_recap_fastpath.py` | Opening recap + split-detail prefetch, no-tools completions |
| `src/smartcoach_mobile_coach/run_recap_comparison_bundle.py` | Optional prior single-run-day facts (KPI-free) for recap LLM appendix |
| `src/smartcoach_mobile_coach/run_recap_week_volume_bundle.py` | Optional this vs last ISO week volume (KPI-free) for recap LLM appendix |
| `src/smartcoach_mobile_coach/run_recap_policy.py` | Recap fastpath eligibility + reason codes |
| `src/smartcoach_mobile_coach/dialogue_manager.py` | Turn / intent / response directive |
| `src/smartcoach_mobile_coach/agent_tools.py` | `execute_tool`: `find_runs_by_date`, `get_run_summary`, `get_run_splits`, … (legacy names `list_runs_for_local_date` / `get_run_insight` map here) |
| `src/smartcoach_mobile_coach/run_insight.py` | Run summary / facts JSON (`*_display` fields) |
| `src/smartcoach_mobile_coach/insight_cache.py` | Per-user TTL cache for run insight builds |
| `scripts/setup_coach_tools.py` | Seeds **`coach_tools`** table (OpenAI tool definitions for the tool loop) |
| `src/services/security/external_apis/openai_service.py` | `chat_completion` / `chat_completion_with_tools` (rate + cost tracked) |

Registered in `src/app.py` as `smartcoach_mobile_coach_bp`.

**Full env table and flow diagram:** [`docs/smartcoach_mobile_coach/README.md`](smartcoach_mobile_coach/README.md#environment-variables-mobile-coach).

## Environment (summary)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SMARTCOACH_MOBILE_AGENT_ENABLED` | `true` | Set to `false` / `0` / `off` to disable the route (503). |
| `SMARTCOACH_MOBILE_AGENT_HTTP_RPM` | `8` | Max `agent-messages` requests per user per minute (HTTP layer). |
| `SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL` | `3600` | Insight tool cache TTL (seconds). |
| `OPENAI_MOBILE_AGENT_TIMEOUT` | `180` | Per **completion** (seconds) for each model call in the mobile agent loop. **Does not** read `OPENAI_TIMEOUT`. |
| `SMARTCOACH_RUN_RECAP_FASTPATH` | `1` | Opening recap single-call fastpath (`0` / `false` / `no` to disable). |
| `SMARTCOACH_RUN_RECAP_FASTPATH_RETRY` | `1` | Retry once on empty fastpath completion before full tool loop (`0` to disable). |
| `SMARTCOACH_RUN_RECAP_PREFETCH_SLIM` | `1` | Recap fastpath LLM appendix: **facts-only** compact JSON by default; card payload still includes full `get_run_summary`. `0` restores KPIs in the appendix. |
| `SMARTCOACH_RUN_RECAP_COMPARISON_BUNDLE` | `1` | Prior **single-run** local days (facts-only `comparison_sessions` + **`when_vs_anchor`** phrasing). `0` disables. |
| `SMARTCOACH_RUN_RECAP_COMPARISON_LOOKBACK_DAYS` | `7` | Days before anchor to scan; clamped `1`–`21`. |
| `SMARTCOACH_RUN_RECAP_COMPARISON_MAX` | `2` | Max prior days attached; clamped `1`–`3`. |
| `SMARTCOACH_RUN_RECAP_WEEK_VOLUME_BUNDLE` | `1` | Recap appendix: **`week_volume_context`** (this vs last ISO week miles + run count + **`spoken_timeframe`**). `0` disables. |
| `SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM` | `1` | Coach tool `get_weekly_training_insight`: **orientation** payload by default; set `include_kpi_detail` true for full KPIs / zone charts. `0` = always full from tool. |
| `SMARTCOACH_SPLIT_DETAIL_FASTPATH` | `1` | Split-detail single-call fastpath. |
| `SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE` | `off` | When `1` / `true`, `POST …/agent-messages` may honor header **`X-SmartCoach-Eval-Model`** with an allowlisted OpenAI model (`gpt-4o`, `gpt-4o-mini`, `gpt-4o-2024-08-06`) for **scripted eval only**. **Leave off in production** unless you accept authenticated users picking the model. Response includes **`X-SmartCoach-Model-Used`**. |
| `SMARTCOACH_COACH_EVAL_REQUEST_SECRET` | *(unset)* | When set to a non-empty string, requests that send header **`X-SmartCoach-Eval-Secret`** with the **same** value (constant-time compare) may use **`X-SmartCoach-Eval-Model`** as if the override flag were on. Use a long random secret; rotate if leaked. `coach_feel_eval.py` reads this env and sends the header. Prefer this over the override flag when only **you** run eval scripts. |

Uses the same OpenAI env vars as the rest of the API (`OPENAI_API_KEY`, `OPENAI_CONVERSATION_MODEL`, etc.).

### Optional: prompt experiment (lighter system message)

For A/B on conversational tone vs template feel, set any of (values `1` / `true` / `yes` / `on`):

- `SMARTCOACH_EXPERIMENT_MINIMAL_DIRECTIVE` — short stub instead of full per-turn directive block.
- `SMARTCOACH_EXPERIMENT_MINIMAL_PREFS` — omit coaching-preferences section.
- `SMARTCOACH_EXPERIMENT_MINIMAL_BASE` — short base prompt instead of full `SYSTEM_PROMPT_BASE`.

Details: [`docs/smartcoach_mobile_coach/README.md`](smartcoach_mobile_coach/README.md#prompt-experiment-ab-default-off). Server logs `[coach_prompt_experiment]` when active.

### Scripted “feel” eval (Excel)

From repo root, with a real bearer token and API base URL:

```bash
# On the API server: either eval override, or a shared secret (see env table above).
export SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE=1
# Or: export SMARTCOACH_COACH_EVAL_REQUEST_SECRET='…'  # same value in shell below

export SMARTCOACH_EVAL_API_BASE_URL=https://…
export SMARTCOACH_EVAL_BEARER_TOKEN=eyJ…
# If using SMARTCOACH_COACH_EVAL_REQUEST_SECRET on the API, set it here too.
python scripts/coach_feel_eval.py -o coach_feel_eval.xlsx
```

Produces two worksheets (**`gpt-4o-mini`** and **`gpt-4o`**), each a **single continuous** conversation over the fixed prompt list; **Prompt** and **Response** columns are filled — you rate the rest locally.

**HTTP worker timeout:** `gunicorn.conf.py` sets **`timeout = 300`** by default (override with **`GUNICORN_TIMEOUT`**). `nixpacks.toml` / `Procfile` use `gunicorn -c gunicorn.conf.py run:app`.

**Railway (multi-service repo):** Do **not** put a **root** `railway.toml` with `deploy.startCommand` here — Railway applies that to **every** service (including the Vite **frontend**), which then crashes with `gunicorn: command not found`. On the **Python API** service only, set **Deploy → Start command** to: `gunicorn -c gunicorn.conf.py run:app` (or rely on Nixpacks if that service builds from this repo with `nixpacks.toml`). If a proxy still caps lower than Gunicorn, raise that limit too.

## Optional client header

Mobile sends `X-SmartCoach-Client: mobile` for log support (not used for authorization).
