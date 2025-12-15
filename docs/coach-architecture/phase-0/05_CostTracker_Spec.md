# Cost Tracker Specification

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

CostTracker provides real-time cost estimation, logging, and alerting for LLM API usage in the Coach system. It tracks costs at the request level and provides daily aggregations for monitoring and budget management.

## Core Principles

1. **Real-Time Estimation**: Calculate cost immediately after each request
2. **Accurate Pricing**: Use current model pricing from config
3. **Comprehensive Logging**: Log all cost data for analysis
4. **Proactive Alerts**: Alert on cost spikes or anomalies
5. **Per-User Tracking**: Track costs by user for budget management

## Pricing Model

### Model Pricing (per 1M tokens)

Stored in `config/model_pricing.yaml`:

```yaml
models:
  gpt-4o:
    input: 2.50   # $2.50 per 1M input tokens
    output: 10.00  # $10.00 per 1M output tokens
  gpt-4o-mini:
    input: 0.15
    output: 0.60
  gpt-4-turbo:
    input: 10.00
    output: 30.00
```

### Cost Calculation

```python
def calculate_cost(tokens_in: int, tokens_out: int, model: str) -> float:
    """Calculate cost for a single request"""

    pricing = load_model_pricing()[model]
    input_cost = (tokens_in / 1_000_000) * pricing["input"]
    output_cost = (tokens_out / 1_000_000) * pricing["output"]

    return input_cost + output_cost
```

## Implementation

### Integration with LLMClient

CostTracker is integrated directly into LLMClient:

```python
class LLMClient:
    def chat_completion(self, ...) -> OpenAIResponse:
        """Make LLM call and track cost"""

        # Make API call
        response = self._client.chat.completions.create(...)

        # Extract token usage
        tokens_in = response.usage.prompt_tokens
        tokens_out = response.usage.completion_tokens

        # Calculate cost
        cost = CostTracker.calculate_cost(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model=model
        )

        # Log cost
        CostTracker.log_request(
            user_id=user_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            request_id=request_id
        )

        return OpenAIResponse(
            content=response.content,
            usage=response.usage,
            cost=cost  # Include in response
        )
```

## Storage Schema

### conversation_logs Table

```sql
CREATE TABLE conversation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID,
    request_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Model info
    model VARCHAR(100) NOT NULL,

    -- Token usage
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    tokens_total INTEGER NOT NULL,

    -- Cost
    estimated_cost_usd DECIMAL(10, 6) NOT NULL,

    -- Metadata
    intent VARCHAR(100),
    latency_ms INTEGER,
    error_flag BOOLEAN DEFAULT FALSE,

    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_conversation_id (conversation_id)
);
```

### cost_summary Table (Daily Rollups)

```sql
CREATE TABLE cost_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    user_id UUID,  -- NULL for global summary

    -- Aggregates
    total_cost_usd DECIMAL(10, 2) NOT NULL,
    num_requests INTEGER NOT NULL,
    avg_cost_per_request DECIMAL(10, 6) NOT NULL,

    -- Token aggregates
    total_tokens_in BIGINT NOT NULL,
    total_tokens_out BIGINT NOT NULL,
    total_tokens BIGINT NOT NULL,

    -- Model breakdown (JSON)
    model_breakdown JSONB,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(date, user_id),
    INDEX idx_date (date),
    INDEX idx_user_id (user_id)
);
```

## Daily Rollup Job

### Implementation

```python
@celery.task
def daily_cost_rollup(date: date = None):
    """
    Aggregate daily costs from conversation_logs to cost_summary.

    Runs daily at 00:00 UTC.
    """
    if date is None:
        date = (datetime.utcnow() - timedelta(days=1)).date()

    # Rollup per user
    rollup_per_user(date)

    # Rollup global
    rollup_global(date)

def rollup_per_user(date: date):
    """Rollup costs per user for a given date"""

    query = """
        SELECT
            user_id,
            COUNT(*) as num_requests,
            SUM(estimated_cost_usd) as total_cost,
            SUM(tokens_in) as total_tokens_in,
            SUM(tokens_out) as total_tokens_out,
            AVG(estimated_cost_usd) as avg_cost,
            jsonb_object_agg(model, cost_by_model) as model_breakdown
        FROM conversation_logs
        WHERE DATE(timestamp) = :date
        GROUP BY user_id
    """

    for row in execute_query(query, date=date):
        upsert_cost_summary(
            date=date,
            user_id=row.user_id,
            total_cost=row.total_cost,
            num_requests=row.num_requests,
            avg_cost=row.avg_cost,
            total_tokens_in=row.total_tokens_in,
            total_tokens_out=row.total_tokens_out,
            model_breakdown=row.model_breakdown
        )

def rollup_global(date: date):
    """Rollup global costs for a given date"""

    query = """
        SELECT
            COUNT(*) as num_requests,
            SUM(estimated_cost_usd) as total_cost,
            SUM(tokens_in) as total_tokens_in,
            SUM(tokens_out) as total_tokens_out,
            AVG(estimated_cost_usd) as avg_cost,
            jsonb_object_agg(model, cost_by_model) as model_breakdown
        FROM conversation_logs
        WHERE DATE(timestamp) = :date
    """

    row = execute_query(query, date=date).first()

    upsert_cost_summary(
        date=date,
        user_id=None,  # Global summary
        total_cost=row.total_cost,
        num_requests=row.num_requests,
        avg_cost=row.avg_cost,
        total_tokens_in=row.total_tokens_in,
        total_tokens_out=row.total_tokens_out,
        model_breakdown=row.model_breakdown
    )
```

### Scheduling

```python
# celerybeat schedule
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'daily-cost-rollup': {
        'task': 'daily_cost_rollup',
        'schedule': crontab(hour=0, minute=0),  # 00:00 UTC daily
    },
}
```

### Error Handling

```python
@celery.task(max_retries=3)
def daily_cost_rollup(date: date = None):
    """Daily rollup with retry logic"""

    try:
        # Rollup logic
        rollup_per_user(date)
        rollup_global(date)

        logger.info(f"Daily cost rollup completed for {date}")

    except Exception as e:
        logger.error(f"Daily cost rollup failed for {date}: {e}")

        # Retry up to 3 times
        raise daily_cost_rollup.retry(exc=e, countdown=300)  # Retry in 5 min
```

## Real-Time Alerts

### Alert Conditions

1. **Single Request Cost > $0.10**
   - Likely indicates too-large context
   - Action: Alert engineering team
   - Threshold: Configurable (default: $0.10)

2. **Daily Global Cost > $100**
   - Budget threshold exceeded
   - Action: Alert + review top spenders
   - Threshold: Configurable (default: $100/day)

3. **Per-User Daily Cost > $0.50**
   - User potentially abusing system
   - Action: Alert + review user activity
   - Threshold: Configurable (default: $0.50/user/day)

4. **Cost Per Conversation > $0.10**
   - Average cost too high
   - Action: Investigate cost regression
   - Threshold: Configurable (default: $0.10/conversation)

### Alert Implementation

```python
class CostTracker:
    @staticmethod
    def log_request(user_id: str, model: str, tokens_in: int,
                    tokens_out: int, cost: float, request_id: str):
        """Log request and check for alerts"""

        # Store in database
        store_conversation_log(
            user_id=user_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=cost,
            request_id=request_id
        )

        # Check real-time alerts
        check_single_request_alert(cost)
        check_user_daily_alert(user_id, cost)

def check_single_request_alert(cost: float):
    """Alert if single request cost is too high"""

    threshold = config.get("cost_alerts.single_request_threshold", 0.10)

    if cost > threshold:
        alert_team(
            f"High-cost request detected: ${cost:.4f} (threshold: ${threshold})",
            severity="medium"
        )

def check_user_daily_alert(user_id: str, incremental_cost: float):
    """Alert if user's daily cost exceeds threshold"""

    today_cost = get_user_daily_cost(user_id, date.today())
    new_total = today_cost + incremental_cost

    threshold = config.get("cost_alerts.user_daily_threshold", 0.50)

    if new_total > threshold:
        alert_team(
            f"User {user_id} daily cost: ${new_total:.2f} (threshold: ${threshold})",
            severity="low"
        )

@periodic_task(run_every=timedelta(minutes=5))
def check_daily_cost_alerts():
    """Periodic check for daily cost thresholds"""

    today = date.today()

    # Check global daily cost
    global_cost = get_global_daily_cost(today)
    global_threshold = config.get("cost_alerts.global_daily_threshold", 100.0)

    if global_cost > global_threshold:
        alert_team(
            f"Global daily cost: ${global_cost:.2f} (threshold: ${global_threshold})",
            severity="high"
        )

    # Check per-user costs
    high_spenders = get_users_exceeding_threshold(today, threshold=0.50)
    if high_spenders:
        alert_team(
            f"Users exceeding daily cost threshold: {len(high_spenders)}",
            details=high_spenders,
            severity="medium"
        )
```

## Cost Queries

### Get User Daily Cost

```python
def get_user_daily_cost(user_id: str, date: date) -> float:
    """Get user's total cost for a given date"""

    query = """
        SELECT COALESCE(SUM(estimated_cost_usd), 0) as total_cost
        FROM conversation_logs
        WHERE user_id = :user_id
        AND DATE(timestamp) = :date
    """

    result = execute_query(query, user_id=user_id, date=date).first()
    return float(result.total_cost)
```

### Get Global Daily Cost

```python
def get_global_daily_cost(date: date) -> float:
    """Get global total cost for a given date"""

    query = """
        SELECT COALESCE(SUM(estimated_cost_usd), 0) as total_cost
        FROM conversation_logs
        WHERE DATE(timestamp) = :date
    """

    result = execute_query(query, date=date).first()
    return float(result.total_cost)
```

### Get Cost Trend

```python
def get_cost_trend(days: int = 7) -> List[dict]:
    """Get daily cost trend for last N days"""

    query = """
        SELECT
            DATE(timestamp) as date,
            SUM(estimated_cost_usd) as daily_cost,
            COUNT(*) as num_requests,
            AVG(estimated_cost_usd) as avg_cost_per_request
        FROM conversation_logs
        WHERE timestamp >= NOW() - INTERVAL ':days days'
        GROUP BY DATE(timestamp)
        ORDER BY date
    """

    return execute_query(query, days=days).fetchall()
```

## Metrics

### Key Metrics

1. **Cost Metrics**
   - `coach.cost.per_request` - Cost per request (histogram)
   - `coach.cost.daily_total` - Daily total cost (gauge)
   - `coach.cost.user_daily` - Per-user daily cost (gauge, tagged by user_id)

2. **Token Metrics**
   - `coach.tokens.in` - Input tokens (counter)
   - `coach.tokens.out` - Output tokens (counter)
   - `coach.tokens.total` - Total tokens (counter)

3. **Model Metrics**
   - `coach.cost.by_model` - Cost by model (counter, tagged by model)

### Metric Export

```python
def emit_cost_metrics(cost: float, tokens_in: int, tokens_out: int, model: str):
    """Emit cost metrics to observability system"""

    metrics.histogram("coach.cost.per_request", cost, tags={"model": model})
    metrics.increment("coach.tokens.in", tokens_in, tags={"model": model})
    metrics.increment("coach.tokens.out", tokens_out, tags={"model": model})
```

## Dashboard

### Cost Dashboard

Display:
- Daily cost trend (last 7/30 days)
- Cost per conversation (p50, p95, p99)
- Cost by model (breakdown)
- Top spenders (users with highest daily cost)
- Cost alerts (recent alerts)

## Configuration

### Environment Variables

```bash
COST_TRACKING_ENABLED=true
COST_ALERT_SINGLE_REQUEST_THRESHOLD=0.10
COST_ALERT_USER_DAILY_THRESHOLD=0.50
COST_ALERT_GLOBAL_DAILY_THRESHOLD=100.0
COST_ALERT_COST_PER_CONVERSATION_THRESHOLD=0.10
```

### Config File

`config/model_pricing.yaml`:
```yaml
models:
  gpt-4o:
    input: 2.50
    output: 10.00
  gpt-4o-mini:
    input: 0.15
    output: 0.60

alerts:
  single_request_threshold: 0.10
  user_daily_threshold: 0.50
  global_daily_threshold: 100.0
  cost_per_conversation_threshold: 0.10
```

## Testing

### Unit Tests

```python
def test_cost_calculation():
    """Test cost calculation accuracy"""

    cost = CostTracker.calculate_cost(
        tokens_in=1000,
        tokens_out=500,
        model="gpt-4o"
    )

    expected = (1000 / 1_000_000 * 2.50) + (500 / 1_000_000 * 10.00)
    assert abs(cost - expected) < 0.0001

def test_alert_thresholds():
    """Test alert triggering"""

    # Test single request alert
    with mock.patch('cost_tracker.alert_team') as mock_alert:
        CostTracker.log_request(
            user_id="test",
            model="gpt-4o",
            tokens_in=100000,  # High token count
            tokens_out=50000,
            cost=0.50,  # Above threshold
            request_id="test-123"
        )
        assert mock_alert.called
```

## Related Documents

- `docs/coach-architecture/phase-0/ObservabilityInfrastructure.md` - Metrics and monitoring
- `config/model_pricing.yaml` - Model pricing configuration
