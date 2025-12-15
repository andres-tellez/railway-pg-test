"""
Intent Classifier for Coach system.

Classifies user questions into intent categories with confidence scores.
Uses rules-based classification first, with fallback options for uncertain cases.

Usage:
    >>> classifier = IntentClassifier()
    >>> result = classifier.classify("How did my long run go?")
    >>> print(result.intent)  # "workout_review"
    >>> print(result.confidence)  # 0.75
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum

from coach.utils.constants import ClassificationMethod

# Confidence scoring constants
DEFAULT_CONFIDENCE_EMPTY = 0.3
DEFAULT_CONFIDENCE_VAGUE = 0.5
DEFAULT_CONFIDENCE_NO_MATCH = 0.4
CONFIDENCE_BASE_SINGLE_MATCH = 0.75
CONFIDENCE_BASE_TWO_MATCHES = 0.85
CONFIDENCE_BASE_MULTIPLE_MATCHES = 0.95
CONFIDENCE_MIN = 0.5
CONFIDENCE_MAX = 0.95

# Boost factors for priority intents
INJURY_BOOST_FACTOR = 1.2
WORKOUT_REVIEW_BOOST_FACTOR = 1.1


class Intent(Enum):
    """Valid intent types."""

    WORKOUT_REVIEW = "workout_review"
    THIS_WEEK_PLAN = "this_week_plan"
    PLAN_ADJUSTMENT_REQUEST = "plan_adjustment_request"
    PROGRESS_CHECK = "progress_check"
    INJURY_OR_SYMPTOM = "injury_or_symptom"
    GENERAL_EDUCATION = "general_education"
    MOTIVATION_SUPPORT = "motivation_support"


@dataclass
class IntentClassificationResult:
    """Result of intent classification."""

    intent: str
    confidence: float
    method: str  # "rules", "embeddings", "llm"


class IntentClassifier:
    """
    Classifies user questions into intent categories.

    Uses rules-based classification first, with fallback to embeddings
    or lightweight LLM for uncertain cases.
    """

    def __init__(self):
        """Initialize intent classifier with patterns."""
        self._build_patterns()

    def _build_patterns(self):
        """Build regex patterns for each intent type."""

        # Workout review patterns
        self.workout_review_patterns = [
            r"\b(how).*?(did|was).*?(my|the).*?(run|workout|training|long run|tempo|interval|race).*?(go|perform|feel|do)\b",
            r"\b(how).*?(do|performed).*?(on|in).*?(my|the).*?(run|workout)\b",
            r"\b(review|analyze|what did you think).*?(my|the|of).*?(run|workout|long run)\b",
            r"\b(tell me about).*?(my|the).*?(run|workout)\b",  # Must match "tell me about" + "my/the" + "run/workout"
            r"\b(how).*?(was).*?(my|the).*?(run|workout).*?(today|yesterday|recent)\b",
        ]

        # This week plan patterns
        self.this_week_plan_patterns = [
            r"\b(what).*?(my|is my|'s my).*?(plan|schedule|workouts?|training plan).*?(this week|for this week|week)\b",
            r"\b(what).*?(workouts?|plan|schedule).*?(do i|have i).*?(this week|for this week)\b",
            r"\b(show|tell).*?(me).*?(my|the).*?(plan|schedule|workouts?|training plan).*?(this week|for this week)\b",
            r"\b(what).*?(should i|do i|am i).*?(run|do).*?(this week)\b",
            r"\b(this week).*?(plan|schedule|workout|training)",
            r"\b(what).*?(on|in).*?(my|the).*?(schedule).*?(this week)\b",
        ]

        # Progress check patterns (must be specific to avoid false positives)
        self.progress_check_patterns = [
            r"\b(how).*?(am i|are things).*?(going|doing)\b",
            r"\b(am i).*?(on track|doing well)\b",
            r"\b(how).*?(is|'s).*?(my|the).*?(training|progress).*?(going)\b",
            r"\b(how'?s).*?(my|the).*?(progress)\b",
            # Don't match "tell me about" or "tell me about my run" - too specific
        ]

        # Injury/symptom patterns
        self.injury_patterns = [
            r"\b(chest|heart).*?(pain|tight|pressure|discomfort)",
            r"\b(knee|leg|foot|ankle|hip|back).*?(hurt|pain|ache|sore)",
            r"\b(dizzy|lightheaded|fainted|blacked out|dizziness)",
            r"\b(experiencing|have|feel|feeling).*?(dizzy|lightheaded|numb|tingling|sharp pain|stabbing pain)",
            r"\b(numb|tingling|sharp pain|stabbing).*?(in|on)\b",
            r"\b(can'?t|cannot).*?(breathe|walk|run)",
            r"\b(swelling|swollen|injury)",
            r"\b(i have|i'm|i am).*?(pain|hurt|ache)",
        ]

        # General education patterns
        self.education_patterns = [
            r"\b(what|explain|how).*?(is|are|do|should|calculate)\b",
            r"\b(what|explain).*?(zone|heart rate|pace|tapering|80/20)",
            r"\b(how).*?(calculate|determine|find)\b",
        ]

        # Motivation support patterns
        self.motivation_patterns = [
            r"\b(feel|feeling).*?(discouraged|unmotivated|struggling|down)",
            r"\b(need|want).*?(motivation|support|help|encouragement)",
            r"\b(giving up|quit|struggling)",
            r"\b(help).*?(stay|me).*?(motivated)",
            r"\b(stay|keep).*?(motivated)",
        ]

        # Plan adjustment patterns
        self.plan_adjustment_patterns = [
            r"\b(can|could|would).*?(adjust|change|modify|update).*?(plan|schedule)",
            r"\b(need|want).*?(to|to change).*?(plan|schedule|workout)",
            r"\b(adjust|change|modify).*?(plan|schedule|training)",
        ]

        # Vague question indicators (must be standalone, not part of specific phrases)
        self.vague_indicators = [
            r"^\s*(how am i|how are things|what's up)\s*$",  # Only at start/end
            r"^\s*(help|hi|hello)\s*$",
            # Don't match "tell me" - it's too often part of specific questions
        ]

    def classify(self, message: str) -> IntentClassificationResult:
        """
        Classify user message into intent category.

        Args:
            message: User's message/question

        Returns:
            IntentClassificationResult with intent, confidence, and method
        """
        if not message or not message.strip():
            return IntentClassificationResult(
                intent=Intent.GENERAL_EDUCATION.value,
                confidence=DEFAULT_CONFIDENCE_EMPTY,
                method=ClassificationMethod.RULES.value,
            )

        message_lower = message.lower().strip()

        # Check for vague questions first
        is_vague = any(
            re.search(pattern, message_lower, re.IGNORECASE)
            for pattern in self.vague_indicators
        )

        if is_vague:
            # Vague questions get progress_check with low confidence
            return IntentClassificationResult(
                intent=Intent.PROGRESS_CHECK.value,
                confidence=DEFAULT_CONFIDENCE_VAGUE,
                method=ClassificationMethod.RULES.value,
            )

        # Try each intent category (order matters for priority)
        intent_scores: List[Tuple[str, float]] = []

        # Injury/symptom (check FIRST - highest priority for safety)
        score = self._score_patterns(message_lower, self.injury_patterns)
        if score > 0:
            intent_scores.append(
                (
                    Intent.INJURY_OR_SYMPTOM.value,
                    min(score * INJURY_BOOST_FACTOR, CONFIDENCE_MAX),
                )
            )

        # This week plan (check before workout review to avoid conflicts)
        score = self._score_patterns(message_lower, self.this_week_plan_patterns)
        if score > 0:
            intent_scores.append((Intent.THIS_WEEK_PLAN.value, score))

        # Workout review (boost confidence slightly for specificity)
        score = self._score_patterns(message_lower, self.workout_review_patterns)
        if score > 0:
            intent_scores.append(
                (
                    Intent.WORKOUT_REVIEW.value,
                    min(score * WORKOUT_REVIEW_BOOST_FACTOR, CONFIDENCE_MAX),
                )
            )

        # Plan adjustment
        score = self._score_patterns(message_lower, self.plan_adjustment_patterns)
        if score > 0:
            intent_scores.append((Intent.PLAN_ADJUSTMENT_REQUEST.value, score))

        # Progress check (only if workout_review didn't match)
        # Check if workout review already matched - if so, skip progress check to avoid conflicts
        workout_review_matched = any(
            intent == Intent.WORKOUT_REVIEW.value for intent, _ in intent_scores
        )
        if not workout_review_matched:
            score = self._score_patterns(message_lower, self.progress_check_patterns)
            if score > 0:
                intent_scores.append((Intent.PROGRESS_CHECK.value, score))

        # Motivation support
        score = self._score_patterns(message_lower, self.motivation_patterns)
        if score > 0:
            intent_scores.append((Intent.MOTIVATION_SUPPORT.value, score))

        # General education
        score = self._score_patterns(message_lower, self.education_patterns)
        if score > 0:
            intent_scores.append((Intent.GENERAL_EDUCATION.value, score))

        # If we have matches, return the highest confidence one
        if intent_scores:
            intent_scores.sort(key=lambda x: x[1], reverse=True)
            best_intent, best_confidence = intent_scores[0]

            # Confidence is already in good range from _score_patterns
            # Just ensure it's within bounds
            confidence = min(max(best_confidence, CONFIDENCE_MIN), CONFIDENCE_MAX)

            return IntentClassificationResult(
                intent=best_intent,
                confidence=confidence,
                method=ClassificationMethod.RULES.value,
            )

        # No patterns matched - default to general education with low confidence
        return IntentClassificationResult(
            intent=Intent.GENERAL_EDUCATION.value,
            confidence=DEFAULT_CONFIDENCE_NO_MATCH,
            method=ClassificationMethod.RULES.value,
        )

    def _score_patterns(self, message: str, patterns: List[str]) -> float:
        """
        Score message against a list of patterns.

        Args:
            message: Lowercase message text
            patterns: List of regex patterns

        Returns:
            Score between 0.0 and 1.0
        """
        matches = sum(
            1 for pattern in patterns if re.search(pattern, message, re.IGNORECASE)
        )

        if matches == 0:
            return 0.0

        # Base score increases with number of matching patterns
        if matches == 1:
            base_score = CONFIDENCE_BASE_SINGLE_MATCH
        elif matches == 2:
            base_score = CONFIDENCE_BASE_TWO_MATCHES
        else:
            base_score = CONFIDENCE_BASE_MULTIPLE_MATCHES

        return base_score
