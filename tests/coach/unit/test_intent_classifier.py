"""
Tests for IntentClassifier.

Tests verify that questions are correctly classified into intent categories
with appropriate confidence scores.
"""

import pytest
from coach.utils.intent_classifier import IntentClassifier, IntentClassificationResult


class TestIntentClassifier:
    """Test IntentClassifier functionality."""

    def test_classify_workout_review(self):
        """Test classifying workout review questions."""
        classifier = IntentClassifier()

        test_cases = [
            "How did my long run go?",
            "How was my workout today?",
            "Tell me about my run yesterday",
            "How did I do on my tempo run?",
            "Review my last run",
            "What did you think of my long run?",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "workout_review", f"Failed for: {message}"
            assert result.confidence > 0.7, f"Low confidence for: {message}"

    def test_classify_this_week_plan(self):
        """Test classifying plan questions."""
        classifier = IntentClassifier()

        test_cases = [
            "What's my plan this week?",
            "What workouts do I have this week?",
            "Show me my training plan for this week",
            "What's on my schedule this week?",
            "What should I run this week?",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "this_week_plan", f"Failed for: {message}"
            assert result.confidence > 0.7, f"Low confidence for: {message}"

    def test_classify_progress_check(self):
        """Test classifying progress check questions."""
        classifier = IntentClassifier()

        test_cases = [
            "How am I doing?",
            "How is my training going?",
            "Am I on track?",
            "How's my progress?",
            "How are things going?",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "progress_check", f"Failed for: {message}"

    def test_classify_injury_or_symptom(self):
        """Test classifying injury/symptom questions."""
        classifier = IntentClassifier()

        test_cases = [
            "I have chest pain",
            "My knee hurts",
            "I'm experiencing dizziness",
            "I have a sharp pain in my leg",
            "I feel numbness in my foot",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "injury_or_symptom", f"Failed for: {message}"
            assert result.confidence > 0.7, f"Low confidence for: {message}"

    def test_classify_vague_questions(self):
        """Test that vague questions get low confidence."""
        classifier = IntentClassifier()

        test_cases = [
            "How am I?",
            "Tell me something",
            "What's up?",
            "Help me",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            # Should classify, but with low confidence
            assert (
                result.confidence < 0.7
            ), f"Too high confidence for vague question: {message}"

    def test_classify_general_education(self):
        """Test classifying general education questions."""
        classifier = IntentClassifier()

        test_cases = [
            "What is zone 2 training?",
            "How do I calculate my max heart rate?",
            "Explain tapering",
            "What's the 80/20 rule?",
            "How should I fuel for a marathon?",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "general_education", f"Failed for: {message}"

    def test_classify_motivation_support(self):
        """Test classifying motivation/support questions."""
        classifier = IntentClassifier()

        test_cases = [
            "I'm feeling discouraged",
            "I need motivation",
            "Help me stay motivated",
            "I'm struggling with my training",
            "I feel like giving up",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "motivation_support", f"Failed for: {message}"

    def test_classify_plan_adjustment_request(self):
        """Test classifying plan adjustment requests."""
        classifier = IntentClassifier()

        test_cases = [
            "Can we adjust my plan?",
            "I need to change my schedule",
            "Can you modify my training plan?",
            "I want to adjust my workouts",
        ]

        for message in test_cases:
            result = classifier.classify(message)
            assert result.intent == "plan_adjustment_request", f"Failed for: {message}"

    def test_classify_case_insensitive(self):
        """Test that classification is case insensitive."""
        classifier = IntentClassifier()

        test_cases = [
            ("HOW DID MY RUN GO?", "workout_review"),
            ("how did my run go?", "workout_review"),
            ("How Did My Run Go?", "workout_review"),
        ]

        for message, expected_intent in test_cases:
            result = classifier.classify(message)
            assert result.intent == expected_intent, f"Failed for: {message}"

    def test_classify_empty_message(self):
        """Test handling empty messages."""
        classifier = IntentClassifier()

        result = classifier.classify("")
        # Should return default intent with low confidence
        assert result.intent is not None
        assert result.confidence < 0.5

    def test_classify_very_long_message(self):
        """Test handling very long messages."""
        classifier = IntentClassifier()

        long_message = "I went for a run. " * 100
        result = classifier.classify(long_message)

        # Should still classify, but might be lower confidence
        assert result.intent is not None
        assert result.confidence >= 0.0

    def test_classify_multiple_intents(self):
        """Test that message with multiple intent indicators gets highest confidence."""
        classifier = IntentClassifier()

        # Message mentions both workout and plan
        message = "How did my run go and what's my plan for this week?"
        result = classifier.classify(message)

        # Should pick one intent (the one with higher confidence)
        assert result.intent in ["workout_review", "this_week_plan"]
        assert result.confidence >= 0.6  # Allow equal to 0.6

    def test_vague_question_early_return(self):
        """Test that truly vague questions (exact matches) return early with progress_check intent."""
        classifier = IntentClassifier()

        # These exact phrases should trigger vague question detection and return early
        # Note: The vague indicator pattern uses ^ and $ anchors for exact matches
        vague_cases = [
            "how am i",  # lowercase, no punctuation
            "how are things",  # lowercase, no punctuation
            "what's up",  # lowercase, no punctuation
            "help",  # single word
            "hi",  # single word
            "hello",  # single word
        ]

        for message in vague_cases:
            result = classifier.classify(message)
            assert result.intent == "progress_check", f"Failed for: {message}"
            assert result.confidence == 0.5, f"Wrong confidence for: {message}"
            assert result.method == "rules", f"Wrong method for: {message}"
