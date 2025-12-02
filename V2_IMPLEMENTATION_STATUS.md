# V2 Refactored Plan Generation - Implementation Status

## ✅ Completed

1. **Directory Structure**
   - `src/services/training_plan/v2/` created
   - `v2/race_configs/` - Configuration system
   - `v2/marathon/` - Marathon-specific services
   - `v2/shared_v2/` - Shared services
   - `tests/utils/` - Comparison utilities
   - `scripts/` - Test scripts

2. **Comparison Utilities**
   - `tests/utils/plan_comparison.py` - Comparison functions
   - `scripts/compare_endpoints.py` - Test script

3. **Race Distance Configuration (Phase 1)**
   - `race_configs/base_config.py` - Abstract base class
   - `race_configs/marathon_config.py` - Marathon config with all values extracted

4. **Race Distance Factory (Phase 2)**
   - `race_distance_factory_v2.py` - Factory to get configs

5. **Shared Services (Copied)**
   - `shared_v2/pass1_weeks_selector_v2.py`
   - `shared_v2/long_run_spine_v2.py`
   - Note: `data_collection_service_v2.py` and `insights_calculation_service_v2.py` were removed (not used - orchestrator uses materialized view)

6. **Marathon Services (Partially Copied)**
   - `marathon/pass1_longrun_first_v2.py` - Copied, needs adaptation

## 🚧 In Progress

- Adapting marathon services to use config
- Creating orchestrator
- Creating route file

## ⏳ Remaining

1. **Marathon Services (Need to adapt to use config)**
   - `marathon/pass1_longrun_first_v2.py` - Update to use MarathonConfig
   - `marathon/weekly_total_calculator_v2.py` - Copy and adapt
   - `marathon/workout_types_v2.py` - Copy and adapt

2. **Other Services (Need to copy/adapt)**
   - `pass3_workout_distribution_v2.py`
   - `pass4_workout_details_v2.py`
   - `plan_validation_service_v2.py`
   - `recovery_week_insertion_service_v2.py`

3. **Orchestrator (Phase 3)**
   - `plan_generation_orchestrator_v2.py` - Main orchestrator

4. **Validators & Services (Phases 5-6)**
   - `draft_plan_validator_v2.py`
   - `plan_date_service_v2.py`

5. **Route File (Phase 9)**
   - `src/routes/plan_routes_v2.py` - New route with `/api/plan-v2/draft`

6. **App Registration (Phase 10)**
   - Update `src/app.py` to register new blueprint

## 📝 Next Steps

1. Complete marathon service adaptations
2. Create orchestrator
3. Create route file
4. Test with comparison script
