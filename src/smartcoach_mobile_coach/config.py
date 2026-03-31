"""Feature flags and tuning for mobile coach agent (railway-pg-test)."""

import os

# Master switch: default on for local/e2e; set SMARTCOACH_MOBILE_AGENT_ENABLED=false to disable.
_raw_agent = os.getenv("SMARTCOACH_MOBILE_AGENT_ENABLED", "true").strip().lower()
SMARTCOACH_MOBILE_AGENT_ENABLED = _raw_agent not in ("0", "false", "no", "off")

# HTTP-layer cap: agent-messages per user per minute (separate from OpenAI per-minute cap).
SMARTCOACH_MOBILE_AGENT_HTTP_RPM = int(
    os.getenv("SMARTCOACH_MOBILE_AGENT_HTTP_RPM", "8")
)

# Insight tool result cache TTL (seconds); per-user keys in insight_cache.py.
SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL = int(
    os.getenv("SMARTCOACH_MOBILE_INSIGHT_CACHE_TTL", "3600")
)

INSIGHT_SCHEMA_VERSION = "2"
