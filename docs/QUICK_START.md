# Training Plan Generation - Quick Start Guide

**For Developers New to This Codebase**

---

## 🎯 What You Need to Know

We're building a **6-layer architecture** to generate personalized marathon training plans:

```
Database → Calculate Metrics → Build Prompt → GPT Generates Plan → Validate → Save
```

**Why this approach?**

- Code handles **calculations** (safety-critical math)
- GPT handles **coaching decisions** (complex reasoning)
- Result: Safe, personalized, flexible plans

---

## 📁 Where Everything Lives

```
railway-pg-test/
├── docs/
│   └── training-plan-architecture-v3.md    ← Full architecture doc (READ THIS FIRST)
│
├── src/services/training_plan/
│   ├── README.md                           ← Developer guide (READ THIS SECOND)
│   ├── data_collection_service.py          ← Layer 1 ✅ DONE
│   ├── insights_calculation_service.py     ← Layer 2 🔨 NEXT
│   ├── prompt_builder_service.py           ← Layer 3 ⏳ PENDING
│   ├── gpt_coach_service.py                ← Layer 4 ⏳ PENDING
│   ├── plan_validation_service.py          ← Layer 5 ⏳ PENDING
│   └── plan_storage_service.py             ← Layer 6 ⏳ PENDING
│
└── tests/services/training_plan/
    ├── test_data_collection_service.py     ← Tests for Layer 1 📝 TO CREATE
    └── test_insights_calculation_service.py ← Tests for Layer 2 ⏳ NEXT
```

---

## 🚀 Getting Started (5 Steps)

### **Step 1: Read the Architecture** (10 min)

```bash
# Open in your editor
code docs/training-plan-architecture-v3.md
```

Understand:

- Why 6 layers?
- What does each layer do?
- How do they work together?

---

### **Step 2: Read the Developer Guide** (5 min)

```bash
code src/services/training_plan/README.md
```

Learn:

- Code standards
- Testing strategy
- How to implement each layer

---

### **Step 3: Review Layer 1 Code** (10 min)

```bash
code src/services/training_plan/data_collection_service.py
```

This is our **reference implementation**. Notice:

- ✅ Comprehensive docstrings
- ✅ Type hints on all functions
- ✅ Clear function names
- ✅ Good example documentation

---

### **Step 4: Create Tests for Layer 1** (30-60 min)

```bash
code tests/services/training_plan/test_data_collection_service.py
```

**This is your first task!**

Write tests for:

1. `fetch_user_profile()` - Test with/without profile
2. `fetch_strava_activities()` - Test with 0, 4, 12 weeks of data
3. `collect_all_data()` - Test complete flow

See stub file for test structure guidance.

---

### **Step 5: Implement Layer 2** (2-4 hours)

```bash
code src/services/training_plan/insights_calculation_service.py
```

Implement these functions in order:

1. `_calculate_age_from_age_group()` - Helper function
2. `_calculate_bmi()` - Helper function
3. `calculate_heart_rate_zones()` - HR zones from age
4. `calculate_runner_identity()` - Demographics
5. `calculate_current_fitness()` - Activity analysis (most complex)
6. `assess_safety()` - Risk assessment
7. `generate_insights()` - Orchestrate all above

---

## 🧪 Testing Guidelines

### **Run Tests**

```bash
# Activate virtual environment
source venv/bin/activate  # or .\venv\Scripts\activate on Windows

# Run specific test file
pytest tests/services/training_plan/test_data_collection_service.py -v

# Run with coverage
pytest tests/services/training_plan/ --cov=src/services/training_plan --cov-report=html
```

### **Test Structure**

```python
def test_function_name_scenario():
    """
    Test description.

    Given: Setup conditions
    When: Action performed
    Then: Expected result
    """
    # Arrange: Set up test data
    test_data = {...}

    # Act: Call the function
    result = MyService.my_function(test_data)

    # Assert: Verify results
    assert result["field"] == expected_value
```

---

## 📊 Key Calculations Reference

### **Heart Rate Zones (Tanaka Formula)**

```python
max_hr = 208 - (0.7 * age)

zone_1 = (max_hr * 0.50, max_hr * 0.60)  # Recovery
zone_2 = (max_hr * 0.60, max_hr * 0.70)  # Aerobic
zone_3 = (max_hr * 0.70, max_hr * 0.80)  # Tempo
zone_4 = (max_hr * 0.80, max_hr * 0.90)  # Threshold
zone_5 = (max_hr * 0.90, max_hr * 1.00)  # VO2 Max
```

### **Weekly Mileage (4-week average)**

```python
recent_4_weeks = get_last_n_weeks(activities, 4)
total_mileage = sum(week.total_distance for week in recent_4_weeks)
avg_weekly_mileage = total_mileage / 4
```

### **ACWR (Injury Risk)**

```python
acute_load = last_week_mileage
chronic_load = avg_of_last_4_weeks
acwr = acute_load / chronic_load

# Interpretation:
# 0.8-1.3: Optimal (LOW risk)
# 1.3-1.5: Caution (MODERATE risk)
# >1.5: High risk (HIGH risk)
```

### **Pace Conversion (m/s → min/mile)**

```python
meters_per_mile = 1609.34
seconds_per_mile = meters_per_mile / meters_per_second
minutes = int(seconds_per_mile // 60)
seconds = int(seconds_per_mile % 60)
pace = f"{minutes}:{seconds:02d}"  # e.g., "10:30"
```

---

## 🎯 Current Focus: Week 1

**Goal:** Complete Layers 1 & 2 with comprehensive tests

### **Monday-Tuesday: Layer 1 Testing**

- [ ] Create test fixtures (sample users, activities)
- [ ] Write tests for `fetch_user_profile()`
- [ ] Write tests for `fetch_strava_activities()`
- [ ] Write tests for `collect_all_data()`
- [ ] All Layer 1 tests passing ✅

### **Wednesday-Friday: Layer 2 Implementation**

- [ ] Implement helper functions first
- [ ] Implement `calculate_heart_rate_zones()`
- [ ] Implement `calculate_runner_identity()`
- [ ] Implement `calculate_current_fitness()` (biggest task)
- [ ] Implement `assess_safety()`
- [ ] Implement `generate_insights()` orchestration

### **Friday-Weekend: Layer 2 Testing**

- [ ] Write tests for each calculation function
- [ ] Test edge cases (0 activities, extreme values, etc.)
- [ ] Integration test: Layer 1 → Layer 2
- [ ] All tests passing ✅

---

## ❓ Common Questions

### **Q: Where do I find existing database models?**

A: Look in `src/db/models/`:

- `user_profile.py` - User profile model
- `activities.py` - Activity model
- `plans.py` - Plan model
- `plan_workouts.py` - PlanWorkout model

### **Q: How do I query the database in tests?**

A: Use SQLAlchemy session fixtures. See existing test files in `tests/` directory for examples.

### **Q: What if I don't have enough activity data?**

A: Layer 2 should assess data quality and return a status:

- `INSUFFICIENT`: < 4 weeks → Use template plan
- `MINIMAL`: 4-7 weeks → Basic personalization
- `GOOD`: 8-11 weeks → Full personalization
- `EXCELLENT`: 12+ weeks → Highly personalized

### **Q: Should I use UTC or local time for dates?**

A: Use UTC internally, convert to local time only for display. Activity `start_date` is already in UTC.

---

## 🆘 Need Help?

1. **Check Architecture Doc:** `docs/training-plan-architecture-v3.md`
2. **Check Developer README:** `src/services/training_plan/README.md`
3. **Look at Layer 1:** `data_collection_service.py` as reference
4. **Check Existing Tests:** Look in `tests/` for patterns

---

## ✅ Ready to Code?

**Your immediate tasks:**

1. ✅ Read this quick start (you're doing it!)
2. 📖 Read architecture doc
3. 📖 Read developer README
4. 👀 Review Layer 1 code
5. 🧪 **Create tests for Layer 1** ← START HERE

**Let's build this layer by layer!** 🚀
