# ENABLE_WEEKLY_TASKS Code Deletion Analysis

## Code That Can Be Deleted

### 1. Main Code Block (src/scripts/metrics_scheduler.py)

**Lines 113-118**: Manual trigger check in `should_run_scheduled_tasks()`

```python
# For development/testing: allow manual trigger via environment variable
# Set ENABLE_WEEKLY_TASKS=true to trigger on the next check (within the hour)
if os.getenv("ENABLE_WEEKLY_TASKS", "false").lower() == "true":
    # Clear the flag so it only runs once
    os.environ.pop("ENABLE_WEEKLY_TASKS", None)
    return True
```

**Impact**: Removes manual trigger capability

### 2. Log Message (src/scripts/metrics_scheduler.py)

**Line 587**: Log message mentioning the feature

```python
"💡 Set ENABLE_WEEKLY_TASKS=true environment variable to manually trigger (for testing)"
```

**Impact**: Removes informational log message

### 3. Documentation References

**Files to update:**
- `docs/weekly-scheduler-email-setup.md` (lines 34, 97, 205, 222)
- `docs/local-testing-guide.md` (lines 14, 17, 20, 93, 131, 149, 151)

**Impact**: Removes documentation about manual trigger feature

## Alternative Manual Trigger Methods

**Existing alternatives:**
- ✅ `/admin/refresh-metrics` - Manually triggers metrics refresh only
- ✅ `/admin/trigger-ingest/<athlete_id>` - Manually triggers activity ingestion
- ❌ **No alternative** for full weekly task sequence (metrics + rebuild + emails)

## Recommendation

### Option 1: Delete Code (Recommended if you don't need manual testing)

**Pros:**
- ✅ Cleaner codebase
- ✅ Removes unused feature
- ✅ Scheduler runs automatically anyway

**Cons:**
- ❌ Lose ability to manually test full weekly task sequence
- ❌ Can't trigger outside of scheduled time for testing

**Action:**
1. Delete lines 113-118 from `metrics_scheduler.py`
2. Delete/update line 587 log message
3. Update documentation files

### Option 2: Keep Code (Recommended if you need testing)

**Pros:**
- ✅ Can manually test weekly tasks
- ✅ Useful for debugging
- ✅ No impact if env var not set

**Cons:**
- ⚠️ Extra code to maintain
- ⚠️ One more env var to manage

**Action:**
- Keep code as-is
- Just remove env var from Railway (code will default to "false")

## Impact Analysis

**If code is deleted:**
- ✅ Scheduler still runs automatically on schedule
- ✅ No functional changes to production
- ❌ Lose manual testing capability
- ❌ Can't test weekly tasks outside scheduled time

**If code is kept but env var removed:**
- ✅ Scheduler runs automatically on schedule
- ✅ Code still exists for future testing
- ✅ No env var to manage
- ✅ Can still manually test by setting env var temporarily

## Final Recommendation

**Keep the code, delete the env var** - Best of both worlds:
- Code available if needed for testing
- No env var to manage in production
- Can temporarily set env var when testing

**OR** if you never need manual testing:

**Delete the code entirely** - Cleaner codebase:
- Delete lines 113-118
- Delete line 587 log message
- Update documentation
