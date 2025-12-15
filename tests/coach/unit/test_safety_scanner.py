"""
Tests for SafetyScanner.

Tests verify that medical and safety red flags are correctly detected
with zero false negatives on critical flags and low false positive rates.
"""

import pytest
from coach.safety.safety_scanner import SafetyScanner, SafetyScanResult


class TestSafetyScannerCriticalFlags:
    """Test critical medical flag detection."""

    def test_chest_pain_flags(self):
        """Test all chest pain variations are detected."""
        scanner = SafetyScanner()

        test_cases = [
            "I had chest pain during my run",
            "Chest tightness after running",
            "I felt chest discomfort",
            "My chest had pressure",
            "chest pain",  # standalone
            "CHEST PAIN",  # uppercase
            "Chest Pain",  # mixed case
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"
            assert any(
                "chest" in flag.lower() for flag in result.flags
            ), f"No chest flag found for: {message}"

    def test_respiratory_flags(self):
        """Test breathing difficulty flags."""
        scanner = SafetyScanner()

        test_cases = [
            "I can't breathe properly",
            "I cannot breathe",
            "difficulty breathing",
            "shortness of breath",
            "trouble breathing",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_consciousness_loss_flags(self):
        """Test loss of consciousness flags."""
        scanner = SafetyScanner()

        test_cases = [
            "I blacked out",
            "I fainted during the run",
            "I passed out",
            "I lost consciousness",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_dizziness_flags(self):
        """Test dizziness and lightheadedness flags."""
        scanner = SafetyScanner()

        test_cases = [
            "I felt dizzy",
            "I'm experiencing dizziness",
            "I felt lightheaded",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_severe_pain_flags(self):
        """Test severe pain indicators."""
        scanner = SafetyScanner()

        test_cases = [
            "I have sharp pain in my leg",
            "stabbing pain in my knee",
            "severe pain",
            "excruciating pain",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_cardiac_events(self):
        """Test cardiac event terminology."""
        scanner = SafetyScanner()

        test_cases = [
            "I think I had a heart attack",
            "cardiac arrest",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_numbness_tingling(self):
        """Test numbness and tingling flags."""
        scanner = SafetyScanner()

        test_cases = [
            "I feel numbness in my foot",
            "tingling in my hands",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_mobility_flags(self):
        """Test inability to bear weight or walk."""
        scanner = SafetyScanner()

        test_cases = [
            "I can't bear weight on my leg",
            "I can't walk",
            "can't walk properly",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_heart_rate_flags(self):
        """Test dangerous heart rate patterns."""
        scanner = SafetyScanner()

        test_cases = [
            "My heart rate spiked to 200",
            "Heart rate exceeded 200 bpm",
            "HR hit 200",
            "heart rate over 200",
            "My heart rate went over 200",
            "Heart rate: 200+",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_heart_rhythm_flags(self):
        """Test heart rhythm abnormalities."""
        scanner = SafetyScanner()

        test_cases = [
            "My heart is racing",
            "heart palpitations",
            "irregular heartbeat",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "critical", f"Wrong severity for: {message}"

    def test_joint_swelling(self):
        """Test joint swelling flag."""
        scanner = SafetyScanner()

        message = "My knee has joint swelling"
        result = scanner.scan(message)
        assert result.has_medical_red_flag is True
        assert result.severity == "critical"


class TestSafetyScannerModerateFlags:
    """Test moderate severity flags."""

    def test_persistent_pain(self):
        """Test persistent/chronic pain flags."""
        scanner = SafetyScanner()

        test_cases = [
            "I have persistent knee pain",
            "pain that won't go away",
            "chronic pain in my back",
            "nagging pain",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "moderate", f"Wrong severity for: {message}"

    def test_general_injury_terms(self):
        """Test general injury terminology."""
        scanner = SafetyScanner()

        test_cases = [
            "I have an injury",
            "I'm hurt",
            "I strained my calf",
            "pulled muscle",
            "tendon pain",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed to flag: {message}"
            assert result.severity == "moderate", f"Wrong severity for: {message}"


class TestSafetyScannerFalsePositives:
    """Test that normal running phrases don't trigger false positives."""

    def test_no_false_positives(self):
        """Test common running phrases don't trigger flags."""
        scanner = SafetyScanner()

        false_positive_cases = [
            "I felt great during my run",
            "My heart rate was in zone 2",
            "I ran at a comfortable pace",
            "My legs feel tired but good",
            "I pushed through the last mile",
            "My breathing was steady",
            "I had a good workout",
            "The run went well",
            "I'm feeling strong",
            "My pace was good",
            "I ran 5 miles today",
            "I did intervals today",
            "My heart rate averaged 150",
            "I felt comfortable at pace",
        ]

        for message in false_positive_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is False, f"False positive: {message}"

    def test_normal_heart_rate_mentions(self):
        """Test that normal HR mentions don't flag."""
        scanner = SafetyScanner()

        normal_cases = [
            "My heart rate was 180",
            "HR was 150",
            "Average HR: 165",
            "My heart rate was around 140",
        ]

        for message in normal_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is False, f"False positive: {message}"


class TestSafetyScannerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_message(self):
        """Empty message should not flag."""
        scanner = SafetyScanner()
        result = scanner.scan("")
        assert result.has_medical_red_flag is False
        assert result.flags == []
        assert result.severity is None

    def test_very_long_message(self):
        """Long messages should still be scanned efficiently."""
        scanner = SafetyScanner()
        long_message = "I went for a run. " * 1000 + "I had chest pain."
        result = scanner.scan(long_message)
        assert result.has_medical_red_flag is True
        assert "chest" in " ".join(result.flags).lower()

    def test_case_insensitivity(self):
        """Test that flags are detected regardless of case."""
        scanner = SafetyScanner()

        test_cases = [
            "CHEST PAIN",
            "Chest Pain",
            "chest pain",
            "cHeSt PaIn",
        ]

        for message in test_cases:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Failed for: {message}"

    def test_multiple_flags(self):
        """Test multiple flags in one message."""
        scanner = SafetyScanner()

        message = "I had chest pain and then blacked out"
        result = scanner.scan(message)
        assert result.has_medical_red_flag is True
        assert len(result.flags) >= 2
        # Should have both flags
        flags_lower = " ".join(result.flags).lower()
        assert "chest" in flags_lower
        assert "black" in flags_lower or "faint" in flags_lower

    def test_flag_in_context(self):
        """Test flags are detected even when embedded in longer context."""
        scanner = SafetyScanner()

        message = "I went for a nice long run today. Everything was great until I had chest pain at mile 5. I stopped immediately."
        result = scanner.scan(message)
        assert result.has_medical_red_flag is True
        assert result.severity == "critical"


class TestSafetyScannerPatterns:
    """Test regex pattern matching for complex cases."""

    def test_heart_rate_patterns(self):
        """Test HR > 200 pattern matching."""
        scanner = SafetyScanner()

        should_flag = [
            "My heart rate exceeded 200 bpm",
            "Heart rate over 200",
            "HR hit 200",
            "heart rate: 200+",
            "HR went over 200",
        ]

        should_not_flag = [
            "My HR was 180",  # Not over 200
            "Average heart rate: 150",
            "HR: 195 bpm",
        ]

        for message in should_flag:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is True, f"Should flag: {message}"

        for message in should_not_flag:
            result = scanner.scan(message)
            assert result.has_medical_red_flag is False, f"Should not flag: {message}"


class TestSafetyScannerPerformance:
    """Test performance requirements."""

    def test_scan_performance(self):
        """SafetyScanner must be fast (< 50ms)."""
        import time

        scanner = SafetyScanner()

        message = "I went for a long run today and felt great"

        start = time.time()
        result = scanner.scan(message)
        elapsed = (time.time() - start) * 1000  # ms

        assert elapsed < 50, f"SafetyScanner too slow: {elapsed:.1f}ms"
        assert result is not None

    def test_scan_large_message_performance(self):
        """Test performance on large messages."""
        import time

        scanner = SafetyScanner()

        large_message = "I went for a run. " * 10000  # ~200KB

        start = time.time()
        result = scanner.scan(large_message)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 100, f"Large message scan too slow: {elapsed:.1f}ms"
        assert result is not None
