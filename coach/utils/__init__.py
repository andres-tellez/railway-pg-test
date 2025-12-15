"""
Coach utility modules.
"""

# Export IntentClassifier for easy importing
from .intent_classifier import IntentClassifier, IntentClassificationResult, Intent
from .constants import ClassificationMethod

__all__ = [
    "IntentClassifier",
    "IntentClassificationResult",
    "Intent",
    "ClassificationMethod",
]
