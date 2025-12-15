# Schema Evolution Strategy

**Version:** 1.0
**Owner:** Architecture Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This document defines the strategy for evolving RunnerState and QuestionContext schemas over time while maintaining backward compatibility and system stability.

## Core Principles

1. **Versioned Schemas**: All structured data includes explicit version fields
2. **Backward Compatibility**: Newer readers must handle older schema versions
3. **Forward Compatibility**: Older readers ignore unknown fields
4. **Cache Invalidation**: Schema changes trigger cache invalidation
5. **Gradual Migration**: No bulk data migration for minor version changes

## Schema Versioning

### Version Format

Schemas use semantic versioning (major.minor.patch):
- **Major** (v1 → v2): Breaking changes requiring migration
- **Minor** (v1.0 → v1.1): Additive changes, backward compatible
- **Patch** (v1.0.0 → v1.0.1): Bug fixes, fully compatible

### Version Fields

All schema objects must include a `version` field:

```json
{
  "version": "1.0.0",
  "runner_state": { ... }
}
```

```json
{
  "version": "1.0.0",
  "question_context": { ... }
}
```

## Backward Compatibility Rules

### v1.1 Readers Reading v1.0 Data

When a v1.1 reader encounters v1.0 data:

1. **New Fields**: Treat missing fields as `null` or use default values
2. **Type Changes**: If field type changed, use safe type coercion or default
3. **Removed Fields**: If field was removed in v1.1, ignore it (won't exist)

Example:
```python
# v1.0 schema has no "fatigue_indicators" field
# v1.1 reader should default to empty list:
fatigue_indicators = data.get("fatigue_indicators", [])
```

### v1.0 Readers Reading v1.1 Data

When a v1.0 reader encounters v1.1 data:

1. **Unknown Fields**: Ignore extra fields (JSON parsing allows this)
2. **Required Fields**: If v1.1 makes a field required that v1.0 didn't need, v1.0 reader must handle absence gracefully

Example:
```python
# v1.0 reader doesn't know about "proactive_insights" field
# JSON parser simply ignores it, no error
```

## Cache Invalidation Strategy

### Cache Key Format

Cache keys include schema version:

```
runner_state:{user_id}:{schema_version}
```

Example:
```
runner_state:abc123:v1.0.0
runner_state:abc123:v1.1.0
```

### Invalidation Triggers

On schema version bump:

1. **Minor Version Change** (v1.0 → v1.1):
   - Invalidate all keys matching pattern: `runner_state:{user_id}:*`
   - Let new cache entries be created with new version on next request
   - No data migration needed

2. **Major Version Change** (v1.x → v2.0):
   - Same invalidation as minor
   - May require dedicated migration script if data format fundamentally changed
   - Migration script runs as separate process, not inline

### Cache Lookup Logic

```python
def get_runner_state(user_id: str) -> RunnerState:
    current_version = get_current_schema_version()  # e.g., "1.1.0"
    cache_key = f"runner_state:{user_id}:{current_version}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    # Cache miss: compute with current schema version
    state = compute_runner_state(user_id, version=current_version)
    cache.set(cache_key, state, ttl=86400)  # 24 hours
    return state
```

## Migration Strategy

### Minor Version Changes (v1.0 → v1.1)

**Approach**: No bulk migration

- Old cached data is invalidated
- New data is computed on-demand with new schema
- Old cached data expires naturally (TTL)
- No user-visible impact

### Major Version Changes (v1.x → v2.0)

**Approach**: Controlled migration with rollback capability

1. **Preparation**:
   - Deploy code that reads both v1.x and v2.0 schemas
   - Run migration script in shadow mode (dual-write)
   - Validate migrated data

2. **Migration**:
   - Run migration script as background job
   - Migrate cached RunnerState entries
   - Keep v1.x data until migration verified

3. **Rollback**:
   - If issues detected, flip feature flag back to v1.x
   - Re-invalidate v2.0 caches, let v1.x recompute

### Migration Script Template

```python
def migrate_runner_state_v1_to_v2(user_id: str) -> RunnerStateV2:
    """
    Migrate RunnerState from v1.x to v2.0.

    This is only needed for major version changes.
    Minor version changes use on-demand recomputation.
    """
    # Read v1.x data
    v1_data = get_cached_runner_state_v1(user_id)

    # Transform to v2.0 format
    v2_data = transform_v1_to_v2(v1_data)

    # Validate
    validate_runner_state_v2(v2_data)

    return v2_data
```

## Schema Change Process

### 1. Design Phase

- Define new schema version (e.g., v1.1.0)
- Document what changed and why
- Define backward compatibility strategy

### 2. Implementation Phase

- Update JSON Schema files
- Update Pydantic models (if using)
- Add version field to all instances
- Update builders to use new schema

### 3. Testing Phase

- Unit tests with both old and new schemas
- Contract tests verify backward compatibility
- Integration tests with real data

### 4. Deployment Phase

- Deploy code that supports both versions
- Invalidate caches
- Monitor for errors
- Gradually migrate if needed

## Schema Registry

### Location

Schemas are stored in:
- `schemas/runner_state_v1_0.json`
- `schemas/runner_state_v1_1.json`
- `schemas/question_context_v1_0.json`
- etc.

### Schema Validation

All schema instances must validate against their declared version:

```python
def validate_runner_state(data: dict) -> bool:
    version = data.get("version")
    schema_file = f"schemas/runner_state_v{version}.json"
    return validate_against_schema(data, schema_file)
```

## Examples

### Example 1: Adding a Field (v1.0 → v1.1)

**v1.0 Schema:**
```json
{
  "version": "1.0.0",
  "runner_state": {
    "phase": "Build",
    "week_of_block": 8
  }
}
```

**v1.1 Schema:**
```json
{
  "version": "1.1.0",
  "runner_state": {
    "phase": "Build",
    "week_of_block": 8,
    "proactive_insights": []  // NEW FIELD
  }
}
```

**Reader Code:**
```python
# v1.1 reader reading v1.0 data
proactive_insights = runner_state.get("proactive_insights", [])  # Defaults to []
```

### Example 2: Changing Field Type (v1.1 → v1.2)

**v1.1:** `week_of_block: int`
**v1.2:** `week_of_block: Optional[int]` (nullable)

**Reader Code:**
```python
# v1.2 reader reading v1.1 data
week_of_block = runner_state.get("week_of_block")  # May be int or None
if week_of_block is not None:
    # Handle as int
```

## Checklist for Schema Changes

When making a schema change:

- [ ] Update version number (major.minor.patch)
- [ ] Update JSON schema file
- [ ] Update Pydantic models (if using)
- [ ] Update all builders to use new version
- [ ] Add backward compatibility tests
- [ ] Update cache invalidation logic
- [ ] Document what changed in CHANGELOG
- [ ] Test with old and new data
- [ ] Deploy with feature flag
- [ ] Monitor for errors

## Rollback Plan

If a schema change causes issues:

1. **Immediate**: Flip feature flag to previous version
2. **Cache**: Invalidate new version caches
3. **Code**: Redeploy previous schema version
4. **Investigation**: Identify root cause
5. **Fix**: Address issue before retrying

## Related Documents

- `schemas/runner_state_v1_0.json` - RunnerState v1.0 schema
- `schemas/question_context_v1_0.json` - QuestionContext v1.0 schema
- `docs/coach-architecture/phase-0/HumanReviewChecklist.md` - Review process for schema changes
