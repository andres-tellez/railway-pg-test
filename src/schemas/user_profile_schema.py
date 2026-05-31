from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, StrictInt

from src.utils.hr_zone_constants import (
    MANUAL_HR_SCHEMA_COARSE_MAX,
    MANUAL_HR_SCHEMA_COARSE_MIN,
)


class Height(BaseModel):
    feet: StrictInt = Field(..., ge=3, le=8)
    inches: StrictInt = Field(..., ge=0, le=11)


class UserProfileSchema(BaseModel):
    user_id: str

    # Physical Stats
    ageGroup: Optional[str] = (
        None  # Changed from enum to string to store user-friendly ranges like "30-39"
    )
    birthYear: Optional[int] = Field(
        None, description="Calendar year of birth for HR guidance cues"
    )
    height: Optional[Height] = None
    weight: Optional[int] = None
    max_hr: Optional[int] = Field(
        None,
        description="Legacy alias for max_hr_manual; narrow validation happens after profile merge",
    )
    max_hr_manual: Optional[int] = Field(
        None,
        description="Manual max HR (bpm); age-based bounds applied on merged profile save",
    )
    max_hr_active: Optional[Literal["manual", "auto"]] = Field(
        None, description="Which max HR drives zones: manual entry vs activity estimate"
    )
    restingHr: Optional[int] = Field(
        None, ge=35, le=110, description="Resting heart rate in bpm"
    )  # Resting heart rate in bpm
    restingHrSource: Optional[Literal["USER", "APPLE_HEALTH"]] = Field(
        None,
        description="How resting HR was obtained; only honored with an explicit restingHr save",
    )

    @field_validator("birthYear")
    @classmethod
    def birth_year_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        y = date.today().year
        if v < 1920 or v > y - 13:
            raise ValueError(f"birthYear must be between 1920 and {y - 13}")
        return v

    @field_validator("max_hr", "max_hr_manual")
    @classmethod
    def coarse_manual_hr_bounds(cls, v: Optional[int]) -> Optional[int]:
        """Wide guard for bad API input; strict window uses birth_year in route + HRMaxResolutionService."""
        if v is None:
            return v
        if v < MANUAL_HR_SCHEMA_COARSE_MIN or v > MANUAL_HR_SCHEMA_COARSE_MAX:
            raise ValueError(
                f"max HR must be between {MANUAL_HR_SCHEMA_COARSE_MIN} "
                f"and {MANUAL_HR_SCHEMA_COARSE_MAX} bpm"
            )
        return v

    @model_validator(mode="after")
    def legacy_max_hr_to_manual(self) -> "UserProfileSchema":
        if self.max_hr is not None and self.max_hr_manual is None:
            return self.model_copy(update={"max_hr_manual": self.max_hr})
        return self

    # Display Preferences
    unitSystem: Optional[Literal["imperial", "metric"]] = Field(
        None, description="Unit system preference"
    )
