# MARATHON TRAINING PLAN GENERATION ARCHITECTURE

## Version 3.0 - Layered Hybrid Architecture

**Last Updated:** October 28, 2025
**Status:** Ready for Implementation
**Approach:** Hybrid (Code Calculations → GPT Generation → Code Validation)

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Layer Specifications](#layer-specifications)
4. [Data Flow](#data-flow)
5. [Testing Strategy](#testing-strategy)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Research Foundation](#research-foundation)

---

## 🎯 EXECUTIVE SUMMARY

### **Core Principle**

Use **code for calculations** and **GPT for coaching decisions** to create safe, personalized marathon training plans.

### **Why This Architecture?**

Based on extensive research:

- ✅ **Safety:** Code enforces critical training rules (10% rule, injury prevention)
- ✅ **Flexibility:** GPT handles complex coaching decisions and edge cases
- ✅ **Reliability:** Validation layer ensures plan safety before storage
- ✅ **Maintainability:** Modular layers can be enhanced independently
- ✅ **Research-Backed:** Aligns with best practices for AI-assisted fitness coaching

### **Key Research Finding**

Study (PMC10915606) found:

- AI-generated training plans improve significantly with structured input data
- Plans require validation against coaching standards
- Hybrid approach (pre-calculated data + AI generation) yields best results

---

## 🏗️ ARCHITECTURE OVERVIEW

### **6-Layer Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Data Collection Service                            │
│ Purpose: Gather raw data from database                      │
│ Output: Raw Strava activities + User profile                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Insights Calculation Service                       │
│ Purpose: Calculate safety-critical metrics                  │
│ Output: Structured baseline metrics (facts only)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Prompt Builder Service                             │
│ Purpose: Structure data into optimized GPT prompt           │
│ Output: Lightweight, structured prompt (~1,000 tokens)      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: GPT Coach Service                                  │
│ Purpose: Generate week-by-week training plan                │
│ Output: Structured JSON training plan                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 5: Plan Validation Service                            │
│ Purpose: Verify plan follows safety rules                   │
│ Output: Validated plan or list of violations                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 6: Plan Storage Service                               │
│ Purpose: Save validated plan to database                    │
│ Output: Created plan with workouts in database              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 LAYER SPECIFICATIONS

### **LAYER 1: Data Collection Service**

**File:** `src/services/training_plan/data_collection_service.py`

**Responsibility:**
Fetch and aggregate all data needed for plan generation.

**Inputs:**

- `user_id` (UUID)
- `session` (SQLAlchemy session)

**Outputs:**

```python
{
    "user_profile": {
        "age_group": "30-39",
        "height_feet": 5,
        "height_inches": 10,
        "weight": 165,
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    },
    "strava_activities": [
        {
            "date": "2025-10-20",
            "distance": 5.2,
            "moving_time": 2850,  # seconds
            "average_heartrate": 145,
            # ... other activity fields
        },
        # ... more activities
    ],
    "plan_request": {
        "race_date": "2025-06-15",
        "primary_goal": "Just Finish",
        "marathon_experience": "First",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
        "notes": "...",
    }
}
```

**Key Functions:**

- `fetch_user_profile(session, user_id)` → User profile data
- `fetch_strava_activities(session, user_id, weeks=12)` → Recent running activities
- `collect_all_data(session, user_id, plan_request)` → Complete data package

**Testing:**

- Unit tests with mock database data
- Verify data structure matches expected format
- Test with users having varying amounts of history

---

### **LAYER 2: Insights Calculation Service**

**File:** `src/services/training_plan/insights_calculation_service.py`

**Responsibility:**
Calculate objective, safety-critical metrics from raw data.

**Inputs:**
Output from Layer 1 (raw data)

**Outputs:**

```python
{
    "runner_identity": {
        "age": 35,
        "bmi": 23.4,
        "goal": "Just Finish",
        "experience": "First",
        "race_date": "2025-06-15",
        "weeks_until_race": 28,
        "available_days": ["Mon", "Wed", "Fri", "Sat"],
        "days_per_week": 4,
    },
    "current_fitness": {
        "data_quality": "GOOD",  # INSUFFICIENT|MINIMAL|GOOD|EXCELLENT
        "weeks_of_history": 8,
        "avg_weekly_mileage": 18.5,
        "mileage_range": {"min": 12, "max": 24},
        "longest_run_recent": 10.2,  # miles, last 60 days
        "runs_per_week": 3.5,
        "consistency_score": 85,  # % of weeks with running
        "avg_pace": "10:15",  # min:sec per mile
        "easy_pace_estimate": "10:45",  # 75th percentile
        "fast_pace_estimate": "9:30",  # 25th percentile
    },
    "heart_rate_zones": {
        "max_hr_estimate": 185,
        "zone_1": {"min": 93, "max": 111, "name": "Recovery"},
        "zone_2": {"min": 111, "max": 130, "name": "Aerobic"},
        "zone_3": {"min": 130, "max": 148, "name": "Tempo"},
        "zone_4": {"min": 148, "max": 167, "name": "Threshold"},
        "zone_5": {"min": 167, "max": 185, "name": "VO2 Max"},
    },
    "safety_assessment": {
        "time_sufficient": True,  # >= 16 weeks
        "time_status": "SUFFICIENT",
        "base_adequate": True,  # >= 15 miles/week
        "base_status": "ADEQUATE",
        "injury_risk_level": "LOW",  # LOW|MODERATE|HIGH
        "acwr": 1.05,  # Acute:Chronic Workload Ratio
        "risk_factors": [],  # List of detected issues
        "safe_peak_mileage": 38,  # Projected using 10% rule
        "target_peak_mileage": 35,  # For "Just Finish" goal
        "plan_feasible": True,
    },
}
```

**Key Functions:**

- `calculate_runner_identity(raw_data)` → Demographics and constraints
- `calculate_current_fitness(activities)` → Fitness baseline metrics
- `calculate_heart_rate_zones(age)` → HR zone ranges
- `assess_safety(current_fitness, race_date)` → Risk and feasibility assessment
- `generate_insights(raw_data)` → Complete insights package

**Calculation Details:**

```python
# Weekly Mileage (4-week rolling average)
avg_weekly_mileage = sum(weekly_totals[-4:]) / 4

# Consistency Score
consistency = (weeks_with_runs / total_weeks) * 100

# Max HR Estimate (Tanaka formula - more accurate than 220-age)
max_hr = 208 - (0.7 * age)

# Heart Rate Zones (5-zone model)
zone_1 = (max_hr * 0.50, max_hr * 0.60)  # Recovery
zone_2 = (max_hr * 0.60, max_hr * 0.70)  # Aerobic
zone_3 = (max_hr * 0.70, max_hr * 0.80)  # Tempo
zone_4 = (max_hr * 0.80, max_hr * 0.90)  # Threshold
zone_5 = (max_hr * 0.90, max_hr * 1.00)  # VO2 Max

# ACWR (Acute:Chronic Workload Ratio)
acute_load = last_week_mileage
chronic_load = avg_of_last_4_weeks
acwr = acute_load / chronic_load
# Optimal: 0.8-1.3 | Caution: 1.3-1.5 | High Risk: >1.5

# Safe Peak Mileage Projection (10% rule with cutback weeks)
weeks_available = (race_date - today).days // 7
# Account for cutback weeks (every 3-4 weeks = ~25% of training weeks)
training_weeks = weeks_available * 0.75
safe_peak = current_mileage * (1.10 ** training_weeks)

# Pace Estimates
avg_pace = weighted_average(all_paces, by_distance)
easy_pace = 75th_percentile(paces)  # Slower 75% of runs
fast_pace = 25th_percentile(paces)  # Faster 25% of runs
```

**Testing:**

- Unit tests for each calculation function
- Test edge cases (0 history, 1 week, 52 weeks, etc.)
- Verify formulas match sports science standards
- Test safety thresholds

---

### **LAYER 3: Prompt Builder Service**

**File:** `src/services/training_plan/prompt_builder_service.py`

**Responsibility:**
Convert insights into optimized GPT prompt.

**Inputs:**
Output from Layer 2 (calculated insights)

**Outputs:**

```python
{
    "messages": [
        {
            "role": "system",
            "content": "You are an elite marathon running coach..."
        },
        {
            "role": "user",
            "content": "# RUNNER BASELINE\nAge: 35\n..."
        }
    ],
    "config": {
        "model": "gpt-4",
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
}
```

**Prompt Template:**

```markdown
# SYSTEM ROLE

You are an elite marathon running coach with 20 years of experience.
You specialize in creating safe, evidence-based training plans for
beginner and intermediate runners.

# RUNNER BASELINE

Age: {age}
Goal: {goal}
Experience: {experience}
Race Date: {race_date} ({weeks_until} weeks available)

## Current Fitness

- Weekly Mileage: {avg_weekly_miles} miles (last 4 weeks)
- Longest Recent Run: {longest_run} miles
- Running Frequency: {runs_per_week} runs/week
- Consistency: {consistency}%

## Training Readiness

- Base Fitness: {base_status}
- Time Available: {time_status}
- Injury Risk: {risk_level}

## Current Pacing

- Average Pace: {avg_pace} /mile
- Easy Runs: ~{easy_pace} /mile
- Faster Efforts: ~{fast_pace} /mile

## Heart Rate Zones

- Max HR: {max_hr} bpm
- Zone 1 (Recovery): {z1_range}
- Zone 2 (Aerobic): {z2_range}
- Zone 3 (Tempo): {z3_range}
- Zone 4 (Threshold): {z4_range}
- Zone 5 (VO2 Max): {z5_range}

## Schedule Constraints

- Available Days: {training_days}
- Days per Week: {days_per_week}

# TASK

Generate a {weeks_until}-week marathon training plan following these principles:

- Progressive overload: Max 10% weekly mileage increase
- Cutback weeks: Every 3-4 weeks, reduce 20-30%
- 80/20 intensity: 80% easy (Z1-2), 20% quality (Z3-5)
- Peak long run: 18-20 miles, 3 weeks before race
- Taper: 2-3 weeks, maintaining intensity while reducing volume

# OUTPUT FORMAT (JSON)

{
"plan_name": "string",
"philosophy": "string",
"weeks": [
{
"week_number": 1,
"phase": "Base Building|Endurance|Peak|Taper",
"total_miles": 20,
"notes": "string",
"workouts": [
{
"day": "Monday",
"type": "Easy Run|Tempo|Long Run|Rest|Cross-Training",
"miles": 4.0,
"pace_target": "10:30 /mile",
"hr_zone": "Z1-Z2",
"description": "..."
}
]
}
],
"nutrition_guidance": "string",
"race_week_strategy": "string",
"safety_notes": "string"
}
```

**Key Functions:**

- `build_system_prompt()` → GPT role definition
- `build_user_prompt(insights)` → Runner-specific data
- `add_conditional_warnings(insights)` → Special instructions if needed
- `build_complete_prompt(insights)` → Full prompt ready for GPT

**Conditional Logic:**

```python
# Add warnings based on insights
if insights["safety_assessment"]["time_sufficient"] == False:
    add_warning("TIME_CONSTRAINT", "Less than 16 weeks - conservative approach")

if insights["safety_assessment"]["injury_risk_level"] == "HIGH":
    add_warning("HIGH_RISK", "Signs of overtraining - emphasize recovery")

if insights["current_fitness"]["data_quality"] == "INSUFFICIENT":
    add_warning("LIMITED_DATA", "Use conservative template approach")
```

**Testing:**

- Unit tests for prompt generation
- Verify token count stays under target (~1,000 tokens)
- Test with different runner profiles
- Validate JSON schema specification is correct

---

### **LAYER 4: GPT Coach Service**

**File:** `src/services/training_plan/gpt_coach_service.py`

**Responsibility:**
Send prompt to GPT and parse response into structured plan.

**Inputs:**

- Prompt from Layer 3
- GPT configuration

**Outputs:**

```python
{
    "plan_name": "Marathon Training - First Timer's Plan",
    "philosophy": "Conservative progression with emphasis on consistency...",
    "weeks": [
        {
            "week_number": 1,
            "phase": "Base Building",
            "total_miles": 20,
            "notes": "Establish baseline, focus on easy running",
            "workouts": [
                {
                    "day": "Monday",
                    "type": "Easy Run",
                    "miles": 4.0,
                    "pace_target": "10:45 /mile",
                    "hr_zone": "Z1-Z2",
                    "description": "Easy pace run, keep it conversational..."
                },
                # ... more workouts
            ]
        },
        # ... more weeks
    ],
    "nutrition_guidance": "...",
    "race_week_strategy": "...",
    "safety_notes": "..."
}
```

**Key Functions:**

- `call_gpt_api(prompt, config)` → Raw GPT response
- `parse_json_response(response)` → Parsed plan object
- `handle_api_errors(error)` → Error handling and retries
- `generate_plan(prompt)` → Complete generation flow

**Error Handling:**

```python
# Retry logic for API failures
max_retries = 3
retry_delay = [1, 2, 5]  # seconds

# Validation of GPT response
- Must be valid JSON
- Must contain required fields
- Must have correct number of weeks
- Workouts must match available training days
```

**Testing:**

- Integration tests with real GPT API (limited)
- Mock tests for error scenarios
- Validate JSON parsing
- Test retry logic

---

### **LAYER 5: Plan Validation Service**

**File:** `src/services/training_plan/plan_validation_service.py`

**Responsibility:**
Verify GPT-generated plan follows safety rules.

**Inputs:**
GPT-generated plan from Layer 4

**Outputs:**

```python
{
    "valid": True,
    "violations": [],
    "warnings": [],
    "plan": {...}  # Original plan if valid
}

# OR if violations found:
{
    "valid": False,
    "violations": [
        {
            "rule": "10_PERCENT_RULE",
            "severity": "ERROR",
            "location": "Week 3 to Week 4",
            "details": "Increase from 20 to 25 miles (25% increase)",
            "recommendation": "Reduce Week 4 to 22 miles"
        }
    ],
    "warnings": [
        {
            "rule": "CONSECUTIVE_HARD_DAYS",
            "severity": "WARNING",
            "location": "Week 5: Tuesday and Wednesday",
            "details": "Back-to-back tempo and threshold workouts",
            "recommendation": "Add easy day between quality workouts"
        }
    ],
    "plan": {...}  # Original plan with issues
}
```

**Validation Rules:**

```python
VALIDATION_RULES = {
    "10_PERCENT_RULE": {
        "check": "Weekly mileage increases <= 10%",
        "severity": "ERROR",
        "threshold": 1.10,
    },
    "CUTBACK_WEEKS": {
        "check": "Cutback weeks every 3-4 weeks",
        "severity": "WARNING",
        "frequency": [3, 4],
    },
    "PEAK_LONG_RUN": {
        "check": "Peak long run 18-20 miles",
        "severity": "ERROR",
        "range": [18, 20],
    },
    "PEAK_TIMING": {
        "check": "Peak long run 3 weeks before race",
        "severity": "WARNING",
        "timing": 3,
    },
    "REST_DAYS": {
        "check": "Minimum 2 rest days per week",
        "severity": "ERROR",
        "minimum": 2,
    },
    "CONSECUTIVE_HARD": {
        "check": "No back-to-back hard workouts",
        "severity": "WARNING",
    },
    "TAPER_PRESENT": {
        "check": "Taper period exists (2-3 weeks)",
        "severity": "ERROR",
        "duration": [2, 3],
    },
}
```

**Key Functions:**

- `validate_mileage_progression(weeks)` → Check 10% rule
- `validate_cutback_weeks(weeks)` → Verify recovery weeks
- `validate_long_run_progression(weeks)` → Check long run safety
- `validate_rest_days(weeks)` → Ensure adequate recovery
- `validate_taper(weeks)` → Verify taper structure
- `validate_complete_plan(plan)` → Run all validations

**Testing:**

- Unit tests for each validation rule
- Test with intentionally flawed plans
- Verify violation detection accuracy
- Test with edge cases

---

### **LAYER 6: Plan Storage Service**

**File:** `src/services/training_plan/plan_storage_service.py`

**Responsibility:**
Save validated plan to database.

**Inputs:**

- Validated plan from Layer 5
- User ID
- Plan request metadata

**Outputs:**

```python
{
    "plan_id": 123,
    "workouts_created": 112,
    "status": "SUCCESS"
}
```

**Key Functions:**

- `create_plan_record(session, user_id, plan_data)` → Create Plan entry
- `create_workout_records(session, plan_id, workouts)` → Create PlanWorkout entries
- `deactivate_old_plans(session, user_id)` → Mark previous plans inactive
- `save_plan(session, user_id, validated_plan)` → Complete save flow

**Database Operations:**

```python
# 1. Deactivate old plans
UPDATE plans SET is_active = false WHERE user_id = ? AND is_active = true

# 2. Create new plan
INSERT INTO plans (user_id, plan_name, race_date, ...) VALUES (...)

# 3. Create workouts (batch insert)
INSERT INTO plan_workouts (plan_id, date, workout_type, ...) VALUES (...), (...), ...

# 4. Commit transaction
```

**Testing:**

- Integration tests with test database
- Test rollback on errors
- Verify old plans deactivated
- Test with various plan sizes

---

## 🔄 DATA FLOW

### **Complete Flow Example:**

```python
# Entry point: src/routes/plan_routes.py
@plan_bp.post("/api/plan/generate")
@requires_auth
def generate_training_plan():
    user_id = get_user_id_from_token()
    plan_request = request.json

    session = get_session()
    try:
        # LAYER 1: Collect Data
        raw_data = DataCollectionService.collect_all_data(
            session, user_id, plan_request
        )

        # LAYER 2: Calculate Insights
        insights = InsightsCalculationService.generate_insights(raw_data)

        # LAYER 3: Build Prompt
        prompt = PromptBuilderService.build_complete_prompt(insights)

        # LAYER 4: Generate Plan with GPT
        generated_plan = GPTCoachService.generate_plan(prompt)

        # LAYER 5: Validate Plan
        validation_result = PlanValidationService.validate_complete_plan(
            generated_plan
        )

        if not validation_result["valid"]:
            return jsonify({
                "status": "error",
                "message": "Generated plan has safety violations",
                "violations": validation_result["violations"]
            }), 400

        # LAYER 6: Save Plan
        result = PlanStorageService.save_plan(
            session, user_id, validation_result["plan"]
        )

        session.commit()

        return jsonify({
            "status": "success",
            "plan_id": result["plan_id"],
            "workouts_created": result["workouts_created"]
        }), 201

    except Exception as e:
        session.rollback()
        logger.error(f"Plan generation failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to generate plan"
        }), 500
    finally:
        session.close()
```

---

## 🧪 TESTING STRATEGY

### **Layer-by-Layer Testing Approach**

#### **Phase 1: Unit Testing Each Layer**

```python
# tests/services/training_plan/test_data_collection_service.py
def test_fetch_user_profile():
    """Test fetching user profile data"""
    # Arrange: Create mock user in test DB
    # Act: Call fetch_user_profile
    # Assert: Verify correct data returned

# tests/services/training_plan/test_insights_calculation_service.py
def test_calculate_weekly_mileage():
    """Test weekly mileage calculation"""
    # Arrange: Create mock activities
    # Act: Call calculate_weekly_mileage
    # Assert: Verify correct average calculated

# ... similar for each layer
```

#### **Phase 2: Integration Testing Between Layers**

```python
# tests/integration/test_plan_generation_flow.py
def test_complete_plan_generation():
    """Test full flow from data collection to storage"""
    # Arrange: Setup test user with activities
    # Act: Run through all 6 layers
    # Assert: Verify plan created in database
```

#### **Phase 3: End-to-End Testing**

```python
# tests/e2e/test_plan_generation_api.py
def test_generate_plan_endpoint():
    """Test API endpoint with real GPT call"""
    # Arrange: Authenticate as test user
    # Act: POST to /api/plan/generate
    # Assert: Verify 201 response and plan in DB
```

### **Test Data Fixtures**

```python
# tests/fixtures/runner_profiles.py

# Test Case 1: Ideal Runner
IDEAL_RUNNER = {
    "weeks_of_history": 12,
    "avg_weekly_mileage": 20,
    "longest_run": 10,
    "weeks_until_race": 20,
    "expected_outcome": "FEASIBLE"
}

# Test Case 2: Insufficient Time
RUSHED_RUNNER = {
    "weeks_of_history": 8,
    "avg_weekly_mileage": 15,
    "longest_run": 6,
    "weeks_until_race": 12,
    "expected_outcome": "TIME_WARNING"
}

# Test Case 3: High Injury Risk
OVERTRAINING_RUNNER = {
    "weeks_of_history": 8,
    "recent_spike": True,
    "acwr": 1.6,
    "expected_outcome": "INJURY_RISK_WARNING"
}

# ... more test cases
```

---

## 📅 IMPLEMENTATION ROADMAP

### **Week 1: Layers 1 & 2**

- ✅ Create service file structure
- ✅ Implement Layer 1 (Data Collection)
- ✅ Write Layer 1 unit tests
- ✅ Implement Layer 2 (Insights Calculation)
- ✅ Write Layer 2 unit tests
- ✅ Integration test Layers 1→2

### **Week 2: Layers 3 & 4**

- ✅ Implement Layer 3 (Prompt Builder)
- ✅ Write Layer 3 unit tests
- ✅ Implement Layer 4 (GPT Coach)
- ✅ Write Layer 4 unit tests (with mocks)
- ✅ Integration test Layers 1→2→3→4

### **Week 3: Layers 5 & 6**

- ✅ Implement Layer 5 (Plan Validation)
- ✅ Write Layer 5 unit tests
- ✅ Implement Layer 6 (Plan Storage)
- ✅ Write Layer 6 unit tests
- ✅ Integration test complete flow

### **Week 4: API & Frontend**

- ✅ Create API endpoint
- ✅ Update frontend forms
- ✅ Connect frontend to API
- ✅ End-to-end testing
- ✅ Beta user testing

---

## 📚 RESEARCH FOUNDATION

### **Key Research Sources**

1. **PMC10915606 Study:**

   - "ChatGPT-generated training plans not rated optimal by coaching experts"
   - "Plan quality improved with additional input information"
   - Conclusion: Hybrid approach with validation needed

2. **Prompt Engineering Best Practices:**

   - Clear, specific instructions improve output
   - Structured data format reduces tokens by 30-40%
   - JSON output mode ensures consistency

3. **Sports Science Standards:**

   - 10% Rule: Maximum 10% weekly mileage increase
   - ACWR: Acute:Chronic Workload Ratio for injury prediction
   - 80/20 Training: 80% easy intensity, 20% quality work
   - Tanaka Formula: Max HR = 208 - (0.7 × age)

4. **Minimum Data Requirements:**
   - 4 weeks: Minimum for baseline assessment
   - 8 weeks: Recommended for quality personalization
   - 12+ weeks: Captures trends, diminishing returns

---

## 🔧 DEVELOPMENT GUIDELINES

### **Code Standards**

1. **Naming Conventions:**

   - Services: `{Purpose}Service` (e.g., `DataCollectionService`)
   - Functions: `verb_noun` (e.g., `calculate_weekly_mileage`)
   - Variables: `descriptive_snake_case`

2. **Documentation:**

   - Docstrings for all public functions
   - Type hints for all parameters and returns
   - Inline comments for complex logic

3. **Error Handling:**

   - Specific exceptions for each error type
   - Meaningful error messages
   - Proper logging at each layer

4. **Testing:**
   - Minimum 80% code coverage
   - Test happy path and edge cases
   - Mock external dependencies (GPT API, DB)

### **File Structure**

```
src/services/training_plan/
├── __init__.py
├── data_collection_service.py
├── insights_calculation_service.py
├── prompt_builder_service.py
├── gpt_coach_service.py
├── plan_validation_service.py
└── plan_storage_service.py

tests/services/training_plan/
├── __init__.py
├── test_data_collection_service.py
├── test_insights_calculation_service.py
├── test_prompt_builder_service.py
├── test_gpt_coach_service.py
├── test_plan_validation_service.py
└── test_plan_storage_service.py

tests/integration/
└── test_plan_generation_flow.py

tests/fixtures/
├── runner_profiles.py
└── sample_plans.py
```

---

## ✅ READY FOR IMPLEMENTATION

This architecture is:

- ✅ **Research-backed:** Based on studies and best practices
- ✅ **Testable:** Each layer independently testable
- ✅ **Maintainable:** Modular design, clear responsibilities
- ✅ **Enhanceable:** Easy to add features layer-by-layer
- ✅ **Safe:** Validation ensures plan quality

**Next Step:** Begin Layer 1 implementation with `DataCollectionService`

---

**End of Architecture Document**
