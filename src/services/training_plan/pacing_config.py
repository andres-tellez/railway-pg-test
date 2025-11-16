from dataclasses import dataclass


@dataclass(frozen=True)
class PacingConfig:
    # Weekly aggregation filters
    min_week_runs: int = 3
    easyish_min_mi: float = 3.0
    easyish_max_mi: float = 12.0

    # Aggregate-based adjustment triggers/caps
    easy_diff_trigger_sec: int = 10  # trigger if |weekly_median - seed_center| > 10s
    weekly_adjust_cap_sec: int = 10  # clamp weekly delta to ±10s

    # Long run signal (optional cue bias; not altering zones yet)
    lr_min_qualifying_mi: float = 10.0


CONFIG = PacingConfig()
