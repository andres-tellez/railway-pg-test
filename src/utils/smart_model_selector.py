# src/utils/smart_model_selector.py

import re
import logging
from typing import Tuple, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class QuestionComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class SmartModelSelector:
    """Intelligent model selection based on question complexity"""

    def __init__(self):
        # Define patterns for different complexity levels
        self.simple_patterns = [
            r"\b(what|when|where|how many|how much)\b.*\b(recently|today|this week|last week)\b",
            r"\b(show me|list|give me)\b.*\b(runs|activities|workouts)\b",
            r"\b(how far|how long|how fast)\b.*\b(did i run|was my|was the)\b",
            r"\b(what is|what was)\b.*\b(my|the)\b.*\b(longest|fastest|best)\b",
            r"\b(tell me about|describe)\b.*\b(my|the)\b.*\b(last|recent)\b",
            r"\b(how many miles|how many runs|how many workouts)\b",
            r"\b(what time|what pace|what distance)\b",
            r"\b(show|display|get)\b.*\b(data|stats|numbers)\b",
        ]

        self.complex_patterns = [
            r"\b(analyze|evaluate|assess|diagnose)\b.*\b(performance|training|progress)\b",
            r"\b(why|why is|why are|why did|why do)\b.*\b(my|the)\b",
            r"\b(what should|what would|what could|what might)\b.*\b(i|we|you)\b",
            r"\b(how can|how should|how would|how do)\b.*\b(i|we|you)\b.*\b(improve|optimize|enhance)\b",
            r"\b(compare|contrast|difference between)\b",
            r"\b(predict|forecast|project|estimate)\b",
            r"\b(explain|elaborate|detail|break down)\b.*\b(why|how|what)\b",
            r"\b(create|design|develop|plan)\b.*\b(strategy|approach|method|program)\b",
            r"\b(race preparation|training plan|periodization|tapering)\b",
            r"\b(heart rate|VO2|lactate|threshold|zones)\b.*\b(analysis|training|optimization)\b",
            r"\b(injury|recovery|overtraining|burnout)\b.*\b(prevention|management|treatment)\b",
            r"\b(nutrition|hydration|supplements|fueling)\b.*\b(strategy|plan|optimization)\b",
        ]

        # Strategic coaching keywords that require GPT-4
        self.strategic_keywords = [
            "periodization",
            "tapering",
            "peaking",
            "base building",
            "threshold",
            "VO2",
            "lactate",
            "aerobic",
            "anaerobic",
            "injury prevention",
            "recovery",
            "overtraining",
            "burnout",
            "race strategy",
            "pacing strategy",
            "nutrition",
            "hydration",
            "mental training",
            "visualization",
            "goal setting",
        ]

        # Question types that need GPT-4
        self.gpt4_question_types = [
            "strategic analysis",
            "performance optimization",
            "race preparation",
            "training periodization",
            "injury prevention",
            "recovery planning",
            "nutrition strategy",
            "mental training",
            "goal setting",
        ]

    def analyze_question_complexity(self, question: str) -> QuestionComplexity:
        """Analyze question complexity based on patterns and keywords"""

        question_lower = question.lower().strip()

        # Check for strategic keywords (always complex)
        for keyword in self.strategic_keywords:
            if keyword in question_lower:
                return QuestionComplexity.COMPLEX

        # Check complex patterns
        for pattern in self.complex_patterns:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return QuestionComplexity.COMPLEX

        # Check simple patterns
        for pattern in self.simple_patterns:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return QuestionComplexity.SIMPLE

        # Default to moderate for unclassified questions
        return QuestionComplexity.MODERATE

    def select_model(
        self, question: str, context_length: int = 0
    ) -> Tuple[str, str, Dict]:
        """
        Select the optimal model based on question complexity and context

        Returns:
            Tuple of (model_name, reasoning, metadata)
        """

        complexity = self.analyze_question_complexity(question)

        # Metadata for logging and analysis
        metadata = {
            "complexity": complexity.value,
            "question_length": len(question),
            "context_length": context_length,
            "has_strategic_keywords": any(
                keyword in question.lower() for keyword in self.strategic_keywords
            ),
        }

        # Model selection logic
        if complexity == QuestionComplexity.COMPLEX:
            model = "gpt-4o"
            reasoning = "Complex strategic question requiring advanced analysis"

        elif complexity == QuestionComplexity.SIMPLE:
            model = "gpt-3.5-turbo"
            reasoning = "Simple factual question suitable for efficient model"

        else:  # MODERATE
            # For moderate complexity, consider context length
            if context_length > 3000:  # Large context might need GPT-4
                model = "gpt-4o"
                reasoning = "Moderate complexity with large context requiring GPT-4"
            else:
                model = "gpt-3.5-turbo"
                reasoning = "Moderate complexity suitable for efficient model"

        logger.info(
            f"Model selection: {model} for question: '{question[:50]}...' - {reasoning}"
        )

        return model, reasoning, metadata

    def get_cost_estimate(
        self, model: str, input_tokens: int, output_tokens: int = 200
    ) -> float:
        """Get cost estimate for the selected model"""

        # Pricing as of 2024 (per 1K tokens)
        pricing = {
            "gpt-4o": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        }

        if model not in pricing:
            return 0.0

        input_cost = (input_tokens / 1000) * pricing[model]["input"]
        output_cost = (output_tokens / 1000) * pricing[model]["output"]

        return input_cost + output_cost

    def get_savings_estimate(self, question: str, context_tokens: int) -> Dict:
        """Estimate potential savings with smart model selection"""

        selected_model, _, metadata = self.select_model(question, context_tokens)

        # Calculate costs for both models
        gpt4_cost = self.get_cost_estimate("gpt-4o", context_tokens)
        gpt35_cost = self.get_cost_estimate("gpt-3.5-turbo", context_tokens)
        selected_cost = self.get_cost_estimate(selected_model, context_tokens)

        return {
            "selected_model": selected_model,
            "selected_cost": selected_cost,
            "gpt4_cost": gpt4_cost,
            "gpt35_cost": gpt35_cost,
            "savings_vs_gpt4": gpt4_cost - selected_cost,
            "savings_percentage": (
                ((gpt4_cost - selected_cost) / gpt4_cost * 100) if gpt4_cost > 0 else 0
            ),
            "complexity": metadata["complexity"],
        }


# Global instance for easy access
smart_selector = SmartModelSelector()
