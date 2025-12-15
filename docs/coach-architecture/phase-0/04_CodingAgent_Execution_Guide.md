# Coding Agent Execution Guide

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This guide defines how coding agents should interact with the Coach architecture codebase, including communication protocols, PR templates, and workflow guidelines.

## Core Principles

1. **Agent Executes, Human Designs**: Agent implements components, humans design architecture
2. **Clear Communication**: Agent must document decisions and blockers
3. **Test-First**: All code changes require tests
4. **CI Compliance**: All code must pass CI checks before review
5. **Human Approval**: All PRs require human approval

## Allowed Directories

### ✅ Coding Agent CAN Write To

```
/coach/
  /builders/
    runner_state_builder.py
    activity_summarizer.py
    question_context_builder.py
  /utils/
    context_compressor.py
    pattern_analyzer.py
  /llm/
    llm_client.py
    prompt_builder.py
  /safety/
    safety_scanner.py
/tests/coach/
  test_runner_state_builder.py
  test_activity_summarizer.py
  ...
/config/
  thresholds.yaml
  model_config.yaml
```

### ❌ Coding Agent CANNOT Write To

```
/prompts/              # Human-designed prompts only
/db/                   # Database migrations
/models/               # Database models
/services/             # Other domain services
/routes/               # API routes (unless specifically requested)
```

## PR Template

Every PR must include this template:

```markdown
## What Was Implemented

- [ ] Component: [Name]
- [ ] Files changed: [List]
- [ ] Tests added: [List]

## Changes Made

### Code Changes
- [Description of changes]

### Tests Added
- [Description of tests]

### Documentation
- [Documentation updated]

## Checklist

### Pre-Submission
- [ ] All tests pass locally
- [ ] Code follows style guide
- [ ] No hardcoded strings/config
- [ ] No direct LLM calls outside LLMClient
- [ ] Schema changes have version bumps (if applicable)
- [ ] Prompt changes have version bumps (if applicable)

### CI Checks
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Schema validation passes
- [ ] Linting passes
- [ ] No security violations

### Review Ready
- [ ] PR description complete
- [ ] Code is self-documenting
- [ ] Known limitations documented
- [ ] Performance considerations noted (if any)

## Known Limitations

[Any known limitations or future work needed]

## Performance Impact

[If applicable: latency, cost, or other performance impacts]

## Testing Notes

[How to test, edge cases covered, etc.]
```

## Status Update Protocol

### Daily Status Updates

For ongoing work, agent should post daily status:

```markdown
## Status Update - [Date]

**Completed Today:**
- [Task 1]
- [Task 2]

**In Progress:**
- [Task 3] - [Expected completion]

**Blockers:**
- [Blocker 1] - [Action needed]

**Next Steps:**
- [Next task]
```

## Blocker Protocol

### When Agent Gets Stuck

If agent encounters a blocker:

1. **Create Issue** with label `agent-blocker`
2. **Tag** relevant team member (`@eng-lead`, `@ai-architect`)
3. **Include**:
   - Summary of blocker
   - What was tried
   - Error logs (if any)
   - Recommendation (if any)

### Issue Template

```markdown
## Blocker: [Brief Description]

**Component:** [Component name]
**Status:** Blocked

### Summary
[What is blocking progress]

### What Was Tried
- [Attempt 1]
- [Attempt 2]

### Error Logs
```
[Relevant error logs]
```

### Recommendation
[Agent's recommendation, if any]

### Questions
- [Question 1]
- [Question 2]
```

## Decision Needed Protocol

### When Spec Is Ambiguous

If agent encounters ambiguous requirement:

1. **Create Issue** with label `decision-needed`
2. **Tag** relevant team member
3. **Provide**:
   - Context
   - Options considered
   - Recommendation with reasoning

### Issue Template

```markdown
## Decision Needed: [Brief Description]

**Component:** [Component name]
**Priority:** [High/Medium/Low]

### Context
[Background on why decision is needed]

### Options Considered

#### Option 1: [Name]
- Pros: [List]
- Cons: [List]
- Implementation effort: [Estimate]

#### Option 2: [Name]
- Pros: [List]
- Cons: [List]
- Implementation effort: [Estimate]

### Recommendation
[Option X] because [reasoning]

### Questions
- [Question 1]
- [Question 2]
```

## Component Implementation Workflow

### Step 1: Understand Requirements

Agent must:
- Read architecture spec
- Understand component interface
- Identify dependencies
- Confirm schema requirements

### Step 2: Write Tests First

Agent must:
- Write unit tests (empty/failing initially)
- Write snapshot tests (if applicable)
- Write contract tests (if applicable)

### Step 3: Implement Component

Agent must:
- Follow interface specification
- Use existing utilities/services
- Add error handling
- Add logging
- Add docstrings

### Step 4: Make Tests Pass

Agent must:
- Run tests locally
- Fix failures
- Achieve >80% coverage
- Verify edge cases

### Step 5: Code Review Preparation

Agent must:
- Run linting
- Format code
- Update documentation
- Fill PR template
- Self-review for common issues

### Step 6: Submit PR

Agent must:
- Create PR with template
- Tag reviewers
- Ensure CI passes
- Wait for human approval

## Common Patterns

### Pattern 1: Adding a New Builder

```python
# 1. Create builder file
# coach/builders/new_builder.py

class NewBuilder:
    """Docstring explaining purpose"""

    def build(self, input_data: dict) -> dict:
        """
        Build output according to schema.

        Args:
            input_data: Input data dict

        Returns:
            Output dict matching schema

        Raises:
            ValueError: If input is invalid
        """
        # Implementation
        pass

# 2. Create tests
# tests/coach/test_new_builder.py

def test_new_builder_basic():
    """Test basic functionality"""
    builder = NewBuilder()
    result = builder.build(test_input)
    assert validate_schema(result)

# 3. Add to __init__.py
# coach/builders/__init__.py
from .new_builder import NewBuilder
```

### Pattern 2: Adding Configuration

```python
# config/thresholds.yaml

new_feature:
  threshold_value: 0.5
  enabled: true

# In code
from config import load_thresholds

thresholds = load_thresholds()
value = thresholds["new_feature"]["threshold_value"]
```

### Pattern 3: Error Handling

```python
from coach.utils.error_handler import CoachErrorHandler

try:
    result = build_runner_state(user_id)
except RunnerStateBuilderError as e:
    CoachErrorHandler.handle(
        error=e,
        severity="HIGH",
        component="RunnerStateBuilder",
        user_id=user_id
    )
    # Return fallback
    return get_minimal_runner_state(user_id)
```

## Code Style Guidelines

### Python Style

- Follow PEP 8
- Use type hints
- Max line length: 100 characters
- Use descriptive variable names

### Docstrings

```python
def function_name(param1: str, param2: int) -> dict:
    """
    Brief description.

    Longer description if needed.

    Args:
        param1: Description
        param2: Description

    Returns:
        Description of return value

    Raises:
        ValueError: When this happens
    """
    pass
```

### Error Messages

```python
# Good
raise ValueError(f"Invalid user_id format: {user_id}")

# Bad
raise ValueError("Invalid input")
```

## Testing Requirements

### Unit Tests

- One test file per component
- Test happy path
- Test edge cases
- Test error conditions
- Mock external dependencies

### Snapshot Tests

```python
def test_runner_state_snapshot(user_id):
    """Snapshot test for RunnerState output"""
    builder = RunnerStateBuilder()
    result = builder.build(user_id)
    assert_matches_snapshot(result, "runner_state_output.json")
```

### Contract Tests

```python
def test_llm_payload_contract():
    """Verify LLM payload matches expected schema"""
    prompt_builder = CoachPromptBuilder()
    payload = prompt_builder.build(runner_state, question_context)

    assert validate_schema(payload, "llm_payload_schema.json")
```

## CI Compliance

### Required Checks

All PRs must pass:

- [ ] Unit tests (`pytest tests/coach/`)
- [ ] Integration tests (`pytest tests/integration/`)
- [ ] Linting (`flake8`, `black`, `mypy`)
- [ ] Schema validation (`validate_schemas.py`)
- [ ] No direct LLM calls (`grep -r "openai.ChatCompletion"`)

### CI Configuration

Agent should NOT modify CI config without approval.

## Documentation Requirements

### When Adding Component

Agent must update:

- [ ] Component docstring
- [ ] Architecture diagram (if major component)
- [ ] README.md (if setup changes)
- [ ] API.md (if interface changes)

### Documentation Standards

See `docs/coach-architecture/phase-0/DocumentationStandards.md`

## Common Mistakes to Avoid

### ❌ Don't Do This

```python
# Hardcoded config
if value > 0.5:  # Bad: magic number

# Direct LLM call
response = openai.ChatCompletion.create(...)  # Bad: bypass LLMClient

# No error handling
result = risky_operation()  # Bad: no try/except

# No logging
process_data()  # Bad: no logging
```

### ✅ Do This Instead

```python
# Use config
threshold = config.get("threshold_value")
if value > threshold:  # Good: config-driven

# Use LLMClient
response = LLMClient.complete(...)  # Good: centralized

# Error handling
try:
    result = risky_operation()
except RiskyOperationError as e:
    logger.error(f"Operation failed: {e}")
    handle_error(e)  # Good: explicit handling

# Logging
logger.info("Processing data", extra={"user_id": user_id})  # Good: logged
```

## Approval Process

### PR Review Checklist

Human reviewer checks:

- [ ] Code follows architecture
- [ ] Tests are comprehensive
- [ ] No hardcoded values
- [ ] Error handling is appropriate
- [ ] Logging is present
- [ ] Documentation is updated
- [ ] Performance is acceptable

### Merge Criteria

PR can be merged when:

- [ ] All checks pass
- [ ] At least 1 reviewer approves
- [ ] No blocking comments
- [ ] Feature flag is set (if applicable)

## Communication Guidelines

### Frequency

- Daily status updates for ongoing work
- Immediate notification for blockers
- Summary at component completion

### Tone

- Professional and clear
- Acknowledge limitations
- Request help when needed
- Document decisions made

## Related Documents

- `docs/coach-architecture/phase-0/HumanReviewChecklist.md` - Review criteria
- `docs/coach-architecture/phase-0/DocumentationStandards.md` - Documentation requirements
