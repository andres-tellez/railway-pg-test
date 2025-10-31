"""
Layer 4: GPT Coach Service

Calls the LLM with the Layer 3 prompt and returns a parsed, validated plan JSON.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class GptCoachService:
    def __init__(
        self,
        *,
        llm_client: Any,
        timeout_seconds: int = 20,
        retries: int = 1,
        backoff_seconds: float = 0.5,
    ) -> None:
        self._llm = llm_client
        self._timeout = timeout_seconds
        self._retries = retries
        self._backoff = backoff_seconds

    def generate_plan(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = prompt.get("messages", [])
        config: Dict[str, Any] = prompt.get("config", {})

        if not isinstance(messages, list) or not messages:
            raise ValueError("invalid prompt: messages missing")

        # Force JSON response format if not present
        # Merge defaults: force JSON response and optional timeout from env
        import os

        default_timeout = float(os.getenv("TRAINING_PLAN_LLM_TIMEOUT", "60"))
        config = {
            **config,
            "response_format": config.get("response_format") or {"type": "json_object"},
            "timeout": config.get("timeout", default_timeout),
        }

        # Call the LLM with retries
        attempts = 0
        last_error: Optional[Exception] = None
        while attempts <= self._retries:
            try:
                raw = self._llm.completion(messages, config)
                break
            except (TimeoutError, ConnectionError) as e:
                last_error = e
                attempts += 1
                if attempts > self._retries:
                    break
                time.sleep(self._backoff * attempts)
            except Exception as e:
                # Unknown client error; treat as retryable once
                last_error = e
                attempts += 1
                if attempts > self._retries:
                    break
                time.sleep(self._backoff * attempts)

        if attempts > self._retries and last_error is not None:
            raise RuntimeError(f"LLM request failed after retries: {last_error}")

        # Parse/validate outside of retry loop so ValueError bubbles up
        return self._parse_and_validate(raw)

    def _parse_and_validate(self, raw_response: str) -> Dict[str, Any]:
        # Strip code fences if present
        text = raw_response.strip()
        if text.startswith("```"):
            # Remove first fenced line and trailing fence
            lines = [ln for ln in text.splitlines()]
            # drop first line (``` or ```json)
            if lines:
                lines = lines[1:]
            # drop trailing ``` if present
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Parse JSON
        try:
            plan = json.loads(text)
        except Exception as e:
            raise ValueError("invalid JSON in LLM response") from e

        # Minimal schema/invariants validation
        self._validate_plan_shape(plan)
        return plan

    def _validate_plan_shape(self, plan: Dict[str, Any]) -> None:
        if not isinstance(plan, dict):
            raise ValueError("schema: plan must be an object")
        if "plan_name" not in plan:
            raise ValueError("schema: missing plan_name")
        if (
            "weeks" not in plan
            or not isinstance(plan["weeks"], list)
            or not plan["weeks"]
        ):
            raise ValueError("schema: weeks must be a non-empty list")

        last_week_num = 0
        for w in plan["weeks"]:
            if not isinstance(w, dict) or "week_number" not in w or "workouts" not in w:
                raise ValueError("schema: each week must have week_number and workouts")
            if (
                not isinstance(w["week_number"], int)
                or w["week_number"] <= last_week_num
            ):
                raise ValueError("schema: week_number must be ascending integers")
            last_week_num = w["week_number"]
            if not isinstance(w["workouts"], list) or not w["workouts"]:
                raise ValueError("schema: workouts must be a non-empty list")
            for wo in w["workouts"]:
                if not isinstance(wo, dict):
                    raise ValueError("schema: workout must be an object")
                for k in ["day", "workout_type", "distance_miles"]:
                    if k not in wo:
                        raise ValueError(f"schema: workout missing {k}")
                if wo.get("distance_miles", 0) < 0:
                    raise ValueError("schema: workout distance must be non-negative")

    @staticmethod
    def create_default() -> "GptCoachService":
        """
        Factory helper: creates GptCoachService using env-based LLM provider.
        For tests, prefer explicit injection: GptCoachService(llm_client=fake).
        """
        from .llm_factory import create_llm_client

        client = create_llm_client()
        timeout = int(os.getenv("TRAINING_PLAN_LLM_TIMEOUT_SECONDS", "20"))
        retries = int(os.getenv("TRAINING_PLAN_LLM_RETRIES", "1"))
        return GptCoachService(
            llm_client=client, timeout_seconds=timeout, retries=retries
        )
