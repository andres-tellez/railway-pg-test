# Coach Architecture Implementation Roadmap

**Version:** 1.0
**Last Updated:** 2025-01-15

## Testing Strategy: When to Test Along the Way

This document outlines when and how to test during implementation, ensuring quality at every stage.

## Testing Philosophy

**Test-First Approach**: Write tests alongside or before implementation code. This ensures:
- Requirements are clear
- Code is testable
- Regressions are caught early
- Refactoring is safe

## Testing Timeline

### Phase 0: Foundations (Weeks 0-2)

**What to Test:**
- ✅ Schema validation utilities (COMPLETE)
- ✅ Error handling utilities (COMPLETE)
- ✅ Configuration loading
- ✅ JSON schema files themselves

**Test Types:**
- **Unit tests**: Test utility functions in isolation
- **Contract tests**: Verify schemas are valid JSON Schema

**Status**: ✅ Foundation utilities have tests

### Phase 1: Core Infrastructure (Weeks 2-6)

**Component-by-Component Testing Approach:**

#### 1. IntentClassifier
**When**: Write tests FIRST, then implement
**Test Types**:
- Unit tests: Test classification logic
- Edge cases: Vague questions, ambiguous intents
- Confidence scoring

**Example**:
```python
# tests/coach/unit/test_intent_classifier.py
def test_classify_workout_review():
    classifier = IntentClassifier()
    result = classifier.classify("How did my long run go?")
    assert result["intent"] == "workout_review"
    assert result["confidence"] > 0.7
```

#### 2. SafetyScanner
**When**: Write tests FIRST, then implement
**Test Types**:
- Unit tests: Test red flag detection
- False positive tests: Normal phrases shouldn't trigger
- Pattern matching tests

**Critical**: Must pass before moving to next component

#### 3. ActivitySummarizer
**When**: Write tests FIRST, then implement
**Test Types**:
- Unit tests: Test summarization logic
- Snapshot tests: Verify output structure
- Edge cases: Empty activities, single activity

**Example**:
```python
def test_summarize_activities():
    summarizer = ActivitySummarizer()
    activities = [generate_activities(20)]
    summary = summarizer.summarize(activities)

    # Verify structure
    assert "last_3_long_runs" in summary
    assert "last_7_days_summary" in summary
    assert "weekly_aggregates" in summary

    # Snapshot test
    assert_matches_snapshot(summary, "activity_summary_snapshot.json")
```

#### 4. RunnerStateBuilder (and submodules)
**When**: Write tests for EACH submodule as you build it

**Testing Order**:
1. RaceInfoBuilder → Test → Implement
2. ZoneCalculator → Test → Implement
3. WeeklyMetricsBuilder → Test → Implement
4. PatternAnalyzer → Test → Implement
5. RunnerStateBuilder (orchestrator) → Integration tests

**Test Types**:
- Unit tests: Each submodule independently
- Snapshot tests: Verify RunnerState output structure
- Contract tests: Verify matches schema
- Integration tests: Full builder with all submodules

**Critical Checkpoint**: RunnerStateBuilder must pass all tests before moving on

#### 5. ContextCompressor
**When**: Write tests FIRST
**Test Types**:
- Unit tests: Compression logic
- Edge cases: Already small context, extremely large context
- Priority verification: Ensure critical data preserved

#### 6. LLMClient
**When**: Write tests FIRST, use mocks
**Test Types**:
- Unit tests: Mock OpenAI API responses
- Error handling: Timeouts, API errors
- Retry logic: Verify retries work
- Cost tracking: Verify costs calculated correctly

**Note**: Use mocks for OpenAI API - don't call real API in tests

#### 7. CoachPromptBuilder
**When**: Write tests FIRST
**Test Types**:
- Unit tests: Prompt assembly logic
- Snapshot tests: Verify message structure
- Contract tests: Verify prompt format

#### 8. ResponseFormatter
**When**: Write tests FIRST
**Test Types**:
- Unit tests: Section extraction
- Edge cases: Missing sections, malformed responses
- Fallback logic: Verify safe fallback works

**After Each Component:**
- ✅ All tests pass
- ✅ Coverage ≥ 80%
- ✅ Code reviewed
- ✅ Integration with previous components tested

### Phase 2: Coach v1 (Weeks 6-10)

**Integration Testing:**

#### End-to-End Tests
**When**: After all Phase 1 components complete
**Test Types**:
- Full pipeline: User question → Coach response
- Golden conversation tests: Compare against expected responses
- Performance tests: Verify latency targets met

**Example**:
```python
# tests/coach/integration/test_full_pipeline.py
def test_workout_review_pipeline(sample_runner_state, sample_question):
    # Full pipeline test
    response = coach_v2.generate_response(
        runner_state=sample_runner_state,
        question=sample_question
    )

    # Verify structure
    assert "quick_takeaway" in response
    assert "action_steps" in response

    # Verify content (not exact match, but key elements)
    assert "pace" in response.lower() or "hr" in response.lower()
```

#### Shadow Mode Tests
**When**: Before enabling shadow mode
**Test Types**:
- Routing: Verify correct users get shadow mode
- Parallel execution: Verify v1 and v2 both execute
- Error isolation: Verify v2 errors don't affect users
- Logging: Verify shadow logs are captured

### Phase 3: Coach v1.5 (Weeks 10-16)

**Advanced Testing:**

#### Proactive Insights Tests
**When**: Test detection logic before integration
**Test Types**:
- Pattern detection: Verify insights are detected correctly
- Severity classification: Verify severity levels correct
- Context injection: Verify insights appear in prompts

#### A/B Testing Infrastructure
**When**: Before enabling A/B tests
**Test Types**:
- Routing: Verify users consistently route to same variant
- Metrics: Verify metrics tracked separately
- Rollback: Verify can rollback if variant underperforms

## Testing Checklist Per Component

When implementing a new component:

- [ ] **Before Implementation**:
  - [ ] Write unit test stubs (test names, empty implementations)
  - [ ] Define expected behavior in test docstrings
  - [ ] Create test fixtures/data

- [ ] **During Implementation**:
  - [ ] Make tests pass one by one
  - [ ] Add edge case tests as you discover them
  - [ ] Refactor if tests reveal design issues

- [ ] **After Implementation**:
  - [ ] All tests pass
  - [ ] Coverage ≥ 80%
  - [ ] Integration tests with other components
  - [ ] Contract tests (if applicable)
  - [ ] Performance tests (if applicable)

- [ ] **Before Moving On**:
  - [ ] Code review
  - [ ] Tests reviewed
  - [ ] Documentation updated

## Test Execution Strategy

### Local Development
```bash
# Run tests for component you're working on
pytest tests/coach/unit/test_intent_classifier.py -v

# Run all unit tests
pytest tests/coach/unit/ -v

# Run with coverage
pytest tests/coach/unit/ --cov=coach --cov-report=html
```

### Pre-Commit
```bash
# Run fast tests only (unit tests)
pytest tests/coach/unit/ -m unit --tb=short
```

### CI Pipeline
```bash
# Run all tests
pytest tests/coach/ -v

# Run with coverage (fail if < 80%)
pytest tests/coach/ --cov=coach --cov-fail-under=80
```

### Before Merging PR
```bash
# Full test suite
pytest tests/coach/ -v

# Contract tests
pytest tests/coach/contract/ -m contract

# Integration tests (if applicable)
pytest tests/coach/integration/ -m integration
```

## Test Maintenance

### When to Update Tests

- **New feature**: Add new tests
- **Bug fix**: Add regression test
- **Refactor**: Update tests to match new structure
- **Schema change**: Update contract tests
- **Behavior change**: Update golden conversation tests

### When to Delete Tests

- **Feature removed**: Delete related tests
- **Test is redundant**: Consolidate duplicate tests
- **Test is flaky**: Fix or delete (prefer fixing)

## Test Data Management

### Fixtures
- Store reusable test data in `conftest.py`
- Use descriptive fixture names
- Keep fixtures focused (one concept per fixture)

### Test Databases
- Use test database for integration tests
- Clean up after each test
- Use transactions that rollback

### Mocking
- Mock external APIs (OpenAI, database)
- Mock expensive operations
- Keep mocks simple and focused

## Quality Gates

### Minimum Requirements
- ✅ All tests pass
- ✅ Coverage ≥ 80%
- ✅ No flaky tests
- ✅ Tests run in < 5 minutes

### Before Production
- ✅ All integration tests pass
- ✅ Performance tests meet targets
- ✅ Shadow mode validated
- ✅ Rollback procedure tested

## Example: Implementing IntentClassifier

### Step 1: Write Test First
```python
# tests/coach/unit/test_intent_classifier.py
def test_classify_workout_review():
    classifier = IntentClassifier()
    result = classifier.classify("How did my long run go?")
    assert result["intent"] == "workout_review"
    assert result["confidence"] > 0.7
```

### Step 2: Run Test (Should Fail)
```bash
pytest tests/coach/unit/test_intent_classifier.py -v
# Expected: ImportError or test failure
```

### Step 3: Implement Minimum to Pass
```python
# coach/utils/intent_classifier.py
class IntentClassifier:
    def classify(self, message: str) -> dict:
        if "long run" in message.lower():
            return {"intent": "workout_review", "confidence": 0.9}
        return {"intent": "general_education", "confidence": 0.5}
```

### Step 4: Add More Tests, Refine Implementation
```python
def test_classify_this_week_plan():
    classifier = IntentClassifier()
    result = classifier.classify("What's my plan this week?")
    assert result["intent"] == "this_week_plan"
```

### Step 5: Edge Cases
```python
def test_classify_vague_question():
    classifier = IntentClassifier()
    result = classifier.classify("How am I doing?")
    assert result["intent"] in ["progress_check", "general_education"]
    assert result["confidence"] < 0.7  # Should be low confidence
```

### Step 6: Integration Test
```python
def test_classifier_integration_with_question_context():
    classifier = IntentClassifier()
    question_context_builder = QuestionContextBuilder()

    intent = classifier.classify("How did my run go?")
    context = question_context_builder.build(intent)

    assert context["intent"] == intent["intent"]
```

## Key Principles

1. **Test as You Go**: Don't accumulate untested code
2. **Fail Fast**: Run tests frequently during development
3. **Test Behavior, Not Implementation**: Test what code does, not how
4. **Keep Tests Simple**: Each test should verify one thing
5. **Use Descriptive Names**: Test names should explain what they test
6. **Refactor Tests Too**: Keep test code clean and maintainable

## Related Documents

- `tests/README.md` - Test structure and guidelines
- `docs/coach-architecture/phase-0/03_SafetyScannerTestPlan.md` - Safety scanner testing
- `docs/coach-architecture/phase-0/04_CodingAgent_Execution_Guide.md` - Agent workflow
