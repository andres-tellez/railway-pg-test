from __future__ import annotations

# Removed imports: DataCollectionService, InsightsCalculationService
# This selector no longer collects data - it receives fitness metrics from Step 1


class Pass1WeeksSelector:
    """Deterministic fitness-based mapping for training-week count.

    Used by the orchestrator for Step 2 (fitness-only weeks before calendar constraints).

    Logic (safety-first):
    - Use current base mileage (weekly_mileage) as primary signal
    - Map to recommended duration:
        <15 mpw                     -> 24 weeks
        15–<20 mpw                  -> 20 weeks
        20–30 mpw                   -> 16 weeks
        >30 mpw                     -> 12 weeks
    """

    def __init__(self):
        # No dependencies needed - receives fitness metrics as parameters
        pass

    @staticmethod
    def _map_weeks(*, base_mileage: float) -> int:
        if base_mileage < 15.0:
            return 24
        if base_mileage < 20.0:
            return 20
        if base_mileage <= 30.0:
            return 16
        return 12
