"""
CoachContext package public API.

This package is the single owner of the compact always-on CoachSnapshot.
"""

from src.smartcoach_mobile_coach.coach_context.config import coach_context_v1_enabled
from src.smartcoach_mobile_coach.coach_context.prompt_formatter import (
    format_snapshot_for_system,
)
from src.smartcoach_mobile_coach.coach_context.schemas import (
    CoachSnapshot,
    SnapshotBuildResult,
)
from src.smartcoach_mobile_coach.coach_context.snapshot_builder import (
    build_snapshot,
    FIELD_SOURCES,
)

__all__ = [
    "CoachSnapshot",
    "FIELD_SOURCES",
    "SnapshotBuildResult",
    "build_snapshot",
    "coach_context_v1_enabled",
    "format_snapshot_for_system",
]
