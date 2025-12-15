"""
Shared constants for Coach system.

Centralized constants to avoid magic strings and numbers across components.
"""

from enum import Enum


class ClassificationMethod(Enum):
    """Methods used for classification/scanning."""

    RULES = "rules"
    EMBEDDINGS = "embeddings"
    LLM = "llm"


# Activity Summarization Defaults
DEFAULT_LAST_7_DAYS = 7
DEFAULT_LONG_RUNS_LIMIT = 3
DEFAULT_WEEKS_FOR_AGGREGATES = 4
