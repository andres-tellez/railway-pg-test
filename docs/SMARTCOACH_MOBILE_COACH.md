# SmartCoach mobile Coach (agent) — backend

**Audience:** Mobile app **Coach** tab only (`smartcoach_app`). Web and legacy `POST …/messages` are unchanged.

## Entry point

- **`POST /api/conversations/{conversation_id}/agent-messages`**
- Body: `{ "message": string, "client_local_date": "YYYY-MM-DD", "client_timezone"?: string }`
  - **`client_local_date`** (required for correct “today”): the user’s **device** local calendar date. Mobile sends this every turn.
  - **`client_timezone`**: optional IANA name (e.g. `America/Chicago`) for the system prompt; does not change SQL (activities still use per-activity timezone).
  - If `client_local_date` is missing or invalid, the server falls back to **UTC** calendar date (logged) — prefer always sending it from the app.
- Success: `{ "response": string, … }` (same shape as plain `…/messages` for assistant text).

## Code layout

| Path | Role |
|------|------|
| `src/smartcoach_mobile_coach/routes.py` | Flask blueprint, auth, HTTP rate limit, persistence |
| `src/smartcoach_mobile_coach/orchestrator.py` | OpenAI tool loop (bounded iterations; see `SMARTCOACH_AGENT_MAX_LOOPS`) |
| `src/smartcoach_mobile_coach/agent_tools.py` | `list_runs_for_local_date`, `get_run_insight` |
| `src/smartcoach_mobile_coach/run_insight.py` | Facts + peer comparison JSON (`*_display` fields) |
| `src/smartcoach_mobile_coach/insight_cache.py` | Per-user TTL cache for `get_run_insight` |
| `src/services/security/external_apis/openai_service.py` | `chat_completion_with_tools` (rate + cost tracked) |

Registered in `src/app.py` as `smartcoach_mobile_coach_bp`.

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `SMARTCOACH_MOBILE_AGENT_ENABLED` | `true` | Set to `false` / `0` / `off` to disable the route (503). |
| `SMARTCOACH_MOBILE_AGENT_HTTP_RPM` | `8` | Max `agent-messages` requests per user per minute (HTTP layer). |
| `SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL` | `3600` | Insight tool cache TTL (seconds). |
| `OPENAI_MOBILE_AGENT_TIMEOUT` | `180` | Per **completion** (seconds) for each `chat_completion_with_tools` in the mobile agent loop. **Does not** read `OPENAI_TIMEOUT`. |
| `SMARTCOACH_COACH_EVAL_MODEL_OVERRIDE` | `off` | When `1` / `true`, `POST …/agent-messages` may honor header **`X-SmartCoach-Eval-Model`** with an allowlisted OpenAI model (`gpt-4o`, `gpt-4o-mini`, `gpt-4o-2024-08-06`) for **scripted eval only**. **Leave off in production** unless you accept authenticated users picking the model. Response includes **`X-SmartCoach-Model-Used`**. |
| `SMARTCOACH_COACH_EVAL_REQUEST_SECRET` | *(unset)* | When set to a non-empty string, requests that send header **`X-SmartCoach-Eval-Secret`** with the **same** value (constant-time compare) may use **`X-SmartCoach-Eval-Model`** as if the override flag were on. Use a long random secret; rotate if leaked. `coach_feel_eval.py` reads this env and sends the header. Prefer this over the override flag when only **you** run eval scripts. |

Uses the same OpenAI env vars as the rest of the API (`OPENAI_API_KEY`, `OPENAI_CONVERSATION_MODEL`, etc.).

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
