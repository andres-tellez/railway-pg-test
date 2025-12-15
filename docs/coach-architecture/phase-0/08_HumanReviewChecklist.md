# Human Review Checklist

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This checklist defines what human reviewers must verify before approving coding agent PRs. It ensures code quality, architectural compliance, and safety.

## Reviewers

### Primary Reviewers

- **Engineering Lead**: Reviews all PRs for architecture compliance and code quality
- **AI/ML Architect**: Reviews LLM-specific changes (prompts, model config, context building)

### Secondary Reviewers

- **Senior Engineers**: Review for code quality and best practices
- **Product Manager**: Review for feature completeness and user experience

### Review SLA

- **Target**: 24-48 hours for initial review
- **Blockers**: Same-day review for critical issues
- **Non-blockers**: Within 48 hours

## Required Checks

### 1. Architecture Compliance

- [ ] Code follows defined architecture (builders, LLMClient, etc.)
- [ ] Components have single responsibility
- [ ] No direct LLM calls outside LLMClient
- [ ] No hardcoded prompts/config (everything in config/ or prompts/)
- [ ] Error handling uses CoachErrorHandler (not ad-hoc try/except)

### 2. Testing

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Test coverage ≥ 80% for new code
- [ ] Snapshot tests added (if applicable)
- [ ] Contract tests added (if applicable)
- [ ] Edge cases tested

### 3. Schema & Configuration

- [ ] Schema changes have version bumps
- [ ] Schema changes have updated tests
- [ ] Schema changes documented in CHANGELOG
- [ ] Config changes are in config files (not hardcoded)
- [ ] Config changes documented

### 4. Prompt Changes

- [ ] Prompt changes have version bumps
- [ ] Prompt changes have change notes
- [ ] Prompt changes reviewed by AI/ML Architect
- [ ] Prompt changes don't introduce safety risks

### 5. Error Handling & Logging

- [ ] Appropriate error handling present
- [ ] Errors are logged with context
- [ ] Error severity classified correctly
- [ ] Fallback behavior defined
- [ ] No silent failures

### 6. Documentation

- [ ] Docstrings added for public functions/classes
- [ ] Complex logic has inline comments
- [ ] Architecture docs updated (if major component)
- [ ] README updated (if setup changes)
- [ ] API docs updated (if interface changes)

### 7. Performance

- [ ] Performance impact considered
- [ ] No obvious performance regressions
- [ ] Database queries optimized (if applicable)
- [ ] Caching used appropriately (if applicable)

### 8. Security & Safety

- [ ] No security vulnerabilities introduced
- [ ] PII handling is appropriate
- [ ] SafetyScanner logic is correct (if changed)
- [ ] Medical red flags handled correctly

## Optional Checks (Nice to Have)

- [ ] Code style/readability
- [ ] Naming conventions followed
- [ ] Code reuse opportunities identified
- [ ] Future refactoring suggestions

## Review Process

### Step 1: Initial Review

Reviewer checks:
1. PR description is complete
2. All required checks pass
3. Code follows architecture
4. Tests are adequate

### Step 2: Detailed Review

Reviewer examines:
1. Code logic and correctness
2. Error handling
3. Edge cases
4. Performance implications
5. Documentation quality

### Step 3: Approval or Request Changes

**Approve if:**
- All required checks pass
- Code quality is acceptable
- No blocking concerns

**Request changes if:**
- Required checks fail
- Code quality needs improvement
- Architecture violations
- Missing tests
- Security concerns

### Step 4: Re-Review (if changes requested)

- Agent addresses feedback
- Reviewer re-checks changes
- Repeat until approved

## Review Templates

### Approval Comment

```markdown
✅ Approved

**Reviewed by:** [Name]
**Date:** [Date]

**Summary:**
- All required checks pass
- Code follows architecture
- Tests are comprehensive
- No blocking concerns

**Optional suggestions:**
- [Suggestion 1]
- [Suggestion 2]

Ready to merge.
```

### Request Changes Comment

```markdown
❌ Changes Requested

**Reviewed by:** [Name]
**Date:** [Date]

**Required Changes:**
1. [Issue 1] - [Explanation]
2. [Issue 2] - [Explanation]

**Optional Suggestions:**
- [Suggestion 1]

Please address required changes before re-requesting review.
```

### Blocking Comment

```markdown
🚫 Blocked

**Reviewed by:** [Name]
**Date:** [Date]

**Blocking Issues:**
1. [Critical issue 1] - [Explanation]
2. [Critical issue 2] - [Explanation]

**Required Actions:**
- [Action 1]
- [Action 2]

This PR cannot be merged until blocking issues are resolved.
```

## Common Issues to Watch For

### ❌ Architecture Violations

```python
# Bad: Direct LLM call
response = openai.ChatCompletion.create(...)

# Good: Use LLMClient
response = LLMClient.chat_completion(...)
```

### ❌ Hardcoded Values

```python
# Bad: Hardcoded threshold
if value > 0.5:

# Good: From config
threshold = config.get("threshold_value")
if value > threshold:
```

### ❌ Missing Error Handling

```python
# Bad: No error handling
result = risky_operation()

# Good: Error handling
try:
    result = risky_operation()
except RiskyOperationError as e:
    logger.error(f"Operation failed: {e}")
    handle_error(e)
```

### ❌ Missing Tests

```python
# Bad: No tests for new function
def new_function():
    ...

# Good: Tests added
def test_new_function():
    ...
```

### ❌ Schema Changes Without Version

```python
# Bad: Schema changed without version bump
{
    "new_field": value  # Added without version bump
}

# Good: Version bumped
{
    "version": "1.1.0",  # Version updated
    "new_field": value
}
```

## Review Decision Matrix

| Issue Type | Severity | Action |
|------------|----------|--------|
| Architecture violation | Critical | Block |
| Security vulnerability | Critical | Block |
| Missing required tests | High | Request changes |
| Hardcoded config | High | Request changes |
| Schema change without version | High | Request changes |
| Missing error handling | Medium | Request changes |
| Missing documentation | Medium | Request changes |
| Code style issues | Low | Optional suggestion |
| Performance concern | Medium | Request changes or approve with note |

## Escalation

### When to Escalate

- Security concerns
- Major architecture violations
- Disagreement on approach
- Need for additional expertise

### Escalation Process

1. Tag relevant expert (@security-team, @ai-architect)
2. Explain issue and context
3. Wait for input before proceeding

## Review Metrics

Track review metrics:

- **Average review time**: Target < 24 hours
- **Change request rate**: Monitor for patterns
- **Common issues**: Track frequent problems
- **Reviewer feedback**: Collect feedback on process

## Continuous Improvement

### Monthly Review

- Analyze common issues
- Update checklist based on patterns
- Improve review process
- Share learnings with team

## Related Documents

- `docs/coach-architecture/phase-0/CodingAgent_Execution_Guide.md` - Agent workflow
- `docs/coach-architecture/phase-0/DocumentationStandards.md` - Documentation requirements
