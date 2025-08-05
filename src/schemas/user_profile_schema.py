from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, StrictInt
from src.db.models.user_profile import (
    RunnerLevel,
    RaceDistance,
    PastRace,
    Goal,
    Motivation,
    AgeGroup,
    RunPreference,
)

# Literal support for coercion
HasInjuryLiteral = Literal["Yes", "No"]


class Height(BaseModel):
    feet: StrictInt = Field(..., ge=3, le=8)
    inches: StrictInt = Field(..., ge=0, le=11)


class UserProfileSchema(BaseModel):
    user_id: str
    runnerLevel: RunnerLevel
    raceHistory: bool
    raceDate: Optional[str]
    raceDistance: Optional[RaceDistance]
    pastRaces: Optional[List[PastRace]]

    # ✅ Updated to nested height object
    height: Height

    weight: Optional[int]
    trainingDays: Optional[List[str]]
    mainGoal: Optional[Goal]
    motivation: Optional[List[Motivation]]
    ageGroup: Optional[AgeGroup]
    longestRun: Optional[int]
    runPreference: Optional[RunPreference]

    # 🔁 Changed from bool → coercible union
    hasInjury: HasInjuryLiteral = "No"

    injuryDetails: Optional[str] = Field(default=None)

    @field_validator("injuryDetails")
    @classmethod
    def validate_injury_details(cls, v, info):
        has_injury = info.data.get("hasInjury")
        if has_injury == "Yes" or has_injury is True:
            if not v or not v.strip():
                raise ValueError("injuryDetails is required when hasInjury is Yes/True")
        return v

    @field_validator("hasInjury", mode="before")
    @classmethod
    def coerce_has_injury(cls, v):
        if isinstance(v, str):
            return "Yes" if v.strip().lower() == "yes" else "No"
        if isinstance(v, bool):
            return "Yes" if v else "No"
        raise ValueError("Invalid value for hasInjury; must be Yes, No, True, or False")
