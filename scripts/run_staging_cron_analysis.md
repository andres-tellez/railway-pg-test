# RUN_STAGING_CRON Analysis

## Summary

`RUN_STAGING_CRON` is a **GitHub Actions variable** (not a backend environment variable) that controls whether the staging cron workflow runs.

## Findings

### ✅ Used in GitHub Actions Workflow

**Location**: `.github/workflows/staging-cron.yml` line 11
```yaml
if: ${{ vars.RUN_STAGING_CRON == 'true' }}
```

**Status**:
- ✅ **Currently used** - Controls whether the workflow job runs
- ⚠️ **Workflow is disabled** - Schedule is commented out (line 5-6)
- ⚠️ **Manual trigger only** - Uses `workflow_dispatch` (line 7)

### Workflow Status

**Current State**:
- Schedule: **DISABLED** (commented out - replaced by webhooks)
- Trigger: **Manual only** (`workflow_dispatch`)
- Purpose: **Backup/fallback** if webhooks fail

**Comment in workflow**:
```yaml
# Disabled - replaced by real-time webhooks
# schedule:
#   - cron: "0 */6 * * *"
```

### Script Referenced

**Workflow calls**: `python -m src.scripts.run_staging_cron`
- ⚠️ **File doesn't exist** - Script referenced but not found in codebase
- This suggests the workflow might be broken or the script was deleted

## Recommendation

### Option 1: **Delete the Entire Workflow** (Recommended)

**Reason**:
- Workflow schedule is disabled (replaced by webhooks)
- Script it calls doesn't exist (`run_staging_cron.py`)
- Only manual trigger remains (can use admin endpoints instead)
- Railway cron service handles scheduled tasks

**Action**: Delete `.github/workflows/staging-cron.yml`

### Option 2: **Keep Workflow but Remove Variable Check**

**Reason**:
- Keep as backup manual trigger
- Remove the conditional check (always allow manual runs)

**Action**: Remove `if: ${{ vars.RUN_STAGING_CRON == 'true' }}`

### Option 3: **Keep as-is** (If you want manual backup)

**Reason**:
- Useful as emergency backup if webhooks fail
- Can manually trigger ingestion

**Action**: Keep workflow and variable

## Impact

**If deleting workflow**:
- ✅ No impact on production (Railway handles cron)
- ✅ No impact on staging (webhooks handle real-time sync)
- ✅ Manual ingestion still available via `/admin/trigger-ingest/<athlete_id>`

**If keeping workflow**:
- ⚠️ **Broken** - Script `run_staging_cron.py` doesn't exist
- ⚠️ **Would fail** if triggered manually

## Conclusion

**Recommended**: **Delete the entire workflow** since:
1. Schedule is disabled (webhooks replaced it)
2. Script it calls doesn't exist
3. Manual ingestion available via admin endpoints
4. Railway cron service handles scheduled tasks

**OR** if you want to keep it as backup, you need to:
1. Create `src/scripts/run_staging_cron.py` script
2. OR update workflow to call a different script
