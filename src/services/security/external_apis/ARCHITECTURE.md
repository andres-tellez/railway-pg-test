# OpenAI Service Architecture
=====================

**Purpose:** Centralized, consistent OpenAI API integration with automatic security controls.

**Status:** 🏗️ Design Phase
**Last Updated:** December 2025

---

## Core Principles

1. **Single Source of Truth**
   - All OpenAI pricing comes from one place
   - All OpenAI calls go through one service
   - All token usage follows one extraction pattern

2. **Automatic Security Controls**
   - Rate limiting applied automatically
   - Cost tracking applied automatically
   - No manual integration required

3. **Consistent Patterns**
   - Standardized return types
   - Standardized error handling
   - Standardized token extraction

4. **No Code Drift**
   - All new OpenAI code uses this service
   - Direct OpenAI client calls are forbidden
   - Architecture enforced via linting/review

---

## Architecture Design

### Unified OpenAI Service

```
OpenAIService
├── Pricing (from cost_tracker)
├── Rate Limiting (automatic)
├── Cost Tracking (automatic)
├── Token Extraction (standardized)
└── Error Handling (consistent)
```

### Service Interface

```python
class OpenAIService:
    """
    Unified service for all OpenAI API interactions.

    Automatically handles:
    - Rate limiting
    - Cost tracking
    - Token extraction
    - Error handling
    """

    def chat_completion(
        self,
        messages: List[Dict],
        model: str = "gpt-4o",
        user_id: str,  # Required for rate limiting + cost tracking
        **kwargs  # temperature, max_tokens, etc.
    ) -> OpenAIResponse:
        """
        Make OpenAI chat completion call with automatic security controls.

        Returns:
            OpenAIResponse with:
            - content: str
            - usage: Dict (tokens)
            - cost: float
            - model: str
        """
        pass
```

### Response Type

```python
@dataclass
class OpenAIResponse:
    """Standardized OpenAI API response"""
    content: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    cost: float
    model: str
    request_id: Optional[str] = None
```

---

## Migration Strategy

### Phase 1: Create Service ✅
- [x] Define interface
- [ ] Implement OpenAIService class
- [ ] Add automatic rate limiting integration
- [ ] Add automatic cost tracking integration

### Phase 2: Migrate Existing Code
- [ ] Update `gpt_ops.py` → use OpenAIService
- [ ] Update `openai_adapter.py` → use OpenAIService
- [ ] Fix async version consistency
- [ ] Remove duplicate pricing/config

### Phase 3: Enforce Architecture
- [ ] Add linting rules (prevent direct OpenAI calls)
- [ ] Update code review checklist
- [ ] Add architecture documentation to README

---

## Usage Pattern

### Before (Inconsistent, Duplicated)

```python
# Direct OpenAI call - no rate limiting, no cost tracking
response = client.chat.completions.create(...)
content = response.choices[0].message.content

# Manual token extraction
usage = response.usage
tokens = usage.prompt_tokens + usage.completion_tokens

# Manual cost calculation (duplicated logic)
cost = calculate_cost(...)
```

### After (Centralized, Automatic)

```python
from src.services.security.external_apis.openai_service import OpenAIService

service = OpenAIService()
response = service.chat_completion(
    messages=messages,
    model="gpt-4o",
    user_id=str(user_id),  # Required
    temperature=0.7,
    max_tokens=800,
)

# All security controls applied automatically
# Rate limiting checked
# Cost tracked
# Tokens extracted
# Consistent response format

content = response.content
cost = response.cost
tokens = response.usage["total_tokens"]
```

---

## Integration Points

### Automatic Rate Limiting

```python
# Inside OpenAIService.chat_completion()
allowed, retry_after = can_make_request(user_id)
if not allowed:
    raise RateLimitExceededError(retry_after)
```

### Automatic Cost Tracking

```python
# After successful API call
cost = record_request_cost(
    user_id=user_id,
    model=model,
    prompt_tokens=usage.prompt_tokens,
    completion_tokens=usage.completion_tokens,
)
```

### Cost Limit Checking

```python
# Before API call
cost_allowed, error, exceeded_by = check_cost_limits(user_id)
if not cost_allowed:
    raise CostLimitExceededError(error, exceeded_by)
```

---

## Guardrails

### 1. No Direct OpenAI Client Calls

**Rule:** All OpenAI API calls MUST go through `OpenAIService`

**Enforcement:**
- Code review: Reject PRs with direct `openai.` or `client.chat.completions.create()` calls
- Linting: Add rule to flag direct OpenAI imports/calls
- Documentation: Clear "how to use OpenAI" guide

### 2. Single Pricing Source

**Rule:** Pricing MUST come from `openai_cost_tracker.MODEL_PRICING`

**Enforcement:**
- All pricing references must import from cost_tracker
- No hardcoded pricing values
- Pricing updates only in one place

### 3. Consistent Return Types

**Rule:** All OpenAI calls return `OpenAIResponse` dataclass

**Enforcement:**
- Type hints required
- Async versions must match sync versions
- No mixing of return types

### 4. User ID Required

**Rule:** All OpenAI calls MUST provide `user_id` for tracking

**Enforcement:**
- Type checking: `user_id` is required parameter
- Runtime validation: Raise error if missing
- No anonymous calls allowed

---

## Migration Checklist

For each file that calls OpenAI directly:

- [ ] Import OpenAIService
- [ ] Replace direct client calls with service.chat_completion()
- [ ] Remove duplicate pricing/config
- [ ] Update return type handling
- [ ] Add user_id parameter
- [ ] Remove manual rate limiting (now automatic)
- [ ] Remove manual cost tracking (now automatic)
- [ ] Test functionality unchanged
- [ ] Verify cost tracking works
- [ ] Verify rate limiting works

---

## Files to Migrate

1. `src/utils/gpt_ops.py`
   - `get_conversation_response()` → use OpenAIService
   - `get_conversation_response_async()` → use OpenAIService
   - `get_gpt_response()` → use OpenAIService (if still needed)

2. `src/services/training_plan/llm_adapters/openai_adapter.py`
   - `completion()` → use OpenAIService

3. `src/utils/smart_model_selector.py`
   - Already fixed to use cost_tracker pricing ✅

---

## Future Enhancements

- Circuit breaker pattern (fail fast on repeated errors)
- Retry logic with exponential backoff
- Request/response logging
- Performance metrics
- A/B testing different models
- Cost optimization suggestions

---

## Notes

- This service sits in the new security architecture (`external_apis/`)
- It consolidates existing patterns but doesn't break existing code
- Migration is incremental and backward-compatible
- Old code continues to work during migration
