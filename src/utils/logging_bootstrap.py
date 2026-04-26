"""Central logging setup for SmartCoach API.

Env:
  SMARTCOACH_LOG_LEVEL — DEBUG, INFO, WARNING, ERROR (optional; widens root logging).
  WEEKLY_TOTAL_TRACE — 0/false/no/off disables weekly total JSON traces to stderr.
    Any other explicit non-empty value (e.g. 1/true) forces them on; unset = on.

Weekly ``weekly_total_trace`` lines default on in every environment (including
production) so prod-only mobile builds still emit them in Railway logs. Use
``WEEKLY_TOTAL_TRACE=0`` to turn them off. Pytest stays quiet unless
``WEEKLY_TOTAL_TRACE=1``.
"""

from __future__ import annotations

import logging
import os
import sys


_WEEKLY_LOGGER_NAME = (
    "src.services.training_plan.v2.marathon.weekly_total_calculator_v2"
)
_WEEKLY_HANDLER_ATTR = "_smartcoach_weekly_trace_handler"


def _env_lower(name: str) -> str:
    return (os.getenv(name) or "").strip().lower()


def _explicit_weekly_trace() -> str | None:
    raw = os.getenv("WEEKLY_TOTAL_TRACE")
    if raw is None or not str(raw).strip():
        return None
    v = str(raw).strip().lower()
    if v in ("1", "true", "yes", "on"):
        return "on"
    if v in ("0", "false", "no", "off"):
        return "off"
    return None


def _want_weekly_total_trace(flask_debug: bool, *, testing: bool) -> bool:
    ex = _explicit_weekly_trace()
    if ex == "off":
        return False
    if ex == "on":
        return True
    if testing:
        return False
    if flask_debug or _env_lower("FLASK_DEBUG") in ("1", "true"):
        return True
    # Default on (including production) so prod-only mobile builds still get traces;
    # set WEEKLY_TOTAL_TRACE=0 to disable.
    return True


def _attach_weekly_trace_handler() -> None:
    log = logging.getLogger(_WEEKLY_LOGGER_NAME)
    if getattr(log, _WEEKLY_HANDLER_ATTR, False):
        return
    log.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.propagate = False
    setattr(log, _WEEKLY_HANDLER_ATTR, True)


def configure_smartcoach_logging(
    *, flask_debug: bool = False, testing: bool = False
) -> None:
    """Call once from ``create_app`` (after ``Flask()`` is constructed)."""
    if _want_weekly_total_trace(flask_debug, testing=testing):
        _attach_weekly_trace_handler()

    level_name = (os.getenv("SMARTCOACH_LOG_LEVEL") or "").strip().upper()
    if not level_name:
        return
    level = getattr(logging, level_name, None)
    if level is None or not isinstance(level, int):
        return

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        return

    root.setLevel(level)
    for h in root.handlers:
        try:
            if h.level == logging.NOTSET or h.level > level:
                h.setLevel(level)
        except (AttributeError, TypeError):
            continue
