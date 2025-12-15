# Safety Scanner Test Plan

**Version:** 1.0
**Owner:** Engineering + Safety Team
**Status:** Approved
**Last Updated:** 2025-01-15

## Overview

This document defines the comprehensive testing strategy for SafetyScanner to ensure it correctly identifies medical and safety red flags while maintaining low false positive rates.

## Testing Objectives

1. **Detect All Medical Red Flags**: Zero false negatives on critical medical phrases
2. **Minimize False Positives**: Keep false positive rate < 1%
3. **Handle Edge Cases**: Test boundary conditions and ambiguous language
4. **Validate Shadow Mode**: Ensure dual-mode safety checking works correctly
5. **Performance**: SafetyScanner must run in < 50ms per request

## Medical Red Flag Dictionary

### Critical Flags (Immediate Medical Attention)

```python
CRITICAL_FLAGS = [
    "chest pain",
    "chest tightness",
    "chest discomfort",
    "chest pressure",
    "heart attack",
    "cardiac arrest",
    "can't breathe",
    "difficulty breathing",
    "shortness of breath",
    "trouble breathing",
    "dizziness",
    "lightheaded",
    "fainted",
    "blacked out",
    "passed out",
    "lost consciousness",
    "numbness",
    "tingling",
    "sharp pain",
    "stabbing pain",
    "severe pain",
    "excruciating pain",
    "joint swelling",
    "can't bear weight",
    "can't walk",
    "heart rate spiked to 200",
    "heart racing",
    "heart palpitations",
    "irregular heartbeat",
]
```

### Moderate Flags (Medical Consultation Recommended)

```python
MODERATE_FLAGS = [
    "persistent pain",
    "pain that won't go away",
    "chronic pain",
    "nagging pain",
    "discomfort",
    "soreness that lasts",
    "injury",
    "hurt",
    "strained",
    "pulled muscle",
    "tendon pain",
]
```

### Pattern-Based Detection

Some flags require context:

```python
PATTERN_FLAGS = [
    r"heart rate.*(?:200|over 200|exceeded 200)",
    r"(?:chest|heart).*(?:pain|tight|uncomfortable|pressure)",
    r"(?:can'?t|cannot).*(?:breathe|breath)",
    r"(?:fainted|blacked out|passed out|lost consciousness)",
]
```

## Test Categories

### 1. Unit Tests

#### 1.1 Synthetic Test Cases

**Test Suite: `test_safety_scanner_unit.py`**

```python
def test_critical_flags():
    """Test all critical medical flags are detected"""

    test_cases = [
        ("I had chest pain during my run", ["chest pain"]),
        ("After sprinting I blacked out", ["blacked out"]),
        ("I can't breathe properly", ["can't breathe"]),
        ("Heart rate spiked to 200", ["heart rate spiked to 200"]),
        ("My knee has sharp pain", ["sharp pain"]),
    ]

    for message, expected_flags in test_cases:
        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] is True
        assert set(expected_flags).issubset(set(result["flags"]))

def test_no_false_positives():
    """Test common running phrases don't trigger false positives"""

    false_positive_cases = [
        "I felt great during my run",
        "My heart rate was in zone 2",
        "I ran at a comfortable pace",
        "My legs feel tired but good",
        "I pushed through the last mile",
        "My breathing was steady",
    ]

    for message in false_positive_cases:
        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] is False, f"False positive: {message}"

def test_moderate_flags():
    """Test moderate flags are detected but categorized correctly"""

    moderate_cases = [
        ("I have persistent knee pain", ["persistent pain"]),
        ("My calf is strained", ["strained"]),
    ]

    for message, expected_flags in moderate_cases:
        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] is True
        assert result["severity"] == "moderate"

def test_pattern_matching():
    """Test regex patterns catch variations"""

    pattern_cases = [
        ("My heart rate exceeded 200 bpm", True),
        ("Heart rate over 200", True),
        ("HR hit 200", True),
        ("My HR was 180", False),  # Not over 200
    ]

    for message, should_flag in pattern_cases:
        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] == should_flag

def test_case_insensitivity():
    """Test flags are detected regardless of case"""

    test_cases = [
        "CHEST PAIN",
        "Chest Pain",
        "chest pain",
        "cHeSt PaIn",
    ]

    for message in test_cases:
        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] is True

def test_multiple_flags():
    """Test multiple flags in one message"""

    message = "I had chest pain and then blacked out"
    result = SafetyScanner.scan(message)
    assert result["has_medical_red_flag"] is True
    assert "chest pain" in result["flags"]
    assert "blacked out" in result["flags"]
    assert len(result["flags"]) >= 2
```

#### 1.2 Edge Cases

```python
def test_empty_message():
    """Empty message should not flag"""
    result = SafetyScanner.scan("")
    assert result["has_medical_red_flag"] is False

def test_very_long_message():
    """Long messages should still be scanned efficiently"""
    long_message = "I went for a run. " * 1000 + "I had chest pain."
    result = SafetyScanner.scan(long_message)
    assert result["has_medical_red_flag"] is True

def test_unicode_characters():
    """Unicode characters should not break detection"""
    message = "I had chëst pâin 😰"
    result = SafetyScanner.scan(message)
    assert result["has_medical_red_flag"] is True

def test_flag_in_url():
    """Flags in URLs should not trigger (if URL is parsed out)"""
    message = "Check out https://example.com/chest-pain-info"
    result = SafetyScanner.scan(message)
    # Decision: Should we flag URLs? Probably not for safety scanner
    # But document the decision
```

### 2. Integration Tests with Anonymized Data

#### 2.1 Anonymization Process

**Step 1: Extract Sample Messages**

```python
def extract_sample_messages(limit: int = 1000) -> List[str]:
    """Extract recent user messages from database"""
    query = """
        SELECT content
        FROM conversation_messages
        WHERE role = 'user'
        ORDER BY created_at DESC
        LIMIT :limit
    """
    # Execute query
    return messages
```

**Step 2: Detect and Remove PII**

```python
import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

def anonymize_message(message: str) -> str:
    """Remove PII from message"""

    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    # Detect PII
    results = analyzer.analyze(
        text=message,
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"],
        language="en"
    )

    # Anonymize
    anonymized = anonymizer.anonymize(
        text=message,
        analyzer_results=results
    )

    return anonymized.text
```

**Step 3: Manual Review**

- Review 10% of anonymized messages manually
- Verify no PII remains
- Verify semantic meaning preserved

**Step 4: Store Test Corpus**

Store anonymized test corpus in separate location:
- `tests/fixtures/anonymized_messages.json`
- Never commit to main branch
- Store in secure test data repository

#### 2.2 Integration Test Suite

```python
def test_anonymized_message_corpus():
    """Test SafetyScanner on anonymized real messages"""

    corpus = load_anonymized_corpus("tests/fixtures/anonymized_messages.json")

    results = []
    for message in corpus:
        result = SafetyScanner.scan(message)
        results.append({
            "message": message,
            "flagged": result["has_medical_red_flag"],
            "flags": result["flags"],
        })

    # Analyze results
    flagged_count = sum(1 for r in results if r["flagged"])
    flag_rate = flagged_count / len(results)

    # Expected: < 5% flag rate (most messages are normal)
    assert flag_rate < 0.05, f"Flag rate too high: {flag_rate:.1%}"

    # Manual review of flagged messages
    flagged_messages = [r for r in results if r["flagged"]]
    log_for_manual_review(flagged_messages)
```

### 3. Shadow Mode Tests

#### 3.1 Dual Scanner Mode

```python
def test_shadow_mode_dual_scanner():
    """Test old scanner vs new scanner in shadow mode"""

    test_messages = load_test_messages()

    discrepancies = []

    for message in test_messages:
        old_result = old_safety_scanner.scan(message)
        new_result = new_safety_scanner.scan(message)

        if old_result["has_medical_red_flag"] != new_result["has_medical_red_flag"]:
            discrepancies.append({
                "message": message,
                "old_flagged": old_result["has_medical_red_flag"],
                "new_flagged": new_result["has_medical_red_flag"],
                "old_flags": old_result["flags"],
                "new_flags": new_result["flags"],
            })

    # Log discrepancies for review
    if discrepancies:
        log_discrepancies(discrepancies)
        # Alert if new scanner misses a flag that old scanner caught
        missed_flags = [
            d for d in discrepancies
            if d["old_flagged"] and not d["new_flagged"]
        ]
        if missed_flags:
            alert_safety_team(f"New scanner missed {len(missed_flags)} flags")
```

#### 3.2 Shadow Mode Alerting

```python
def test_shadow_mode_alerts():
    """Test that shadow mode alerts when new scanner misses flags"""

    # Simulate scenario where new scanner misses a flag
    message = "I had chest pain during my run"

    old_result = old_safety_scanner.scan(message)  # Flags: True
    new_result = new_safety_scanner.scan(message)  # Flags: False (bug)

    if old_result["has_medical_red_flag"] and not new_result["has_medical_red_flag"]:
        # This should trigger an alert
        assert shadow_mode_detected_discrepancy(message, old_result, new_result)
```

### 4. Performance Tests

```python
def test_scan_performance():
    """SafetyScanner must be fast (< 50ms)"""

    message = "I went for a long run today and felt great"

    import time
    start = time.time()
    result = SafetyScanner.scan(message)
    elapsed = (time.time() - start) * 1000  # ms

    assert elapsed < 50, f"SafetyScanner too slow: {elapsed:.1f}ms"
    assert result is not None

def test_scan_large_message():
    """Test performance on large messages"""

    large_message = "I went for a run. " * 10000  # ~200KB
    import time
    start = time.time()
    result = SafetyScanner.scan(large_message)
    elapsed = (time.time() - start) * 1000

    assert elapsed < 100, f"Large message scan too slow: {elapsed:.1f}ms"
```

### 5. Regression Tests

```python
def test_regression_known_flags():
    """Test that known flags are still detected after changes"""

    known_flags_file = "tests/fixtures/known_medical_flags.json"
    known_cases = load_json(known_flags_file)

    for case in known_cases:
        message = case["message"]
        expected_flags = case["expected_flags"]

        result = SafetyScanner.scan(message)
        assert result["has_medical_red_flag"] is True
        assert set(expected_flags).issubset(set(result["flags"]))
```

## Test Data Management

### Synthetic Test Data

Store in: `tests/fixtures/safety_scanner_test_cases.json`

```json
{
  "critical_flags": [
    {
      "message": "I had chest pain during my run",
      "expected_flags": ["chest pain"],
      "severity": "critical"
    }
  ],
  "false_positives": [
    {
      "message": "I felt great during my run",
      "should_flag": false
    }
  ]
}
```

### Anonymized Real Data

- **Storage**: Secure test data repository (not in main repo)
- **Access**: Limited to engineering team
- **Refresh**: Quarterly (with new anonymized samples)
- **Retention**: 1 year

## Test Execution

### CI/CD Integration

```yaml
# .github/workflows/safety-scanner-tests.yml
name: Safety Scanner Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run unit tests
        run: pytest tests/test_safety_scanner_unit.py
      - name: Run integration tests
        run: pytest tests/test_safety_scanner_integration.py
      - name: Run performance tests
        run: pytest tests/test_safety_scanner_performance.py
```

### Manual Test Execution

```bash
# Run all safety scanner tests
pytest tests/test_safety_scanner*.py -v

# Run with coverage
pytest tests/test_safety_scanner*.py --cov=safety_scanner --cov-report=html

# Run specific test category
pytest tests/test_safety_scanner_unit.py::test_critical_flags -v
```

## Test Metrics

### Key Metrics to Track

1. **Test Coverage**: Target > 95%
2. **False Negative Rate**: Target 0% (on critical flags)
3. **False Positive Rate**: Target < 1%
4. **Performance**: p95 < 50ms
5. **Regression Detection**: All known flags still detected

### Reporting

Generate test report after each run:

```python
def generate_test_report():
    """Generate comprehensive test report"""

    report = {
        "timestamp": datetime.utcnow(),
        "test_coverage": calculate_coverage(),
        "false_negative_rate": calculate_false_negatives(),
        "false_positive_rate": calculate_false_positives(),
        "performance_p95_ms": calculate_performance_p95(),
        "regression_count": count_regressions(),
    }

    return report
```

## Continuous Improvement

### Flag Dictionary Updates

When adding new flags:

1. Add to dictionary
2. Add test case
3. Run full test suite
4. Validate on anonymized corpus
5. Deploy with monitoring

### Periodic Review

- **Monthly**: Review false positives/false negatives
- **Quarterly**: Update test corpus with new anonymized data
- **Annually**: Comprehensive review of flag dictionary

## Related Documents

- `docs/coach-architecture/phase-0/ShadowModeExecutor.md` - Shadow mode testing
- `safety_scanner/red_flag_dictionary.yaml` - Flag dictionary source of truth
