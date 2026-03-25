"""
HTTP client for SmartCoach MVP service (POST /analyze-run only).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

import httpx

from src.utils.config import config

logger = logging.getLogger(__name__)


Jsonish = Union[Dict[str, Any], list, str, None]


class SmartCoachUpstreamError(Exception):
    """Raised when SmartCoach returns an error or the request fails."""

    def __init__(
        self,
        status_code: int,
        payload: Optional[Jsonish] = None,
        log_message: Optional[str] = None,
    ):
        self.status_code = status_code
        self.payload = payload
        self.log_message = log_message
        super().__init__(log_message or str(status_code))


def post_analyze_run(run: Dict[str, Any], runner_id: str) -> Tuple[Dict[str, Any], int]:
    """
    POST {SMARTCOACH_BASE_URL}/analyze-run with {"run": ..., "runner_id": ...}.

    Returns (response_json, http_status) on 200.

    Raises:
        SmartCoachUpstreamError: not configured, transport error, or non-200/422.
        On 422, payload is the parsed JSON body (e.g. FastAPI {"detail": ...}).
    """
    base = config.SMARTCOACH_BASE_URL
    if not base:
        raise SmartCoachUpstreamError(
            503,
            {"detail": "SmartCoach is not configured (SMARTCOACH_BASE_URL)."},
        )

    url = f"{base.rstrip('/')}/analyze-run"
    timeout = httpx.Timeout(config.SMARTCOACH_TIMEOUT_SECONDS)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                json={"run": run, "runner_id": runner_id},
            )
    except httpx.RequestError as exc:
        logger.exception("SmartCoach request failed: %s", exc)
        raise SmartCoachUpstreamError(
            502,
            None,
            log_message="SmartCoach transport error",
        ) from exc

    if response.status_code == 422:
        try:
            body = response.json()
        except Exception:
            body = {"detail": response.text}
        raise SmartCoachUpstreamError(422, body)

    if response.status_code != 200:
        logger.warning(
            "SmartCoach HTTP %s for %s: %s",
            response.status_code,
            url,
            (response.text or "")[:500],
        )
        raise SmartCoachUpstreamError(response.status_code, None)

    return response.json(), 200
