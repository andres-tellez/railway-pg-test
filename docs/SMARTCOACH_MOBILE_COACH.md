# SmartCoach mobile Coach (agent) — backend

**Audience:** Mobile app **Coach** tab only (`smartcoach_app`). Web and legacy `POST …/messages` are unchanged.

## Entry point

- **`POST /api/conversations/{conversation_id}/agent-messages`**
- Body: `{ "message": string }`
- Success: `{ "response": string, … }` (same shape as plain `…/messages` for assistant text).

## Code layout

| Path | Role |
|------|------|
| `src/smartcoach_mobile_coach/routes.py` | Flask blueprint, auth, HTTP rate limit, persistence |
| `src/smartcoach_mobile_coach/orchestrator.py` | OpenAI tool loop (max 3 iterations) |
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

Uses the same OpenAI env vars as the rest of the API (`OPENAI_API_KEY`, `OPENAI_CONVERSATION_MODEL`, etc.).

## Optional client header

Mobile sends `X-SmartCoach-Client: mobile` for log support (not used for authorization).
