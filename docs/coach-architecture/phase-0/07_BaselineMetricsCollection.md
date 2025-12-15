# Baseline Metrics Collection Plan

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

Before implementing Coach v2, we must establish baseline metrics for the current Coach v1 system. These baselines enable us to measure improvement, detect regressions, and set realistic targets.

## Collection Period

**Duration:** Minimum 1 week (recommended: 2 weeks)
**Start:** Before Phase 1 begins
**End:** Before Phase 2 shadow mode starts

## Metrics to Collect

### 1. Performance Metrics

#### Latency

- **Metric**: Response time from request to response
- **Collection**: Per-request timing
- **Aggregation**: p50, p95, p99, p99.9
- **Target**: Collect at least 1,000 requests

```python
# Example collection
latency_ms = (response_time - request_time) * 1000
metrics.histogram("coach.v1.latency_ms", latency_ms)
```

**Baseline Targets:**
- p50: < 2 seconds
- p95: < 5 seconds
- p99: < 10 seconds

#### Error Rate

- **Metric**: Percentage of requests that fail
- **Collection**: Count errors / total requests
- **Aggregation**: Per hour, per day
- **Target**: < 1% error rate

```python
# Example collection
if error_occurred:
    metrics.increment("coach.v1.error_count")
metrics.increment("coach.v1.request_count")
error_rate = error_count / request_count
```

### 2. Cost Metrics

#### Cost Per Conversation

- **Metric**: Estimated cost per conversation
- **Collection**: Calculate from token usage
- **Aggregation**: Average, p50, p95, p99
- **Method**: Use same CostTracker logic

```python
# Example collection
cost = calculate_cost(tokens_in, tokens_out, model)
metrics.histogram("coach.v1.cost_per_conversation", cost)
```

**Baseline Target:** < $0.05 per conversation

#### Daily Cost

- **Metric**: Total daily cost
- **Collection**: Sum of all conversation costs per day
- **Aggregation**: Daily total
- **Target**: Establish normal daily range

```python
# Example collection
daily_cost = sum(conversation_costs_for_day)
metrics.gauge("coach.v1.daily_cost", daily_cost)
```

### 3. Token Usage

#### Tokens Per Request

- **Metric**: Input and output tokens per request
- **Collection**: From LLM API response
- **Aggregation**: Average, p50, p95
- **Target**: Understand token distribution

```python
# Example collection
metrics.histogram("coach.v1.tokens_in", tokens_in)
metrics.histogram("coach.v1.tokens_out", tokens_out)
metrics.histogram("coach.v1.tokens_total", tokens_in + tokens_out)
```

### 4. User Engagement Metrics

#### Follow-Up Question Rate

- **Metric**: Percentage of conversations with follow-up questions
- **Collection**: Count conversations with >1 message / total conversations
- **Aggregation**: Daily percentage
- **Target**: Establish baseline engagement

```python
# Example collection
conversations_with_followups = count_conversations_with_multiple_messages()
total_conversations = count_total_conversations()
followup_rate = conversations_with_followups / total_conversations
metrics.gauge("coach.v1.followup_rate", followup_rate)
```

#### Conversation Length

- **Metric**: Average messages per conversation
- **Collection**: Count messages per conversation
- **Aggregation**: Average
- **Target**: Understand typical conversation depth

```python
# Example collection
avg_messages = calculate_avg_messages_per_conversation()
metrics.gauge("coach.v1.avg_messages_per_conversation", avg_messages)
```

### 5. Quality Metrics (If Available)

#### User Ratings

- **Metric**: Thumbs up/down or star ratings
- **Collection**: User feedback (if implemented)
- **Aggregation**: Percentage positive
- **Target**: If not available, skip (add in Phase 2)

```python
# Example collection (if available)
positive_ratings = count_positive_ratings()
total_ratings = count_total_ratings()
positive_rate = positive_ratings / total_ratings
metrics.gauge("coach.v1.positive_rating_rate", positive_rate)
```

## Data Collection Implementation

### Instrumentation

Add metrics collection to current Coach v1 endpoint:

```python
@conversation_bp.route("/conversations/<conversation_id>/messages", methods=["POST"])
def send_message(conversation_id):
    """Current endpoint with baseline metrics collection"""

    start_time = time.time()

    try:
        # Existing logic
        response = generate_coach_response(...)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Collect metrics
        BaselineMetricsCollector.record_request(
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            error_occurred=False
        )

        return response

    except Exception as e:
        # Calculate latency even on error
        latency_ms = (time.time() - start_time) * 1000

        # Collect error metrics
        BaselineMetricsCollector.record_request(
            latency_ms=latency_ms,
            error_occurred=True,
            error_type=type(e).__name__
        )

        raise
```

### BaselineMetricsCollector

```python
class BaselineMetricsCollector:
    """Collects baseline metrics for Coach v1"""

    @staticmethod
    def record_request(
        latency_ms: float,
        tokens_in: int = None,
        tokens_out: int = None,
        cost: float = None,
        error_occurred: bool = False,
        error_type: str = None
    ):
        """Record a single request's metrics"""

        # Emit to metrics system
        metrics.histogram("coach.v1.baseline.latency_ms", latency_ms)
        metrics.increment("coach.v1.baseline.request_count")

        if error_occurred:
            metrics.increment("coach.v1.baseline.error_count",
                            tags={"error_type": error_type})

        if tokens_in is not None:
            metrics.histogram("coach.v1.baseline.tokens_in", tokens_in)
        if tokens_out is not None:
            metrics.histogram("coach.v1.baseline.tokens_out", tokens_out)
        if cost is not None:
            metrics.histogram("coach.v1.baseline.cost", cost)

        # Store in database for analysis
        store_baseline_metric(
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            error_occurred=error_occurred,
            error_type=error_type,
            timestamp=datetime.utcnow()
        )
```

### Storage Schema

```sql
CREATE TABLE baseline_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Performance
    latency_ms FLOAT NOT NULL,

    -- Cost
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd DECIMAL(10, 6),

    -- Errors
    error_occurred BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),

    -- Metadata
    user_id UUID,
    conversation_id UUID,

    INDEX idx_timestamp (timestamp),
    INDEX idx_error_occurred (error_occurred)
);
```

## Analysis and Reporting

### Daily Summary

Generate daily summary reports:

```python
def generate_daily_baseline_summary(date: date) -> dict:
    """Generate daily summary of baseline metrics"""

    query = """
        SELECT
            COUNT(*) as total_requests,
            COUNT(*) FILTER (WHERE error_occurred) as error_count,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) as p50_latency,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99_latency,
            AVG(cost_usd) as avg_cost,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY cost_usd) as p50_cost,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY cost_usd) as p95_cost,
            AVG(tokens_in) as avg_tokens_in,
            AVG(tokens_out) as avg_tokens_out
        FROM baseline_metrics
        WHERE DATE(timestamp) = :date
    """

    return execute_query(query, date=date).first()
```

### Final Baseline Report

After collection period, generate final report:

```python
def generate_baseline_report(start_date: date, end_date: date) -> dict:
    """Generate comprehensive baseline report"""

    return {
        "collection_period": {
            "start": start_date,
            "end": end_date,
            "duration_days": (end_date - start_date).days
        },
        "performance": {
            "p50_latency_ms": calculate_percentile("latency_ms", 0.50),
            "p95_latency_ms": calculate_percentile("latency_ms", 0.95),
            "p99_latency_ms": calculate_percentile("latency_ms", 0.99),
        },
        "cost": {
            "avg_cost_per_conversation": calculate_avg("cost_usd"),
            "p50_cost": calculate_percentile("cost_usd", 0.50),
            "p95_cost": calculate_percentile("cost_usd", 0.95),
            "daily_avg_cost": calculate_daily_avg_cost(),
        },
        "tokens": {
            "avg_tokens_in": calculate_avg("tokens_in"),
            "avg_tokens_out": calculate_avg("tokens_out"),
            "avg_tokens_total": calculate_avg("tokens_in + tokens_out"),
        },
        "errors": {
            "error_rate": calculate_error_rate(),
            "total_errors": count_errors(),
        },
        "engagement": {
            "avg_messages_per_conversation": calculate_avg_messages(),
            "followup_rate": calculate_followup_rate(),
        }
    }
```

## Baseline Comparison Dashboard

Create dashboard comparing v2 vs baseline:

```python
def get_baseline_comparison(date: date) -> dict:
    """Compare v2 metrics vs baseline"""

    baseline = get_baseline_metrics()
    v2_metrics = get_v2_metrics(date)

    return {
        "latency": {
            "baseline_p50": baseline["p50_latency_ms"],
            "v2_p50": v2_metrics["p50_latency_ms"],
            "delta_p50": v2_metrics["p50_latency_ms"] - baseline["p50_latency_ms"],
            "delta_p50_pct": ((v2_metrics["p50_latency_ms"] - baseline["p50_latency_ms"]) / baseline["p50_latency_ms"]) * 100,
        },
        "cost": {
            "baseline_avg": baseline["avg_cost"],
            "v2_avg": v2_metrics["avg_cost"],
            "delta": v2_metrics["avg_cost"] - baseline["avg_cost"],
            "delta_pct": ((v2_metrics["avg_cost"] - baseline["avg_cost"]) / baseline["avg_cost"]) * 100,
        },
        "errors": {
            "baseline_rate": baseline["error_rate"],
            "v2_rate": v2_metrics["error_rate"],
            "delta": v2_metrics["error_rate"] - baseline["error_rate"],
        }
    }
```

## Acceptance Criteria

Baseline collection is complete when:

- [ ] Minimum 1,000 requests collected
- [ ] Minimum 7 days of data
- [ ] All key metrics captured
- [ ] Baseline report generated
- [ ] Comparison dashboard created
- [ ] Team review and approval of baseline

## Targets for Coach v2

Based on baseline, Coach v2 should:

### Performance
- **Latency**: ≤ baseline + 20% (acceptable regression)
- **Error Rate**: ≤ baseline (no regression allowed)

### Cost
- **Cost Per Conversation**: ≤ baseline (ideally 10-20% reduction)
- **Daily Cost**: ≤ baseline (with same traffic)

### Quality
- **User Engagement**: ≥ baseline (maintain or improve)
- **Response Quality**: ≥ baseline (if measurable)

## Related Documents

- `docs/coach-architecture/phase-0/CostTracker_Spec.md` - Cost tracking implementation
- `docs/coach-architecture/phase-0/ObservabilityInfrastructure.md` - Metrics infrastructure
