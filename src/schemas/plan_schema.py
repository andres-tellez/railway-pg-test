# src/schemas/plan_schema.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date
from enum import Enum
from src.utils.date_helpers import DAY_NAMES_ABBREV


class PrimaryGoal(str, Enum):
    JUST_FINISH = "Just Finish"
    TARGET_TIME = "Target Time"


class PlanCreateSchema(BaseModel):
    """Schema for creating a new training plan."""

    # Race details (required)
    race_date: date = Field(..., description="Target race date")
    race_distance: str = Field(default="Marathon", description="Race distance")
    race_name: Optional[str] = Field(
        None, max_length=255, description="Race name (optional)"
    )
    race_location: Optional[str] = Field(
        None, max_length=255, description="Race location (optional)"
    )
    race_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Race metadata including terrain, elevation gain, course type, etc. (optional)",
    )

    # Plan goals (required)
    primary_goal: PrimaryGoal = Field(
        ..., description="Primary goal: Just Finish or Target Time"
    )
    target_time: Optional[str] = Field(
        None,
        max_length=20,
        description="Target time (required if primary_goal is Target Time)",
    )

    # Training schedule (required)
    training_days: List[str] = Field(
        ..., min_length=1, description="Days of week to train"
    )

    # Long run day (optional) - must be one of the selected training days
    long_run_day: Optional[str] = Field(
        None,
        description="Preferred day for long runs (must be in training_days)",
    )

    # User context (optional but recommended)
    notes: Optional[str] = Field(
        None, description="Additional notes for plan generation"
    )
    user_timezone: Optional[str] = Field(
        default=None,
        description="IANA timezone for the user when generating the plan",
    )

    def model_post_init(self, __context):
        """Validate target_time requirement and long_run_day consistency."""
        if self.primary_goal == PrimaryGoal.TARGET_TIME and not self.target_time:
            raise ValueError(
                "target_time is required when primary_goal is 'Target Time'"
            )

        # Validate long_run_day is in training_days
        if self.long_run_day and self.long_run_day not in self.training_days:
            raise ValueError(
                f"long_run_day '{self.long_run_day}' must be one of the selected "
                f"training_days: {self.training_days}"
            )

    @field_validator("training_days")
    @classmethod
    def validate_training_days(cls, v: List[str]) -> List[str]:
        valid_days = DAY_NAMES_ABBREV
        if not v or len(v) == 0:
            raise ValueError("At least one training day must be specified")
        for day in v:
            if day not in valid_days:
                raise ValueError(
                    f"Invalid training day: {day}. Must be one of: {valid_days}"
                )
        return v

    @field_validator("long_run_day")
    @classmethod
    def validate_long_run_day(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that long_run_day is a valid day abbreviation."""
        # Treat empty strings as None (optional field - empty string means "auto-select")
        if v is None or v == "":
            return None

        # Check if it's a valid day abbreviation
        if v not in DAY_NAMES_ABBREV:
            raise ValueError(
                f"Invalid long_run_day: {v}. Must be one of: {DAY_NAMES_ABBREV}"
            )

        # Cross-field validation (checking if in training_days) is done in model_post_init
        return v

    class Config:
        # Use enum values in JSON
        use_enum_values = True
