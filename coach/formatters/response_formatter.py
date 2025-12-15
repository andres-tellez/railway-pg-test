"""
ResponseFormatter for Coach system.

Validates and formats LLM responses for the Coach.
"""

import re
from typing import Dict, List, Any, Optional

from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity


class ResponseFormatter:
    """
    Formats and validates LLM responses for the Coach.

    Provides:
    - Response validation (structure, safety)
    - Section extraction (if structured format is used)
    - Fallback handling for malformed responses
    """

    # Common section markers (if LLM uses structured format)
    SECTION_MARKERS = {
        "summary": [r"##?\s*Summary", r"^Summary[:\-]", r"^# Summary"],
        "action_steps": [
            r"##?\s*Action\s+Steps?",
            r"^Action\s+Steps?[:\-]",
            r"^# Action Steps",
        ],
        "guidance": [r"##?\s*Guidance", r"^Guidance[:\-]", r"^# Guidance"],
        "safety_note": [r"##?\s*Safety", r"^Safety\s+Note[:\-]", r"⚠️", r"WARNING"],
    }

    # Unsafe content patterns (basic check)
    UNSAFE_PATTERNS = [
        r"ignore\s+safety",
        r"train\s+through\s+pain",
        r"ignore\s+medical",
        r"don'?t\s+see\s+a\s+doctor",
    ]

    def __init__(self):
        """Initialize ResponseFormatter."""
        pass

    def format(self, raw_response: str, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Format and validate LLM response.

        Args:
            raw_response: Raw response text from LLM
            intent: Optional intent (for context-aware formatting)

        Returns:
            Formatted response dict with:
            - content: Main response content
            - sections: Extracted sections (if any)
            - is_valid: Whether response structure is valid
            - warnings: Any warnings about the response
        """
        try:
            if not raw_response or not raw_response.strip():
                return self._create_fallback_response("Empty response from coach")

            # Clean response (remove markdown code fences if present)
            cleaned_response = self._clean_response(raw_response)

            # Validate structure
            is_valid, validation_issues = self._validate_structure(cleaned_response)

            # Extract sections if structured format is detected
            sections = self._extract_sections(cleaned_response)

            # Check for unsafe content
            safety_warnings = self._check_safety(cleaned_response, intent)

            # Build formatted response
            formatted = {
                "content": cleaned_response,
                "is_valid": is_valid,
                "sections": sections,
                "warnings": validation_issues + safety_warnings,
            }

            # If response is invalid and has warnings, use fallback if severe
            if not is_valid and any("critical" in w.lower() for w in validation_issues):
                return self._create_fallback_response(
                    "Response validation failed",
                    original_content=cleaned_response,
                )

            return formatted

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.MEDIUM,
                component="ResponseFormatter.format",
                metadata={
                    "intent": intent,
                    "response_length": len(raw_response) if raw_response else 0,
                },
            )
            return self._create_fallback_response(
                f"Error formatting response: {str(e)}"
            )

    def validate_structure(self, response: str) -> bool:
        """
        Validate response structure.

        Args:
            response: Response text to validate

        Returns:
            True if structure is valid, False otherwise
        """
        is_valid, _ = self._validate_structure(response)
        return is_valid

    def extract_sections(self, response: str) -> Dict[str, str]:
        """
        Extract sections from structured response.

        Args:
            response: Response text

        Returns:
            Dict mapping section names to content
        """
        return self._extract_sections(response)

    def _clean_response(self, response: str) -> str:
        """
        Clean response text (remove markdown fences, extra whitespace).

        Args:
            response: Raw response

        Returns:
            Cleaned response
        """
        # Remove markdown code fences
        cleaned = re.sub(
            r"^```(?:markdown|text)?\s*\n", "", response.strip(), flags=re.MULTILINE
        )
        cleaned = re.sub(r"\n```\s*$", "", cleaned.strip(), flags=re.MULTILINE)

        # Remove excessive blank lines (more than 2 consecutive)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    def _validate_structure(self, response: str) -> tuple[bool, List[str]]:
        """
        Validate response structure.

        Args:
            response: Response text

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check minimum length
        if len(response) < 10:
            issues.append("Response too short (less than 10 characters)")
            return False, issues

        # Check for common error patterns
        if re.search(r"\[ERROR\]", response, re.IGNORECASE):
            issues.append("Response contains error marker")
            return False, issues

        if re.search(
            r"error\s+occurred|failed\s+to|unable\s+to", response, re.IGNORECASE
        ):
            issues.append("Response may indicate an error")

        # Check for excessive repetition (could indicate truncated or broken response)
        words = response.split()
        if len(words) > 0:
            unique_words = len(set(words))
            if unique_words / len(words) < 0.3 and len(words) > 50:
                issues.append("Response may have excessive repetition")

        is_valid = len([i for i in issues if "critical" in i.lower()]) == 0
        return is_valid, issues

    def _extract_sections(self, response: str) -> Dict[str, str]:
        """
        Extract structured sections from response.

        Args:
            response: Response text

        Returns:
            Dict mapping section names to content
        """
        sections = {}

        # Look for section markers
        for section_name, patterns in self.SECTION_MARKERS.items():
            for pattern in patterns:
                match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
                if match:
                    # Extract content after marker until next section or end
                    start_pos = match.end()

                    # Find next section marker
                    next_section_pos = len(response)
                    for other_section, other_patterns in self.SECTION_MARKERS.items():
                        if other_section != section_name:
                            for other_pattern in other_patterns:
                                other_match = re.search(
                                    other_pattern,
                                    response[start_pos:],
                                    re.IGNORECASE | re.MULTILINE,
                                )
                                if other_match:
                                    next_section_pos = min(
                                        next_section_pos,
                                        start_pos + other_match.start(),
                                    )

                    section_content = response[start_pos:next_section_pos].strip()
                    if section_content:
                        sections[section_name] = section_content
                    break  # Found section with first matching pattern

        return sections

    def _check_safety(self, response: str, intent: Optional[str] = None) -> List[str]:
        """
        Check response for unsafe content.

        Args:
            response: Response text
            intent: Optional intent for context-aware checking

        Returns:
            List of safety warnings
        """
        warnings = []

        response_lower = response.lower()

        # Check for unsafe patterns
        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, response_lower):
                warnings.append(f"Potential unsafe content detected: {pattern}")

        # For injury intent, ensure response doesn't encourage ignoring symptoms
        if intent == "injury_or_symptom":
            if not re.search(
                r"(?:see|consult|visit|talk to).*?(?:doctor|physician|medical|healthcare)",
                response_lower,
            ):
                if len(response) > 100:  # Only warn if response is substantial
                    warnings.append(
                        "Injury response may lack medical consultation recommendation"
                    )

        return warnings

    def _create_fallback_response(
        self, message: str, original_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create fallback response when formatting fails.

        Args:
            message: Fallback message
            original_content: Optional original content to preserve

        Returns:
            Fallback response dict
        """
        fallback_content = (
            "I apologize, but I'm having trouble processing that right now. "
            "Please try rephrasing your question or ask again."
        )

        if original_content and len(original_content) > 50:
            # If we have substantial original content, try to use it
            fallback_content = original_content

        return {
            "content": fallback_content,
            "is_valid": False,
            "sections": {},
            "warnings": [message],
            "is_fallback": True,
        }
