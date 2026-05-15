"""
Purpose:
- Typed errors for CoachContext assembly.

Responsibilities:
- Distinguish hard failures from slice-level soft failures.

Non-goals:
- No fallback policy decisions.

Guardrails:
- Allowed imports/calls: built-in Exception only.
- Must not import orchestrator or service modules.
"""


class CoachContextError(Exception):
    """Base error for coach-context failures."""


class CoachContextSoftFailure(CoachContextError):
    """Slice-local failure that should degrade to omission, not fallback."""
