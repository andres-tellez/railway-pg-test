# Rollback Runbook

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This runbook defines the exact procedures for rolling back Coach v2 if issues are detected in production. It includes trigger conditions, rollback steps, investigation procedures, and recovery plans.

## Rollback Principles

1. **Speed**: Rollback should be instant (< 1 minute)
2. **Safety**: No data loss during rollback
3. **Visibility**: Clear communication of rollback status
4. **Investigation**: Systematic root cause analysis
5. **Recovery**: Controlled re-rollout after fixes

## Trigger Conditions

### Automatic Rollback Triggers

These conditions should trigger **immediate** rollback:

1. **Error Rate > 5%** (over 10-minute window)
   - Metric: `coach.v2.error_rate`
   - Threshold: 5%
   - Window: 10 minutes
   - Severity: **CRITICAL**

2. **Safety Incident Confirmed**
   - Medical red flag missed by SafetyScanner
   - Unsafe training advice given
   - Severity: **CRITICAL**

3. **Cost Spike > 300%**
   - Daily cost > 3x baseline
   - Sustained for > 1 hour
   - Severity: **HIGH**

### Manual Rollback Triggers

These conditions may warrant **manual** rollback decision:

1. **Latency Regression > 200%**
   - p95 latency > 2x baseline
   - Sustained for > 30 minutes
   - Severity: **MEDIUM**

2. **User Complaints Spike**
   - Support tickets > 5x baseline
   - Negative feedback > 10% of users
   - Severity: **MEDIUM**

3. **Quality Regression**
   - Response quality ratings < baseline - 20%
   - Sustained for > 24 hours
   - Severity: **LOW**

## Rollback Procedure

### Step 1: Immediate Rollback (0-1 minute)

```bash
# 1. Disable Coach v2 via feature flag
# Via admin dashboard or environment variable:
COACH_V2_ENABLED=false

# OR via database:
UPDATE feature_flags SET enabled = false WHERE flag = 'coach_v2_enabled';

# 2. Verify rollback
# Check that all traffic is routing to v1:
curl https://api.yourapp.com/health/coach-version
# Expected: {"version": "v1", "traffic_percentage": 100}

# 3. Disable shadow mode (optional, but recommended)
COACH_SHADOW_MODE_ENABLED=false
```

### Step 2: Verify Rollback Success (1-2 minutes)

```bash
# 1. Check error rate drops
# Monitor dashboard: coach.v1.error_rate should be normal

# 2. Check all requests routing to v1
# Query logs:
SELECT COUNT(*)
FROM conversation_logs
WHERE timestamp > NOW() - INTERVAL '5 minutes'
AND version = 'v1';
# Should be 100% of requests

# 3. Verify no new v2 errors
# Query logs:
SELECT COUNT(*)
FROM conversation_logs
WHERE timestamp > NOW() - INTERVAL '5 minutes'
AND version = 'v2';
# Should be 0
```

### Step 3: Communication (2-5 minutes)

```markdown
# Internal Alert

**Subject:** Coach v2 Rollback - [Reason]

**Status:** ✅ Rolled back to v1

**Trigger:** [Error rate > 5% / Safety incident / Cost spike]

**Time:** [Timestamp]

**Impact:** All traffic now using Coach v1

**Next Steps:**
- Investigation in progress
- Root cause analysis expected within [timeframe]
- Updates will be provided in [channel]

# External Communication (if needed)

[Only if users are impacted]

"We're temporarily using our previous coaching system while we
investigate a performance issue. All coaching features remain
available. We'll restore the new system once the issue is resolved."
```

### Step 4: Investigation (5-30 minutes)

#### 4.1 Gather Evidence

```bash
# 1. Check recent deployments
git log --oneline --since="2 hours ago"

# 2. Check error logs
# Query for errors in last 30 minutes:
SELECT *
FROM conversation_logs
WHERE timestamp > NOW() - INTERVAL '30 minutes'
AND error_flag = true
ORDER BY timestamp DESC
LIMIT 100;

# 3. Check recent prompt changes
# If prompt was changed, check version:
SELECT * FROM prompt_versions
WHERE created_at > NOW() - INTERVAL '2 hours'
ORDER BY created_at DESC;

# 4. Check schema changes
# If schema was changed, check version:
SELECT * FROM schema_versions
WHERE created_at > NOW() - INTERVAL '2 hours'
ORDER BY created_at DESC;

# 5. Check cost logs
SELECT
    DATE_TRUNC('minute', timestamp) as minute,
    SUM(estimated_cost_usd) as cost,
    COUNT(*) as requests
FROM conversation_logs
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;
```

#### 4.2 Identify Root Cause

Check common issues:

1. **Prompt Changes**
   - Was prompt version updated?
   - Check prompt diff
   - Test prompt locally

2. **Schema Changes**
   - Was schema version updated?
   - Check schema validation errors
   - Test schema with sample data

3. **Configuration Changes**
   - Were thresholds changed?
   - Was model changed?
   - Check config diff

4. **Code Deployment**
   - Was new code deployed?
   - Check git diff
   - Review recent PRs

5. **Infrastructure Issues**
   - LLM API outages?
   - Database connection issues?
   - Cache failures?

#### 4.3 Document Findings

```markdown
# Root Cause Analysis

**Issue:** [Description]

**Root Cause:** [Identified cause]

**Timeline:**
- [Time] - Issue started
- [Time] - Rollback executed
- [Time] - Root cause identified

**Evidence:**
- [Evidence 1]
- [Evidence 2]

**Fix Required:** [Description of fix]
```

### Step 5: Data Integrity Check (if applicable)

If Coach v2 wrote any data (e.g., auto-updated plans):

```bash
# 1. Check for data writes
SELECT COUNT(*)
FROM plan_updates
WHERE created_at > [rollback_time] - INTERVAL '1 hour'
AND created_at < [rollback_time];

# 2. If data was written, decide:
# - Keep it? (if safe)
# - Rollback? (if unsafe)
# - Review manually? (if uncertain)

# 3. If rollback needed, create migration script
# (This should be rare - most v2 features are read-only)
```

## Recovery Procedure

### Step 1: Fix the Issue

```bash
# 1. Create fix branch
git checkout -b fix/coach-v2-[issue-description]

# 2. Implement fix
# [Fix code]

# 3. Add tests
# [Add regression tests]

# 4. Test locally
pytest tests/
# [Verify all tests pass]

# 5. Get review
# [Create PR, get approval]
```

### Step 2: Deploy Fix to Shadow Mode

```bash
# 1. Deploy fix to production (but v2 still disabled)
git checkout main
git merge fix/coach-v2-[issue-description]
# Deploy to production

# 2. Enable shadow mode only
COACH_SHADOW_MODE_ENABLED=true
COACH_V2_ENABLED=false  # Still disabled

# 3. Monitor shadow mode for 24 hours
# - Check error rate
# - Check cost
# - Check quality metrics

# 4. If shadow mode looks good, proceed to Step 3
```

### Step 3: Gradual Re-Rollout

```bash
# 1. Enable v2 for 5% of users
COACH_V2_ENABLED=true
COACH_V2_PERCENTAGE=5

# 2. Monitor for 1 hour
# - Error rate
# - Latency
# - Cost
# - User feedback

# 3. If stable, increase to 25%
COACH_V2_PERCENTAGE=25

# 4. Monitor for 1 hour

# 5. If stable, increase to 50%
COACH_V2_PERCENTAGE=50

# 6. Monitor for 1 hour

# 7. If stable, increase to 100%
COACH_V2_PERCENTAGE=100
```

### Step 4: Post-Mortem

```markdown
# Post-Mortem Document

**Issue:** [Description]
**Date:** [Date]
**Duration:** [Duration of issue]

## Timeline
- [Time] - Issue detected
- [Time] - Rollback executed
- [Time] - Root cause identified
- [Time] - Fix deployed
- [Time] - Full rollout completed

## Root Cause
[Detailed root cause analysis]

## Impact
- Users affected: [Number]
- Duration: [Time]
- Cost impact: [If applicable]

## Fix Applied
[Description of fix]

## Prevention
- [Action item 1]
- [Action item 2]

## Lessons Learned
- [Lesson 1]
- [Lesson 2]
```

## Rollback Checklist

### Before Rollback

- [ ] Confirm issue severity meets trigger condition
- [ ] Notify team (if manual rollback)
- [ ] Have rollback command ready
- [ ] Have monitoring dashboard open

### During Rollback

- [ ] Execute rollback command
- [ ] Verify feature flag changed
- [ ] Check error rate drops
- [ ] Verify all traffic routes to v1
- [ ] Confirm no new v2 errors

### After Rollback

- [ ] Communicate status to team
- [ ] Begin investigation
- [ ] Document findings
- [ ] Create fix (if needed)
- [ ] Plan recovery

## Automation

### Automated Rollback Script

```python
def automated_rollback():
    """Automated rollback if trigger conditions met"""

    # Check error rate
    error_rate = get_error_rate(window_minutes=10)
    if error_rate > 0.05:  # 5%
        execute_rollback(reason="Error rate > 5%")
        alert_team("Automated rollback: Error rate > 5%")
        return

    # Check cost spike
    cost_spike = get_cost_spike()
    if cost_spike > 3.0:  # 300%
        execute_rollback(reason="Cost spike > 300%")
        alert_team("Automated rollback: Cost spike > 300%")
        return

def execute_rollback(reason: str):
    """Execute rollback procedure"""

    # Disable v2
    set_feature_flag("coach_v2_enabled", False)

    # Disable shadow mode
    set_feature_flag("coach_shadow_mode_enabled", False)

    # Log rollback
    log_rollback_event(reason=reason, timestamp=datetime.utcnow())

    # Emit metrics
    metrics.increment("coach.rollback.count", tags={"reason": reason})
```

### Monitoring Integration

Set up alerts that can trigger automated rollback:

```yaml
# Prometheus alerting rules
groups:
  - name: coach_rollback_alerts
    rules:
      - alert: CoachV2HighErrorRate
        expr: coach_v2_error_rate > 0.05
        for: 10m
        annotations:
          summary: "Coach v2 error rate > 5%"
        # Could trigger automated rollback webhook
```

## Related Documents

- `docs/coach-architecture/phase-0/ShadowModeExecutor.md` - Shadow mode for safe testing
- `docs/coach-architecture/phase-0/ObservabilityInfrastructure.md` - Monitoring and alerts
