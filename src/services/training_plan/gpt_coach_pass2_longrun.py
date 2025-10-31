from typing import Any, Dict, List
import json
import os
import logging
from src.services.training_plan.json_utils import (
    parse_json_flexible,
    extract_first_list,
)


class GptCoachPass2LongRun:
    """Pass 2 - Add long_run_miles to each week according to constraints."""

    def __init__(
        self,
        llm_client: Any,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ):
        self.llm = llm_client
        self.model = model or os.getenv("TRAINING_PLAN_GPT_MODEL", "gpt-4o-mini")
        self.temperature = (
            float(os.getenv("TRAINING_PLAN_TEMPERATURE", "0.2"))
            if temperature is None
            else temperature
        )
        self.timeout = float(os.getenv("TRAINING_PLAN_LLM_TIMEOUT", "60"))

    def build_messages(self, weeks_skel: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        skel_str = json.dumps(weeks_skel)
        return [
            {
                "role": "system",
                "content": "You are an elite marathon coach (Jack Daniels methodology). Respond with ONLY valid JSON. No markdown, no backticks, no prose.",
            },
            {
                "role": "user",
                "content": f"""Add a long_run_miles field to each week in the skeleton and return an object with key "weeks".

Skeleton:
{skel_str}

Constraints:
- Long run ≈ 25–35% of weekly_mileage and ≤ 20 miles.
- In normal weeks: long_run_miles ≤ previous_week_long_run + 1.0 mile.
- After a cutback week: long_run_miles ≤ pre-cutback long run (+1.0 max). Do not leap past pre-cutback in a single week.

Return JSON object {{"weeks": [...]}} with the same objects plus long_run_miles only. If any constraint would be violated, reduce the long run to the largest legal value and return.
Respond with ONLY a JSON object. Do not include code fences or explanations. If unsure, return {{"weeks": []}}.
""",
            },
        ]

    def run(self, weeks_skel: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Deterministic computation-only Pass 2 (no LLM)
        result: List[Dict[str, Any]] = []
        prev_long: float | None = None
        pre_cutback_long: float | None = None
        for w in weeks_skel:
            weekly = float(w.get("weekly_mileage", 0) or 0)
            week_num = int(w.get("week_number", len(result) + 1))
            # Desired range 25-35% of weekly
            min_lr = max(0.0, round(weekly * 0.25 * 2) / 2)
            max_lr = max(min_lr, round(weekly * 0.35 * 2) / 2)
            desired = round(weekly * 0.30 * 2) / 2
            lr = min(20.0, max(min_lr, min(desired, max_lr)))

            # Enforce progression: +1.0 max from previous
            if prev_long is not None:
                lr = min(lr, round((prev_long + 1.0) * 2) / 2)

            # Detect cutback weeks: if weekly < previous weekly by >= 15%
            is_cutback = False
            if result:
                prev_weekly = (
                    float(result[-1]["weekly_mileage"])
                    if isinstance(result[-1]["weekly_mileage"], (int, float))
                    else weekly
                )
                if prev_weekly > 0 and weekly <= prev_weekly * 0.85:
                    is_cutback = True
                    pre_cutback_long = prev_long

            # After cutback resume: cap at pre-cutback +1
            if not is_cutback and pre_cutback_long is not None and week_num % 4 == 1:
                lr = min(lr, round((pre_cutback_long + 1.0) * 2) / 2)
                pre_cutback_long = None

            prev_long = lr
            out = dict(w)
            out["long_run_miles"] = float(lr)
            result.append(out)

        logging.getLogger(__name__).info("Pass2 computed long runs without LLM")
        return result
