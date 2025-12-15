# Shadow Mode Executor Specification

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

Shadow Mode allows us to run the new Coach v2 pipeline in parallel with the existing Coach v1 system without impacting users. This enables safe testing, comparison, and gradual rollout.

## Core Principles

1. **Zero User Impact**: Users always get v1 response, v2 runs in background
2. **Deterministic Routing**: Same user always routes to same shadow bucket
3. **Async Execution**: v2 never blocks v1 response
4. **Comprehensive Logging**: Capture all metrics for comparison
5. **Error Isolation**: v2 errors never affect user experience

## Routing Strategy

### Bucket Assignment

For each request, compute shadow bucket:

```python
def get_shadow_bucket(user_id: str) -> int:
    """Returns 0-99, deterministic per user"""
    import hashlib
    hash_obj = hashlib.md5(user_id.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    return hash_int % 100
```

### Shadow Mode Activation

```python
SHADOW_MODE_PERCENTAGE = 10  # Configurable, e.g., 10% of users

def should_enable_shadow_mode(user_id: str) -> bool:
    bucket = get_shadow_bucket(user_id)
    return bucket < SHADOW_MODE_PERCENTAGE
```

**Properties:**
- Deterministic: Same user always gets same decision
- Tunable: Change percentage without user churn
- Distributed: Even distribution across user base

## Execution Flow

### Primary Path (Coach v1)

```python
def handle_user_request(user_id: str, message: str):
    # 1. Execute v1 (user waits for this)
    start_time = time.time()
    v1_response = coach_v1.generate_response(user_id, message)
    v1_latency = (time.time() - start_time) * 1000  # ms

    # 2. Check if shadow mode enabled
    if should_enable_shadow_mode(user_id):
        # Queue v2 execution (async, doesn't block)
        queue_shadow_execution(user_id, message, v1_response, v1_latency)

    # 3. Return v1 response immediately
    return v1_response
```

### Shadow Path (Coach v2)

```python
@background_task
def execute_shadow_mode(user_id: str, message: str, v1_response: str, v1_latency_ms: float):
    """Executes v2 in background, logs results"""

    shadow_log = {
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "request_payload_hash": hash_message(message),
        "v1_response": v1_response,
        "v1_latency_ms": v1_latency_ms,
        "v2_error_flag": False,
        "v2_response_structure_valid": False,
    }

    try:
        # Execute v2
        start_time = time.time()
        v2_response = coach_v2.generate_response(user_id, message)
        v2_latency = (time.time() - start_time) * 1000  # ms

        # Get token usage from LLMClient
        v2_tokens_in = get_last_request_tokens_in()
        v2_tokens_out = get_last_request_tokens_out()

        # Validate response structure
        v2_valid = ResponseFormatter.validate_structure(v2_response)

        # Update log
        shadow_log.update({
            "v2_response": v2_response,
            "v2_latency_ms": v2_latency,
            "v2_tokens_in": v2_tokens_in,
            "v2_tokens_out": v2_tokens_out,
            "v2_response_structure_valid": v2_valid,
        })

    except Exception as e:
        # v2 failed, but user already has v1 response
        shadow_log.update({
            "v2_error_flag": True,
            "v2_error_message": str(e),
            "v2_error_type": type(e).__name__,
        })
        logger.error(f"Shadow mode v2 failed for user {user_id}: {e}")

    # Store log
    store_shadow_log(shadow_log)

    # Emit metrics
    emit_shadow_metrics(shadow_log)
```

## Background Task Queue

### Implementation

Use a task queue (e.g., Celery, AWS SQS, or in-memory queue for small scale):

```python
from celery import Celery

app = Celery('coach_shadow')

@app.task
def shadow_mode_task(user_id: str, message: str, v1_response: str, v1_latency_ms: float):
    execute_shadow_mode(user_id, message, v1_response, v1_latency_ms)
```

### Timeout Handling

```python
@background_task(timeout=30)  # 30 second timeout
def execute_shadow_mode(...):
    # If v2 takes > 30 seconds, task is cancelled
    # Log timeout, don't block user
```

## Storage Schema

### shadow_logs Table

```sql
CREATE TABLE shadow_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    request_payload_hash VARCHAR(64),  -- SHA256 hash of request

    -- v1 metrics
    v1_response TEXT,
    v1_latency_ms FLOAT,
    v1_tokens_in INTEGER,
    v1_tokens_out INTEGER,

    -- v2 metrics
    v2_response TEXT,
    v2_latency_ms FLOAT,
    v2_tokens_in INTEGER,
    v2_tokens_out INTEGER,
    v2_error_flag BOOLEAN DEFAULT FALSE,
    v2_error_message TEXT,
    v2_error_type VARCHAR(100),
    v2_response_structure_valid BOOLEAN DEFAULT FALSE,

    -- Comparison metrics (computed)
    latency_delta_ms FLOAT,  -- v2_latency - v1_latency
    cost_delta_usd FLOAT,    -- v2_cost - v1_cost
    response_similarity_score FLOAT,  -- Optional: semantic similarity

    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_error_flag (v2_error_flag)
);
```

## Error Handling

### v2 Failure Scenarios

1. **LLM Timeout**: Log timeout, mark error_flag
2. **LLM API Error**: Log error, mark error_flag
3. **Context Too Large**: Log compression warning, mark error_flag
4. **Invalid Response**: Log validation failure, mark error_flag
5. **Unexpected Exception**: Log exception, mark error_flag

**Key Principle**: v2 errors never affect user experience. User always receives v1 response.

### Error Logging

```python
def emit_shadow_metrics(shadow_log: dict):
    """Emit metrics for observability"""

    # Error rate
    if shadow_log["v2_error_flag"]:
        metrics.increment("coach.shadow.v2.error_count", tags={
            "error_type": shadow_log.get("v2_error_type", "unknown")
        })

    # Latency comparison
    latency_delta = shadow_log["v2_latency_ms"] - shadow_log["v1_latency_ms"]
    metrics.histogram("coach.shadow.latency_delta_ms", latency_delta)

    # Cost comparison
    cost_delta = calculate_cost_delta(shadow_log)
    metrics.histogram("coach.shadow.cost_delta_usd", cost_delta)
```

## Alerting

### Alert Conditions

1. **v2 Error Rate > 5%** (over 10-minute window)
   - Action: Alert engineering team
   - Threshold: Configurable (default: 5%)

2. **v2 Latency > 3x v1 Latency** (consistently)
   - Action: Investigate performance regression
   - Threshold: p95 latency delta > 300% of v1

3. **v2 Cost > 2x v1 Cost** (consistently)
   - Action: Investigate cost regression
   - Threshold: Average cost delta > 200% of v1

### Alert Implementation

```python
def check_shadow_alerts():
    """Run periodically (every 5 minutes)"""

    window_start = datetime.utcnow() - timedelta(minutes=10)

    # Query recent shadow logs
    recent_logs = get_shadow_logs_since(window_start)

    if not recent_logs:
        return

    total = len(recent_logs)
    errors = sum(1 for log in recent_logs if log["v2_error_flag"])
    error_rate = errors / total

    if error_rate > 0.05:  # 5%
        alert_team(
            f"Shadow mode v2 error rate: {error_rate:.1%} (threshold: 5%)",
            severity="high"
        )
```

## Metrics

### Key Metrics to Track

1. **Shadow Mode Coverage**
   - `coach.shadow.enabled_count` - Number of requests in shadow mode
   - `coach.shadow.coverage_percent` - Percentage of requests

2. **Performance**
   - `coach.shadow.v1.latency_ms` - v1 latency (histogram)
   - `coach.shadow.v2.latency_ms` - v2 latency (histogram)
   - `coach.shadow.latency_delta_ms` - v2 - v1 (histogram)

3. **Cost**
   - `coach.shadow.v1.cost_usd` - v1 cost per request
   - `coach.shadow.v2.cost_usd` - v2 cost per request
   - `coach.shadow.cost_delta_usd` - v2 - v1 cost

4. **Quality**
   - `coach.shadow.v2.error_count` - v2 errors (counter)
   - `coach.shadow.v2.structure_valid` - Valid responses (counter)
   - `coach.shadow.v2.structure_invalid` - Invalid responses (counter)

## Comparison Analysis

### Response Quality Comparison

```python
def compare_responses(v1_response: str, v2_response: str) -> dict:
    """Compare v1 and v2 responses"""

    return {
        "length_diff": len(v2_response) - len(v1_response),
        "word_count_diff": len(v2_response.split()) - len(v1_response.split()),
        "similarity_score": calculate_semantic_similarity(v1_response, v2_response),
        "structure_compliance": ResponseFormatter.validate_structure(v2_response),
    }
```

### Cost Comparison

```python
def calculate_cost_delta(shadow_log: dict) -> float:
    """Calculate cost difference between v1 and v2"""

    v1_cost = estimate_cost(
        shadow_log["v1_tokens_in"],
        shadow_log["v1_tokens_out"],
        model="gpt-4o"  # v1 model
    )

    v2_cost = estimate_cost(
        shadow_log["v2_tokens_in"],
        shadow_log["v2_tokens_out"],
        model="gpt-4o"  # v2 model (may differ)
    )

    return v2_cost - v1_cost
```

## Dashboard

### Shadow Mode Dashboard

Display:
- Shadow mode coverage percentage
- v1 vs v2 latency comparison (p50, p95, p99)
- v1 vs v2 cost comparison
- v2 error rate
- v2 response structure validity rate
- Top error types

## Rollout Strategy

### Phase 1: 5% Shadow Mode
- Validate shadow mode works correctly
- Ensure no performance impact
- Monitor error rates

### Phase 2: 10% Shadow Mode
- Increase coverage
- Gather more comparison data
- Validate quality improvements

### Phase 3: 25% Shadow Mode
- Larger sample size
- More statistical confidence
- Continue monitoring

### Phase 4: 50% → 100%
- Gradually increase
- Monitor at each step
- Ready for full rollout

## Configuration

### Environment Variables

```bash
SHADOW_MODE_ENABLED=true
SHADOW_MODE_PERCENTAGE=10
SHADOW_MODE_TIMEOUT_SECONDS=30
SHADOW_MODE_ALERT_ERROR_RATE_THRESHOLD=0.05
```

### Feature Flag

```python
SHADOW_MODE_FEATURE_FLAG = "coach_shadow_mode_enabled"
SHADOW_MODE_PERCENTAGE_FLAG = "coach_shadow_mode_percentage"
```

## Testing

### Unit Tests

- Test bucket assignment (deterministic)
- Test routing logic
- Test error handling
- Test metrics emission

### Integration Tests

- Test full shadow mode flow
- Test background task execution
- Test timeout handling
- Test error logging

### Load Tests

- Verify shadow mode doesn't impact v1 latency
- Verify background tasks don't overwhelm queue
- Verify storage can handle shadow log volume

## Related Documents

- `docs/coach-architecture/phase-0/ObservabilityInfrastructure.md` - Metrics and monitoring
- `docs/coach-architecture/phase-0/RollbackRunbook.md` - Rollback procedures
