# ENABLE_WEEKLY_TASKS Analysis

## Summary

`ENABLE_WEEKLY_TASKS` is an **optional testing/development flag** used to manually trigger weekly scheduled tasks outside of the normal schedule.

## Usage

**Location**: `src/scripts/metrics_scheduler.py` lines 114-118

```python
# For development/testing: allow manual trigger via environment variable
# Set ENABLE_WEEKLY_TASKS=true to trigger on the next check (within the hour)
if os.getenv("ENABLE_WEEKLY_TASKS", "false").lower() == "true":
    # Clear the flag so it only runs once
    os.environ.pop("ENABLE_WEEKLY_TASKS", None)
    return True
```

## Purpose

- **Manual trigger for testing**: Allows developers to trigger weekly tasks immediately without waiting for the scheduled time (Sunday at 5 PM Central Time)
- **Development/testing only**: Explicitly marked as "For development/testing"
- **Self-clearing**: Automatically removes itself from environment after use (only runs once)

## How It Works

1. **Normal operation**: Scheduler runs automatically on schedule (Sunday at 5 PM Central Time)
2. **With flag set**: If `ENABLE_WEEKLY_TASKS=true`, scheduler runs on the next check (within 1 hour)
3. **After execution**: Flag is automatically cleared (popped from environment)

## Is It Needed?

### ❌ **Not Required for Production**

- ✅ Scheduler runs automatically on schedule
- ✅ No dependencies on this flag for normal operation
- ✅ Only used for manual testing/development

### ⚠️ **Optional for Staging**

- Useful for testing weekly tasks without waiting for scheduled time
- Can be set temporarily when needed
- Safe to leave set (it clears itself after use)

### ✅ **Safe to Delete**

- Won't break anything if removed
- Scheduler works normally without it
- Only affects manual testing capability

## Recommendation

### Option 1: **Delete It** (Recommended for Production)
- ✅ Cleaner environment variables
- ✅ No impact on normal operation
- ✅ Scheduler runs automatically on schedule

### Option 2: **Keep It** (If You Need Manual Testing)
- ✅ Useful for testing weekly tasks
- ✅ Can trigger scheduler manually when needed
- ⚠️ Set to `false` by default (only enable when testing)

## Current Status in Staging

If it's set to `TRUE` in staging:
- Likely leftover from testing
- Harmless (clears itself after use)
- Can be deleted or set to `false`

## Impact of Deletion

**If deleted:**
- ✅ Scheduler still runs automatically on schedule
- ✅ No functional changes
- ❌ Lose ability to manually trigger for testing (can still wait for schedule)

**If kept:**
- ✅ Can manually trigger weekly tasks for testing
- ✅ No negative impact (clears itself)
- ⚠️ One more variable to manage

## Conclusion

**Recommended**: **Delete it** if you don't need manual testing capability. It's purely optional and doesn't affect normal operation.
