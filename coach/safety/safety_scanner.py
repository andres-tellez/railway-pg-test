"""
Safety Scanner for Coach system.

Detects medical and safety red flags in user messages.
Zero false negatives on critical flags - safety first.

Usage:
    >>> scanner = SafetyScanner()
    >>> result = scanner.scan("I had chest pain during my run")
    >>> print(result.has_medical_red_flag)  # True
    >>> print(result.severity)  # "critical"
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from coach.utils.config import Config
from coach.utils.constants import ClassificationMethod


@dataclass
class SafetyScanResult:
    """Result of safety scan."""

    has_medical_red_flag: bool
    flags: List[str]
    severity: Optional[str]  # "critical", "moderate", or None
    method: str = "rules"  # "rules", "embeddings", "llm"


class SafetyScanner:
    """
    Scans user messages for medical and safety red flags.

    Zero tolerance for false negatives on critical flags.
    Prioritizes safety over specificity.

    Flags are loaded from config/safety_flags.yaml for easy updates.
    """

    def __init__(self):
        """Initialize safety scanner with flags from config and compiled patterns."""
        self._load_flags_from_config()
        self._build_patterns()

    def _load_flags_from_config(self):
        """Load safety flags from configuration file."""
        config = Config.get_safety_flags()

        # Load flags from config, with empty list as fallback
        self.critical_flags = config.get("critical_flags", [])
        self.moderate_flags = config.get("moderate_flags", [])

        # Load pattern flags from config
        pattern_configs = config.get("pattern_flags", [])
        self.pattern_flags = []
        for pattern_config in pattern_configs:
            if isinstance(pattern_config, dict):
                self.pattern_flags.append(
                    (
                        pattern_config.get("pattern", ""),
                        pattern_config.get("description", ""),
                    )
                )

    def _build_patterns(self):
        """Build and compile regex patterns for pattern-based flags."""
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), description)
            for pattern, description in self.pattern_flags
            if pattern  # Skip empty patterns
        ]

    def _matches_flag(self, message_lower: str, flag: str) -> bool:
        """
        Check if flag matches in message.

        Handles word boundary matching for better accuracy.
        Special handling for multi-word flags with optional words in between.

        Args:
            message_lower: Lowercase message text
            flag: Flag phrase to match

        Returns:
            True if flag is found in message
        """
        # For single words, use word boundary matching
        if len(flag.split()) == 1:
            # Use word boundary to avoid partial matches
            pattern = r"\b" + re.escape(flag) + r"\b"
            return bool(re.search(pattern, message_lower))
        else:
            # For phrases, check for exact match first
            if flag in message_lower:
                return True

            # Special handling for "heart racing" - allow words in between
            if flag == "heart racing":
                pattern = r"\bheart\b.*\bracing\b"
                return bool(re.search(pattern, message_lower, re.IGNORECASE))

            # For other phrases, simple substring match
            return flag in message_lower

    def scan(self, message: str) -> SafetyScanResult:
        """
        Scan message for medical and safety red flags.

        Args:
            message: User's message to scan

        Returns:
            SafetyScanResult with flags detected, severity, and method
        """
        if not message or not message.strip():
            return SafetyScanResult(
                has_medical_red_flag=False,
                flags=[],
                severity=None,
                method=ClassificationMethod.RULES.value,
            )

        message_lower = message.lower()
        detected_flags: Set[str] = set()
        severity_levels: Set[str] = set()

        # Check critical flags first (safety priority)
        for flag in self.critical_flags:
            if self._matches_flag(message_lower, flag):
                detected_flags.add(flag)
                severity_levels.add("critical")

        # Check moderate flags
        for flag in self.moderate_flags:
            if self._matches_flag(message_lower, flag):
                detected_flags.add(flag)
                # If "persistent" or "chronic" is found, check if it's in context of pain
                if flag in ("persistent", "chronic") and "pain" in message_lower:
                    detected_flags.add(f"{flag} pain")
                severity_levels.add("moderate")

        # Check pattern-based flags
        for pattern, description in self.compiled_patterns:
            if pattern.search(message):
                detected_flags.add(description)
                # Pattern flags are typically critical
                if (
                    "heart rate" in description.lower()
                    or "breathing" in description.lower()
                ):
                    severity_levels.add("critical")
                elif (
                    "chest" in description.lower()
                    or "consciousness" in description.lower()
                ):
                    severity_levels.add("critical")

        # Determine overall severity (critical takes precedence)
        if "critical" in severity_levels:
            overall_severity = "critical"
        elif "moderate" in severity_levels:
            overall_severity = "moderate"
        else:
            overall_severity = None

        has_flag = len(detected_flags) > 0

        return SafetyScanResult(
            has_medical_red_flag=has_flag,
            flags=list(detected_flags),
            severity=overall_severity,
            method=ClassificationMethod.RULES.value,
        )

    def scan_for_schema(self, message: str) -> Dict:
        """
        Scan message and return result in safety_flags schema format.

        Args:
            message: User's message to scan

        Returns:
            Dictionary matching safety_flags schema format
        """
        result = self.scan(message)

        safety_flags = {
            "has_medical_red_flag": result.has_medical_red_flag,
            "flags": result.flags,
        }

        # Only include severity if it's not None (schema doesn't allow null)
        if result.severity is not None:
            safety_flags["severity"] = result.severity

        return {
            "version": "1.0.0",
            "safety_flags": safety_flags,
        }
