"""
Gunicorn settings for SmartCoach API (Railway + local).

Railpack / dashboard auto-detect often omits --timeout; default worker silence
timeout is 30s, which matches agent-messages 500s at ~30s. Override with env
GUNICORN_TIMEOUT if needed.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "60"))
