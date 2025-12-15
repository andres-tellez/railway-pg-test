# Testing Strategy: When to Test Along the Way

**Version:** 1.0
**Last Updated:** 2025-01-15

## Overview

This document provides a practical guide for when and how to test during Coach architecture implementation, ensuring quality is built in from the start.

## Core Testing Principles

1. **Test-First When Possible**: Write tests before or alongside implementation
2. **Test Continuously**: Run tests frequently during development
3. **Test at Multiple Levels**: Unit → Integration → End-to-End
4. **Fail Fast**: Catch issues early
5. **Keep Tests Maintainable**: Clean, readable, focused tests

## Testing Timeline by Phase

### Phase 0: Foundations ✅ COMPLETE

**What Was Tested:**
- ✅ Schema validation utilities (`test_schema_validator.py`)
- ✅ Error handling utilities (`test_error_handler.py`)
- ✅ Configuration loading (`test_config.py`)

**Status**: Foundation utilities are tested and working.

### Phase 1: Core Infrastructure (Current)

**Testing Strategy: Component-by-Component**

For each component, follow this cycle:

#### 1. IntentClassifier

**Testing Approach:**
1. **Write test stubs first** - Define expected behavior
2. **Implement minimum to pass** - Get tests green
3. **Refactor and expand** - Add edge cases, improve implementation
4. **Integration test** - Test with other components

**Test File**: `tests/coach/unit/test_intent_classifier.py`

**Test Cases Needed:**
```python
def test_classify_workout_review():
    """Test classifying workout review questions"""
    # "How did my long run go?" → workout_review

def test_classify_this_week_plan():
    """Test classifying plan questions"""
    # "What's my plan this week?" → this_week_plan

def test_classify_vague_question():
    """Test low confidence for vague questions"""
    # "How am I doing?" → low confidence

def test_classify_injury_question():
    """Test injury detection"""
    # "I have chest pain" → injury_or_symptom
```

**When to Test:**
- ✅ Write tests FIRST
- ✅ Run tests after each implementation step
- ✅ Add edge cases as you discover them
- ✅ Integration test after all intents defined

**Acceptance Criteria:**
- [ ] All intent types classified correctly
- [ ] Confidence scores reasonable
- [ ] Vague questions get low confidence
- [ ] Tests pass with >80% coverage

#### 2. SafetyScanner

**Testing Approach:**
- **CRITICAL**: Must have comprehensive tests before any deployment
- **Test-first mandatory** - Safety cannot be compromised

**Test File**: `tests/coach/unit/test_safety_scanner.py`

**Test Cases Needed:**
```python
def test_detect_critical_flags():
    """Test all critical medical flags"""
    # "chest pain", "blacked out", etc.

def test_no_false_positives():
    """Test normal phrases don't trigger"""
    # "I felt great" → no flags

def test_case_insensitivity():
    """Test flags detected regardless of case"""

def test_multiple_flags():
    """Test multiple flags in one message"""
```

**When to Test:**
- ✅ Write tests FIRST (before any implementation)
- ✅ Run tests after each flag added
- ✅ Manual review of test cases
- ✅ Integration test with real anonymized messages

**Acceptance Criteria:**
- [ ] 100% of critical flags detected
- [ ] < 1% false positive rate
- [ ] Case insensitive
- [ ] Performance < 50ms

#### 3. ActivitySummarizer

**Testing Approach:**
- Test summarization logic with various input sizes
- Snapshot tests for output structure

**Test File**: `tests/coach/unit/test_activity_summarizer.py`

**Test Cases Needed:**
```python
def test_summarize_last_3_long_runs():
    """Test last 3 long runs are fully detailed"""

def test_summarize_last_7_days():
    """Test last 7 days are summarized"""

def test_summarize_older_activities():
    """Test older activities are weekly aggregates"""

def test_empty_activities():
    """Test handling empty activity list"""

def test_single_activity():
    """Test handling single activity"""
```

**When to Test:**
- ✅ Write tests FIRST
- ✅ Snapshot test for output structure
- ✅ Test edge cases (empty, single, many)
- ✅ Integration test with real activity data

#### 4. RunnerStateBuilder (Submodules)

**Testing Approach:**
- Test each submodule independently FIRST
- Then integration test the orchestrator

**Testing Order:**
1. **RaceInfoBuilder** → Test → Implement
2. **ZoneCalculator** → Test → Implement
3. **WeeklyMetricsBuilder** → Test → Implement
4. **PatternAnalyzer** → Test → Implement
5. **RunnerStateBuilder** (orchestrator) → Integration tests

**Test Files:**
- `tests/coach/unit/test_race_info_builder.py`
- `tests/coach/unit/test_zone_calculator.py`
- `tests/coach/unit/test_weekly_metrics_builder.py`
- `tests/coach/unit/test_pattern_analyzer.py`
- `tests/coach/integration/test_runner_state_builder.py`

**Snapshot Test Example:**
```python
def test_runner_state_snapshot(sample_user_data):
    """Snapshot test for RunnerState output"""
    builder = RunnerStateBuilder()
    result = builder.build(sample_user_data)

    # Verify matches schema
    SchemaValidator.validate_runner_state(result)

    # Snapshot test
    assert_matches_snapshot(result, "runner_state_output_v1_0.json")
```

**When to Test:**
- ✅ Test each submodule BEFORE integration
- ✅ Snapshot test after each submodule
- ✅ Integration test after all submodules complete
- ✅ Contract test (schema validation) always

#### 5. ContextCompressor

**Testing Approach:**
- Test compression priority logic
- Test edge cases (already small, extremely large)

**Test File**: `tests/coach/unit/test_context_compressor.py`

**Test Cases Needed:**
```python
def test_compress_priority_order():
    """Test critical data preserved"""
    # Race context, zones, current week metrics kept

def test_no_compression_needed():
    """Test when context is already small"""

def test_extreme_compression():
    """Test when context is very large"""

def test_compression_preserves_critical():
    """Test critical fields always preserved"""
```

**When to Test:**
- ✅ Write tests FIRST
- ✅ Test priority logic thoroughly
- ✅ Performance test (compression should be fast)

#### 6. LLMClient

**Testing Approach:**
- **Use mocks** - Never call real OpenAI API in tests
- Test error handling, retries, timeouts

**Test File**: `tests/coach/unit/test_llm_client.py`

**Test Cases Needed:**
```python
@mock.patch('openai.ChatCompletion.create')
def test_chat_completion_success(mock_openai):
    """Test successful LLM call"""

def test_chat_completion_timeout():
    """Test timeout handling"""

def test_chat_completion_retry():
    """Test retry logic"""

def test_cost_tracking():
    """Test cost is calculated and logged"""
```

**When to Test:**
- ✅ Write tests FIRST with mocks
- ✅ Test all error paths
- ✅ Test retry logic
- ✅ Test cost calculation

**Important**: Use mocks - don't call real API in tests!

#### 7. CoachPromptBuilder

**Testing Approach:**
- Snapshot tests for prompt structure
- Contract tests for message format

**Test File**: `tests/coach/unit/test_prompt_builder.py`

**Test Cases Needed:**
```python
def test_build_system_prompt():
    """Test system prompt includes all sections"""

def test_inject_runner_state():
    """Test runner state injected correctly"""

def test_inject_question_context():
    """Test question context injected correctly"""

def test_prompt_versioning():
    """Test prompt version included"""
```

**When to Test:**
- ✅ Write tests FIRST
- ✅ Snapshot test prompt structure
- ✅ Test version handling

#### 8. ResponseFormatter

**Testing Approach:**
- Test section extraction
- Test fallback logic

**Test File**: `tests/coach/unit/test_response_formatter.py`

**Test Cases Needed:**
```python
def test_extract_sections():
    """Test all sections extracted"""

def test_missing_sections():
    """Test handling missing sections"""

def test_fallback_message():
    """Test fallback when parsing fails"""
```

**When to Test:**
- ✅ Write tests FIRST
- ✅ Test edge cases (malformed responses)
- ✅ Test fallback logic

### Phase 2: Coach v1 Integration

**End-to-End Testing:**

**Test File**: `tests/coach/integration/test_full_pipeline.py`

**When to Test:**
- ✅ After all Phase 1 components complete
- ✅ Before enabling shadow mode
- ✅ After each prompt version change

**Test Cases:**
```python
def test_workout_review_pipeline():
    """Test full pipeline for workout review"""
    # User question → RunnerState → QuestionContext → LLM → Response

def test_injury_question_safety():
    """Test safety flags trigger correctly"""
    # "I have chest pain" → SafetyScanner → Safe response

def test_golden_conversations():
    """Test against known good responses"""
    # Compare output to expected responses
```

### Phase 3: Coach v1.5 Advanced Features

**Proactive Insights Testing:**
- Test pattern detection
- Test insight generation
- Test context injection

**A/B Testing:**
- Test routing logic
- Test metrics separation

## Test Execution Checklist

### Before Starting a Component

- [ ] Read architecture spec
- [ ] Understand component interface
- [ ] Identify dependencies
- [ ] Write test stubs with expected behavior

### During Implementation

- [ ] Run tests after each change
- [ ] Make tests pass one by one
- [ ] Add edge cases as discovered
- [ ] Refactor if tests reveal issues

### After Component Complete

- [ ] All tests pass
- [ ] Coverage ≥ 80%
- [ ] Integration tests pass
- [ ] Contract tests pass (if applicable)
- [ ] Code reviewed
- [ ] Documentation updated

### Before Moving to Next Component

- [ ] All acceptance criteria met
- [ ] No flaky tests
- [ ] Performance acceptable
- [ ] Ready for integration

## Continuous Testing

### During Development

```bash
# Run tests for component you're working on
pytest tests/coach/unit/test_intent_classifier.py -v

# Run with watch mode (if available)
pytest-watch tests/coach/unit/test_intent_classifier.py
```

### Before Commit

```bash
# Run all unit tests
pytest tests/coach/unit/ -v

# Run with coverage
pytest tests/coach/unit/ --cov=coach --cov-report=term
```

### In CI

```bash
# Full test suite
pytest tests/coach/ -v --cov=coach --cov-fail-under=80

# Contract tests
pytest tests/coach/contract/ -m contract

# Integration tests
pytest tests/coach/integration/ -m integration
```

## Test Quality Guidelines

### Good Tests

✅ **Fast**: Run in < 1 second
✅ **Isolated**: Don't depend on other tests
✅ **Deterministic**: Same input = same output
✅ **Clear**: Test name explains what it tests
✅ **Focused**: Test one thing

### Bad Tests

❌ **Slow**: Require external services
❌ **Flaky**: Sometimes pass, sometimes fail
❌ **Vague**: Unclear what they test
❌ **Complex**: Hard to understand
❌ **Brittle**: Break on minor changes

## Test Maintenance

### When Tests Fail

1. **Don't ignore** - Fix immediately
2. **Understand why** - Was it a bug or test issue?
3. **Fix properly** - Don't make tests pass by lowering standards
4. **Learn** - What can we improve?

### When to Update Tests

- **New feature**: Add tests
- **Bug fix**: Add regression test
- **Refactor**: Update tests to match new structure
- **Behavior change**: Update expectations

### When to Delete Tests

- **Feature removed**: Delete related tests
- **Redundant**: Consolidate duplicate tests
- **Flaky**: Fix or delete (prefer fixing)

## Example: Complete Testing Cycle

### Component: IntentClassifier

**Step 1: Write Test Stubs**
```python
# tests/coach/unit/test_intent_classifier.py
def test_classify_workout_review():
    classifier = IntentClassifier()
    result = classifier.classify("How did my long run go?")
    assert result["intent"] == "workout_review"
    assert result["confidence"] > 0.7
```

**Step 2: Run Test (Fail)**
```bash
pytest tests/coach/unit/test_intent_classifier.py::test_classify_workout_review -v
# Expected: ImportError or test failure
```

**Step 3: Implement Minimum**
```python
# coach/utils/intent_classifier.py
class IntentClassifier:
    def classify(self, message: str) -> dict:
        if "long run" in message.lower() or "workout" in message.lower():
            return {"intent": "workout_review", "confidence": 0.9}
        return {"intent": "general_education", "confidence": 0.5}
```

**Step 4: Test Passes**
```bash
pytest tests/coach/unit/test_intent_classifier.py::test_classify_workout_review -v
# ✅ PASSED
```

**Step 5: Add More Tests**
```python
def test_classify_this_week_plan():
    classifier = IntentClassifier()
    result = classifier.classify("What's my plan this week?")
    assert result["intent"] == "this_week_plan"
```

**Step 6: Expand Implementation**
```python
# Add more classification logic
def classify(self, message: str) -> dict:
    message_lower = message.lower()

    if any(phrase in message_lower for phrase in ["long run", "workout", "run"]):
        return {"intent": "workout_review", "confidence": 0.9}
    elif "plan" in message_lower and "week" in message_lower:
        return {"intent": "this_week_plan", "confidence": 0.85}
    # ... etc
```

**Step 7: Edge Cases**
```python
def test_classify_vague_question():
    classifier = IntentClassifier()
    result = classifier.classify("How am I doing?")
    assert result["confidence"] < 0.7  # Low confidence for vague
```

**Step 8: Integration Test**
```python
def test_classifier_with_question_context_builder():
    classifier = IntentClassifier()
    context_builder = QuestionContextBuilder()

    intent = classifier.classify("How did my run go?")
    context = context_builder.build(intent, ...)

    assert context["intent"] == intent["intent"]
```

**Step 9: Done!**
- ✅ All tests pass
- ✅ Coverage ≥ 80%
- ✅ Ready for next component

## Key Takeaways

1. **Test as you go** - Don't accumulate untested code
2. **Start simple** - Get basic tests passing, then expand
3. **Run frequently** - Get fast feedback
4. **Fix immediately** - Don't let failures accumulate
5. **Keep tests clean** - Maintainable tests are valuable

## Related Documents

- `docs/coach-architecture/IMPLEMENTATION_ROADMAP.md` - Full implementation plan
- `tests/README.md` - Test structure and organization
