from typing import Any, Dict, List
import logging


GROWTH_MIN = 1.06  # 6%
GROWTH_MAX = 1.09  # 9%
GROWTH_CEIL = 1.105  # 10.5% ceiling to absorb rounding
CUTBACK_FACTOR = 0.75  # ~25% reduction (in-range 0.7–0.8)
BUILD_BLOCK = 4  # 3 build + 1 cutback
TAPER_W1 = 0.60  # ~60% of peak (range 0.6–0.8)
TAPER_W2 = 0.40  # ~40% of peak (range 0.4–0.6)


class GptCoachPass1Weekly:
    """Pass 1 - Generate weekly mileage skeleton only.

    Produces an array of weeks: [{"week_number", "phase", "weekly_mileage"}].
    Keeps constraints global and simple to reduce drift later.
    """

    def __init__(
        self,
        llm_client: Any,
        *,
        model: str | None = None,
        temperature: float | None = None
    ):
        # llm_client retained for compatibility; unused in deterministic Pass 1
        self.llm = llm_client

    # No prompt building needed in deterministic path
    def build_messages(
        self, ctx: Dict[str, Any]
    ) -> List[Dict[str, str]]:  # pragma: no cover
        return []

    def run(self, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Deterministic computation-only Pass 1 (no LLM)
        weeks = int(ctx.get("weeks", 16) or 16)
        start = float(ctx.get("current_weekly_mileage", 0) or 0)
        experience = (ctx.get("experience") or "").lower().strip()
        if start <= 0:
            start = 20.0
        skeleton = self._fallback_weekly_skeleton(weeks, start, experience)
        logging.getLogger(__name__).info("Pass1 generated weekly skeleton without LLM")
        return skeleton

    def _fallback_weekly_skeleton(
        self, weeks: int, start_miles: float, experience: str | None
    ) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        base = float(start_miles)
        cap = self._adaptive_peak_cap(base_mileage=base, experience=experience)
        current = max(10.0, min(cap, base if base > 0 else 20.0))
        g_target = GROWTH_MAX

        def round_half(x: float) -> float:
            return round(x * 2) / 2.0

        def apply_growth(prev: float) -> float:
            return round_half(min(prev * g_target, prev * GROWTH_CEIL))

        def rebound_cap(pre_cutback: float) -> float:
            r_pct = min(0.15, GROWTH_CEIL - 1.0)
            r_abs = 0.10 * pre_cutback
            return min(pre_cutback * (1.0 + r_pct), pre_cutback + r_abs)

        def violates_rolling_avg(new_val: float) -> bool:
            if len(result) < 2:
                return False
            avg_prev2 = (
                result[-1]["weekly_mileage"] + result[-2]["weekly_mileage"]
            ) / 2.0
            avg_new2 = (result[-1]["weekly_mileage"] + new_val) / 2.0
            return avg_new2 > avg_prev2 * 1.10 + 1e-6

        for i in range(1, weeks + 1):
            # Reserve last 2 weeks for taper; apply cutbacks every BUILD_BLOCK weeks before taper
            is_taper_window = i > weeks - 2
            if (i % BUILD_BLOCK == 0) and not is_taper_window:
                # Adaptive cutback: ensure next week can rebound ≤30% from cutback back toward pre-cutback
                min_cutback_to_allow_safe_rebound = current / 1.30
                planned_cutback = round_half(current * CUTBACK_FACTOR)
                miles = max(
                    10.0,
                    round_half(max(planned_cutback, min_cutback_to_allow_safe_rebound)),
                )
            else:
                # Keep growth conservative and strictly <10.5%
                inc = apply_growth(current)
                miles = min(cap, inc)
                # after cutback, resume near pre-cutback
                if i > 1 and ((i - 1) % BUILD_BLOCK == 0):
                    prev_non_cutback = (
                        result[-2]["weekly_mileage"] if len(result) >= 2 else current
                    )
                    miles = min(miles, rebound_cap(prev_non_cutback))
                    # Also cap vs immediate prior (≤30%)
                    miles = min(miles, result[-1]["weekly_mileage"] * 1.30)

                # rolling-average safety: shrink if necessary
                while violates_rolling_avg(miles) and g_target > GROWTH_MIN:
                    g_target = max(GROWTH_MIN, g_target - 0.005)
                    miles = min(cap, apply_growth(current))

            current = miles
            phase = (
                "Base Building"
                if i <= max(1, weeks // 4)
                else (
                    "Build"
                    if i <= max(2, weeks // 2)
                    else "Peak" if i <= weeks - 2 else "Taper"
                )
            )

            result.append(
                {
                    "week_number": i,
                    "phase": phase,
                    "weekly_mileage": float(miles),
                }
            )

        # Enforce proper taper: last 2 weeks drop to ~60% and ~40% of peak
        if len(result) >= 2:
            peak_candidates = [x["weekly_mileage"] for x in result[:-2]] or [
                result[-2]["weekly_mileage"]
            ]
            peak = max(peak_candidates)
            w11 = round_half(max(10.0, peak * TAPER_W1))
            w12 = round_half(max(5.0, peak * TAPER_W2))
            # ensure descending
            result[-2]["weekly_mileage"] = min(result[-2]["weekly_mileage"], w11)
            result[-1]["weekly_mileage"] = min(result[-1]["weekly_mileage"], w12)
            result[-2]["phase"] = "Taper"
            result[-1]["phase"] = "Taper"

        return result

    @staticmethod
    def _adaptive_peak_cap(*, base_mileage: float, experience: str | None) -> float:
        """Derive a safe peak cap from base mileage rather than a hard constant.

        Rationale (finish goal): cap ≈ base * k, where k varies by base and experience.
        The cap is a safety guard, not a target, and keeps growth bounded.
        """
        exp = (experience or "").lower().strip()
        if base_mileage <= 0:
            return 40.0
        if base_mileage < 20.0:
            k = 2.0 if exp != "experienced" else 2.2
        elif base_mileage <= 30.0:
            k = 2.1 if exp != "experienced" else 2.3
        else:
            k = 2.2 if exp != "experienced" else 2.4
        return base_mileage * k
