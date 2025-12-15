# Observability Infrastructure Specification

**Version:** 1.0
**Owner:** Engineering Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This document specifies the observability infrastructure for the Coach system, including metrics, logs, traces, and dashboards. The system is tool-agnostic but provides concrete examples.

## Core Principles

1. **Comprehensive**: Track all critical metrics
2. **Low Cardinality**: Avoid metric explosion
3. **Real-Time**: Metrics available in real-time
4. **Actionable**: Alerts trigger on actionable conditions
5. **Cost-Aware**: Monitor cost metrics closely

## Metrics

### Metric Types

#### Histograms

For distributions (latency, cost, tokens):
- `coach.latency_ms` - Response latency
- `coach.cost_per_conversation` - Cost per request
- `coach.tokens_in` - Input tokens
- `coach.tokens_out` - Output tokens

#### Counters

For cumulative counts:
- `coach.request_count` - Total requests
- `coach.error_count` - Total errors (tagged by error_type)
- `coach.safety_flag_count` - Safety flags triggered

#### Gauges

For current values:
- `coach.daily_cost` - Daily cost total
- `coach.user_daily_cost` - Per-user daily cost (tagged by user_id)

### Metric Naming

**Format**: `coach.<component>.<metric>.<unit>`

**Examples**:
- `coach.latency_ms`
- `coach.cost_usd`
- `coach.tokens_in`
- `coach.error_count`
- `coach.shadow.v2.error_count`

### Metric Tagging Strategy

**Low-Cardinality Metrics** (no user_id tag):
- `coach.latency_ms` - Aggregated across all users
- `coach.error_count` - Aggregated with error_type tag only
- `coach.request_count` - Total count

**High-Cardinality Metrics** (user_id tag allowed):
- `coach.user_daily_cost` - Tagged by user_id (for per-user analysis)
- `coach.user_request_count` - Tagged by user_id (for abuse detection)

**Component Tags**:
- All metrics tagged by `component` (runner_state_builder, llm_client, etc.)

**Intent Tags**:
- Request metrics tagged by `intent` (workout_review, this_week_plan, etc.)

### Key Metrics

#### Performance Metrics

```python
# Latency (histogram)
metrics.histogram("coach.latency_ms", latency_ms, tags={
    "component": component_name,
    "intent": intent,
})

# Request count (counter)
metrics.increment("coach.request_count", tags={
    "component": component_name,
    "intent": intent,
})
```

#### Error Metrics

```python
# Error count (counter)
metrics.increment("coach.error_count", tags={
    "component": component_name,
    "error_type": error_type,
    "intent": intent,
})

# Error rate (calculated)
error_rate = error_count / request_count
metrics.gauge("coach.error_rate", error_rate, tags={
    "component": component_name,
})
```

#### Cost Metrics

```python
# Cost per conversation (histogram)
metrics.histogram("coach.cost_per_conversation", cost, tags={
    "model": model_name,
    "intent": intent,
})

# Daily cost (gauge)
metrics.gauge("coach.daily_cost", daily_cost)

# Per-user daily cost (gauge, high cardinality)
metrics.gauge("coach.user_daily_cost", user_cost, tags={
    "user_id": user_id,  # Only for cost tracking
})
```

#### Token Metrics

```python
# Input tokens (histogram)
metrics.histogram("coach.tokens_in", tokens_in, tags={
    "model": model_name,
    "intent": intent,
})

# Output tokens (histogram)
metrics.histogram("coach.tokens_out", tokens_out, tags={
    "model": model_name,
    "intent": intent,
})
```

#### Safety Metrics

```python
# Safety flags (counter)
metrics.increment("coach.safety_flag_count", tags={
    "flag_type": flag_type,
})

# Shadow mode discrepancies (counter)
metrics.increment("coach.shadow.discrepancy_count", tags={
    "type": "safety_flag_missed",
})
```

### Metric Export

#### Prometheus Example

```python
from prometheus_client import Histogram, Counter, Gauge

# Define metrics
coach_latency = Histogram(
    'coach_latency_ms',
    'Coach response latency in milliseconds',
    ['component', 'intent']
)

coach_errors = Counter(
    'coach_error_count',
    'Coach error count',
    ['component', 'error_type', 'intent']
)

coach_cost = Histogram(
    'coach_cost_usd',
    'Coach cost per conversation in USD',
    ['model', 'intent']
)

# Use metrics
coach_latency.labels(component='llm_client', intent='workout_review').observe(latency_ms)
coach_errors.labels(component='runner_state_builder', error_type='DatabaseError').inc()
coach_cost.labels(model='gpt-4o', intent='workout_review').observe(cost)
```

#### DataDog Example

```python
from datadog import statsd

# Use statsd
statsd.histogram('coach.latency_ms', latency_ms, tags=[
    f'component:{component_name}',
    f'intent:{intent}'
])

statsd.increment('coach.error_count', tags=[
    f'component:{component_name}',
    f'error_type:{error_type}'
])

statsd.gauge('coach.daily_cost', daily_cost)
```

## Logging

### Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General information about system operation
- **WARNING**: Warning messages for unusual conditions
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

### Log Structure

```python
import logging
import json

logger = logging.getLogger(__name__)

# Structured logging
logger.info(
    "Coach request completed",
    extra={
        "user_id": user_id,
        "conversation_id": conversation_id,
        "intent": intent,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost,
        "error": error_message if error else None,
    }
)
```

### Log Aggregation

- **Centralized**: All logs sent to central system (e.g., DataDog, ELK)
- **Searchable**: Structured logs enable easy searching
- **Retention**: 30 days for INFO, 90 days for ERROR+

## Tracing

### Distributed Tracing

For request flow tracking:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("coach.generate_response") as span:
    span.set_attribute("user_id", user_id)
    span.set_attribute("intent", intent)

    # Nested spans
    with tracer.start_as_current_span("runner_state.build") as sub_span:
        runner_state = build_runner_state(user_id)
        sub_span.set_attribute("phase", runner_state["phase"])
```

### Trace Attributes

- `user_id`: User identifier
- `conversation_id`: Conversation identifier
- `intent`: Request intent
- `component`: Component name
- `latency_ms`: Component latency
- `error`: Error message (if any)

## Dashboards

### Coach Quality Dashboard

**Metrics**:
- Response latency (p50, p95, p99)
- Error rate (by component, by intent)
- Request volume (over time)
- User engagement (follow-up rate)
- Response quality ratings (if available)

**Visualizations**:
- Latency trend over time
- Error rate by component
- Request distribution by intent
- Quality score over time

### Cost Dashboard

**Metrics**:
- Daily cost trend
- Cost per conversation (p50, p95, p99)
- Cost by model
- Cost by intent
- Top spenders (users)

**Visualizations**:
- Daily cost chart
- Cost breakdown by model
- Cost per conversation distribution
- User cost ranking

### Error Dashboard

**Metrics**:
- Error rate over time
- Error count by type
- Error count by component
- Error trends

**Visualizations**:
- Error rate chart
- Error type breakdown
- Component error heatmap
- Error timeline

### Safety Dashboard

**Metrics**:
- Safety flags triggered (by type)
- Shadow mode discrepancies
- Medical red flag rate

**Visualizations**:
- Safety flag trend
- Flag type breakdown
- Discrepancy alerts

## Alerts

### Alert Conditions

#### Critical Alerts (Immediate Response)

1. **Error Rate > 5%** (10-minute window)
   - Metric: `coach.error_rate`
   - Threshold: 0.05
   - Action: Page on-call engineer
   - Severity: CRITICAL

2. **Safety Flag Missed** (Shadow mode detects discrepancy)
   - Metric: `coach.shadow.discrepancy_count`
   - Threshold: > 0
   - Action: Alert safety team immediately
   - Severity: CRITICAL

#### High Alerts (Investigate Soon)

3. **Latency p95 > 10 seconds** (30-minute window)
   - Metric: `coach.latency_ms` (p95)
   - Threshold: 10000 ms
   - Action: Alert engineering team
   - Severity: HIGH

4. **Daily Cost > $200** (150% of baseline)
   - Metric: `coach.daily_cost`
   - Threshold: 200.0
   - Action: Alert + review top spenders
   - Severity: HIGH

#### Medium Alerts (Monitor)

5. **Cost Per Conversation > $0.10** (1-hour window)
   - Metric: `coach.cost_per_conversation` (avg)
   - Threshold: 0.10
   - Action: Log for investigation
   - Severity: MEDIUM

6. **User Daily Cost > $1.00**
   - Metric: `coach.user_daily_cost`
   - Threshold: 1.00
   - Action: Review user activity
   - Severity: MEDIUM

### Alert Implementation

#### Prometheus Alerting Rules

```yaml
groups:
  - name: coach_alerts
    rules:
      - alert: CoachHighErrorRate
        expr: rate(coach_error_count[10m]) / rate(coach_request_count[10m]) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Coach error rate > 5%"

      - alert: CoachHighLatency
        expr: histogram_quantile(0.95, coach_latency_ms) > 10000
        for: 30m
        labels:
          severity: high
        annotations:
          summary: "Coach p95 latency > 10 seconds"

      - alert: CoachHighCost
        expr: coach_daily_cost > 200
        labels:
          severity: high
        annotations:
          summary: "Coach daily cost > $200"
```

#### DataDog Monitors

```python
# Create monitor via API or UI
monitor = {
    "type": "metric alert",
    "query": "avg(last_10m):avg:coach.error_rate > 0.05",
    "name": "Coach High Error Rate",
    "message": "Coach error rate exceeded 5%",
    "options": {
        "thresholds": {
            "critical": 0.05
        },
        "notify_audit": True,
        "notify_no_data": False
    }
}
```

## Tool Selection

### Recommended Stack

**Option 1: Open Source**
- **Metrics**: Prometheus
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Tracing**: Jaeger
- **Dashboards**: Grafana

**Option 2: Managed Services**
- **Metrics & Logs**: DataDog
- **Tracing**: DataDog APM
- **Dashboards**: DataDog Dashboards

**Option 3: Cloud-Native**
- **Metrics**: CloudWatch (AWS) / Azure Monitor
- **Logging**: CloudWatch Logs / Azure Log Analytics
- **Tracing**: X-Ray (AWS) / Application Insights
- **Dashboards**: CloudWatch Dashboards / Azure Dashboards

### Decision Criteria

- **Team Expertise**: Choose stack team knows
- **Cost**: Managed vs self-hosted
- **Scale**: Current and projected volume
- **Integration**: Existing infrastructure

## Implementation

### Metrics Client Wrapper

```python
class MetricsClient:
    """Unified metrics client (abstracts underlying system)"""

    def histogram(self, metric_name: str, value: float, tags: dict = None):
        """Record histogram metric"""
        # Implementation depends on tool
        pass

    def counter(self, metric_name: str, value: int = 1, tags: dict = None):
        """Increment counter metric"""
        # Implementation depends on tool
        pass

    def gauge(self, metric_name: str, value: float, tags: dict = None):
        """Set gauge metric"""
        # Implementation depends on tool
        pass
```

### Usage in Code

```python
from coach.utils.metrics import metrics

# In LLMClient
metrics.histogram("coach.latency_ms", latency_ms, tags={
    "component": "llm_client",
    "intent": intent,
})

# In RunnerStateBuilder
metrics.counter("coach.request_count", tags={
    "component": "runner_state_builder",
})

# In CostTracker
metrics.gauge("coach.daily_cost", daily_cost)
```

## Related Documents

- `docs/coach-architecture/phase-0/CostTracker_Spec.md` - Cost tracking
- `docs/coach-architecture/phase-0/BaselineMetricsCollection.md` - Baseline metrics
