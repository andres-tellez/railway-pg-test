from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, StrictInt


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
        None, ge=120, le=220, description="Legacy alias for max_hr_manual"
    )
    max_hr_manual: Optional[int] = Field(None, ge=120, le=220)
    max_hr_active: Optional[Literal["manual", "auto"]] = Field(
        None, description="Which max HR drives zones: manual entry vs activity estimate"
    )
    restingHr: Optional[int] = Field(
        None, ge=35, le=110, description="Resting heart rate in bpm"
    )  # Resting heart rate in bpm

    @field_validator("birthYear")
    @classmethod
    def birth_year_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        y = date.today().year
        if v < 1920 or v > y - 13:
            raise ValueError(f"birthYear must be between 1920 and {y - 13}")
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
