## Race Distance Configuration Reference

This document captures the marathon-specific constants that now live under
`src/services/training_plan/v2/race_configs/`. Keeping them in one place makes it
easier to extend the deterministic LR-first pipeline to future distances (half,
10K, 5K) without scattering magic numbers across passes.

### Shared contract (`RaceDistanceConfig`)

Every distance-specific config must implement the following properties:

- `target_peak_miles` – long-run peak target
- `taper_weeks` / `taper_ratios` – taper duration & percentage drop each week
- `long_run_increment` – default mile increase per build week
- `cutback_every` / `cutback_factor` – cadence and size of cutbacks during the build
- `recovery_long_run_floor` – minimum LR allowed when scheduling a recovery week
- `recovery_reduction_ratio` – percentage of the most recent long run to target for recovery
- `long_run_percentage_ranges` – allowable long-run share vs. weekly mileage for 3/4/5 day plans
- `peak_caps` – max weekly mileage for 3/4/5 day plans
- `weekly_increase_cap` – guardrail used when computing total mileage
- `non_long_shares` / `min_non_long_day` – distribution inputs for Pass3
- `high_long_run_threshold` / `sustained_high_threshold` – validation warnings
- `race_distance_miles` – canonical race distance
- `race_week_template()` – structured description of the race-week workouts appended by the orchestrator

### Marathon defaults (`MarathonConfig`)

| Setting | Value | Notes / Usage |
| --- | --- | --- |
| `target_peak_miles` | 20.0 | Used by Pass1 spine + validation |
| `long_run_increment` | 1.0 | Adds 1 mile per build week |
| `cutback_every` | 3 | Force recovery every ~3 weeks |
| `cutback_factor` | 0.70 | 30% drop on cutbacks |
| `recovery_long_run_floor` | 8.0 | Protects marathon athletes from <8 mile “long” runs |
| `recovery_reduction_ratio` | 0.70 | Recovery LR ≈ 70% of recent longest |
| `taper_weeks` | 3 | With ratios `[0.70, 0.50, 0.25]` |
| `long_run_percentage_ranges` | `{3: (0.40, 0.50), 4: (0.35, 0.45), 5: (0.30, 0.40)}` | Pass3 validation |
| `peak_caps` | `{3: 42, 4: 46, 5: 50}` | Weekly mileage ceiling |
| `weekly_increase_cap` | 0.08 | 8% per-week increase |
| `non_long_shares` | `[0.55,0.45]` / `[0.40,0.30,0.30]` / `[0.32,0.25,0.23,0.20]` | Pass3 distribution |
| `min_non_long_day` | 3.0 miles | Enforced in Pass3 |
| `high_long_run_threshold` | 18.0 miles | Validation warning |
| `sustained_high_threshold` | 19.0 miles | Validation warning |
| `race_week_template` | 3-3-2-2-Easy + Race Day 26.2 | Consumed by orchestrator `_append_race_week` |

### Adding a new race distance

1. Create a new config class (e.g., `HalfMarathonConfig`) implementing the interface above.
2. Provide a `race_week_template()` for that distance (even if it mirrors marathon).
3. Register the config inside `race_distance_factory_v2.get_race_distance_services`.
4. If the distance needs unique pass logic (e.g., different workout types), add a sibling module under `src/services/training_plan/v2/<distance>/`.
5. Cover the new constants with unit tests (`tests/services/training_plan/v2/`).

Following this checklist ensures that marathon stays stable while we expand to half, 10K, and 5K plans.
