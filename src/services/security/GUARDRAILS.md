# Architecture Guardrails
=====================

**Purpose:** Prevent code drift, ensure centralization, and maintain architectural consistency.

**Status:** ✅ Active
**Last Updated:** December 2025

---

## Core Principles

1. **Single Source of Truth** - No duplicated logic
2. **Centralized Security** - All OpenAI calls through OpenAIService
3. **No Direct Client Calls** - Direct OpenAI client usage is forbidden
4. **Consistent Patterns** - Standardized return types and error handling

---

## Rules and Enforcement

### Rule 1: All OpenAI Calls MUST Use OpenAIService

**Rule:** No direct OpenAI client calls (`openai.` or `client.chat.completions.create()`)

**Enforcement:**
- ✅ Code Review: Reject PRs with direct OpenAI imports/calls
- ⚠️ Linting: Manual review required (no automated rule yet)
- 📚 Documentation: Architecture guide in `ARCHITECTURE.md`

**Exceptions:**
- `src/services/security/external_apis/openai_service.py` (the service itself)
- Test mocks (only in test files)

**Example Violations:**
```python
# ❌ FORBIDDEN
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)

# ❌ FORBIDDEN
import openai
response = openai.ChatCompletion.create(...)
```

**Correct Pattern:**
```python
# ✅ CORRECT
from src.services.security.external_apis.openai_service import get_openai_service

service = get_openai_service()
response = service.chat_completion(
    messages=messages,
    user_id=user_id,  # Required
    model="gpt-4o",
)
```

---

### Rule 2: Pricing MUST Come from Single Source

**Rule:** All pricing references must import from `openai_cost_tracker.MODEL_PRICING`

**Enforcement:**
- ✅ Code Review: Check for hardcoded pricing values
- ⚠️ Linting: Manual review required
- 📚 Documentation: Pricing is in `openai_cost_tracker.py` only

**Example Violations:**
```python
# ❌ FORBIDDEN
pricing = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

# ❌ FORBIDDEN
cost = (tokens / 1000) * 0.03
```

**Correct Pattern:**
```python
# ✅ CORRECT
from src.services.security.external_apis.openai_cost_tracker import (
    MODEL_PRICING,
    _calculate_cost,
)

cost = _calculate_cost(model, prompt_tokens, completion_tokens)
```

---

### Rule 3: Consistent Return Types

**Rule:** All OpenAI calls return `OpenAIResponse` dataclass (via OpenAIService)

**Enforcement:**
- ✅ Type hints required
- ✅ Async versions must match sync versions
- ⚠️ Code Review: Check return type consistency

**Example Violations:**
```python
# ❌ FORBIDDEN (inconsistent return)
def get_response():
    return response.choices[0].message.content  # Just string

# ❌ FORBIDDEN (mixing formats)
def get_response_async():
    return {"content": ..., "tokens": ...}  # Dict format
```

**Correct Pattern:**
```python
# ✅ CORRECT
def get_response(user_id: str):
    service = get_openai_service()
    response = service.chat_completion(..., user_id=user_id)
    return response  # OpenAIResponse dataclass
```

---

### Rule 4: User ID Required for All OpenAI Calls

**Rule:** All OpenAI calls MUST provide `user_id` for tracking

**Enforcement:**
- ✅ Type checking: `user_id` is required parameter
- ✅ Runtime validation: OpenAIService raises error if missing
- ⚠️ Code Review: Verify user_id is passed

**Example Violations:**
```python
# ❌ FORBIDDEN
response = service.chat_completion(
    messages=messages,
    # user_id missing!
)

# ❌ FORBIDDEN
response = get_conversation_response(messages)  # No user_id
```

**Correct Pattern:**
```python
# ✅ CORRECT
response = service.chat_completion(
    messages=messages,
    user_id=str(user_id),  # Required
    model="gpt-4o",
)
```

---

## Code Review Checklist

When reviewing PRs that touch OpenAI integration:

### Pre-Merge Checklist

- [ ] **No direct OpenAI client calls**
  - [ ] No `from openai import OpenAI`
  - [ ] No `import openai`
  - [ ] No `client.chat.completions.create()`

- [ ] **Uses OpenAIService**
  - [ ] All calls go through `get_openai_service()`
  - [ ] `user_id` parameter is provided
  - [ ] Security controls are automatic (no manual rate limiting)

- [ ] **No duplicate pricing/config**
  - [ ] No hardcoded pricing values
  - [ ] Pricing imported from `openai_cost_tracker`
  - [ ] No duplicate model configuration

- [ ] **Consistent return types**
  - [ ] Returns `OpenAIResponse` or compatible format
  - [ ] Async version matches sync version
  - [ ] Type hints are present

- [ ] **Error handling**
  - [ ] Handles `RateLimitExceededError`
  - [ ] Handles `CostLimitExceededError`
  - [ ] Error messages are user-friendly

---

## Migration Guide

When migrating existing code:

### Step 1: Identify Direct Calls

Search for:
```bash
grep -r "openai\." src/
grep -r "client.chat.completions" src/
grep -r "ChatCompletion.create" src/
```

### Step 2: Replace with OpenAIService

1. Remove direct OpenAI imports
2. Import `get_openai_service`
3. Replace API calls with `service.chat_completion()`
4. Add `user_id` parameter
5. Update return type handling

### Step 3: Remove Manual Security Logic

- Remove manual rate limiting checks (now automatic)
- Remove manual cost tracking (now automatic)
- Remove duplicate pricing calculations

### Step 4: Test

- Verify functionality unchanged
- Verify rate limiting works
- Verify cost tracking works
- Verify error handling works

---

## Linting Rules (Future)

We should add automated linting rules:

```python
# .flake8 or ruff rules
[flake8]
# Disallow direct OpenAI imports (except in service file)
per-file-ignores =
    src/services/security/external_apis/openai_service.py:F401
forbidden-imports =
    openai = Use OpenAIService instead: from src.services.security.external_apis.openai_service import get_openai_service
```

**Status:** Not yet implemented (manual review required)

---

## Architecture Documentation

- **Design:** See `src/services/security/external_apis/ARCHITECTURE.md`
- **Migration:** See `src/services/security/MIGRATION_PLAN.md`
- **Overview:** See `src/services/security/README.md`

---

## Questions?

If you're unsure whether your code follows the guardrails:

1. Check `ARCHITECTURE.md` for patterns
2. Review existing migrated code (`gpt_ops.py`, `conversation_routes.py`)
3. Ask for architecture review before implementing

---

## Violations Log

Track known violations that need to be fixed:

- None currently (all code migrated ✅)

---

## Notes

- Guardrails are enforced primarily through code review
- Automated linting rules are planned but not yet implemented
- Documentation is the primary prevention mechanism
- Architecture consistency is prioritized over speed
