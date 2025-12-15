# Coach Architecture Test Suite

This directory contains all tests for the Coach architecture system.

## Test Structure

```
tests/
├── coach/
│   ├── unit/              # Unit tests (fast, isolated)
│   ├── integration/       # Integration tests (may require DB/external services)
│   ├── contract/          # Contract tests (schema validation)
│   ├── conftest.py        # Pytest fixtures
│   └── test_*.py          # Test modules
```

## Test Categories

### Unit Tests

- **Location**: `tests/coach/unit/`
- **Marker**: `@pytest.mark.unit`
- **Speed**: Fast (< 1 second each)
- **Dependencies**: None (mocked)
- **When to run**: On every commit
- **Example**: Testing schema validation, error handling

### Integration Tests

- **Location**: `tests/coach/integration/`
- **Marker**: `@pytest.mark.integration`
- **Speed**: Slower (may require DB/external services)
- **Dependencies**: Database, external APIs (mocked if possible)
- **When to run**: Before merging, in CI
- **Example**: Testing full component workflows

### Contract Tests

- **Location**: `tests/coach/contract/`
- **Marker**: `@pytest.mark.contract`
- **Purpose**: Verify data structures match schemas
- **When to run**: On schema changes, in CI
- **Example**: Verifying RunnerState matches schema

## Running Tests

### Run All Tests

```bash
pytest tests/coach/
```

### Run by Category

```bash
# Unit tests only
pytest tests/coach/unit/ -m unit

# Integration tests only
pytest tests/coach/integration/ -m integration

# Contract tests only
pytest tests/coach/contract/ -m contract
```

### Run with Coverage

```bash
pytest tests/coach/ --cov=coach --cov-report=html
```

### Run Specific Test

```bash
pytest tests/coach/test_schema_validator.py::TestSchemaValidator::test_validate_runner_state_valid
```

## Test Requirements

### Coverage

- **Minimum**: 80% overall
- **Critical components**: 90%+ (builders, LLMClient, SafetyScanner)

### Test Speed

- **Unit tests**: < 1 second each
- **Integration tests**: < 10 seconds each
- **Full test suite**: < 5 minutes

### Test Data

- Use fixtures for reusable test data
- Don't use real user data
- Use anonymized/mock data

## Test Guidelines

1. **Test-First**: Write tests before or alongside implementation
2. **Isolated**: Tests should not depend on each other
3. **Deterministic**: Same input should always produce same output
4. **Fast**: Keep tests fast for quick feedback
5. **Clear**: Test names should describe what they test

## Fixtures

Common fixtures are defined in `conftest.py`:

- `sample_runner_state`: Valid RunnerState example
- `sample_question_context`: Valid QuestionContext example
- `test_schemas_dir`: Path to schemas directory
