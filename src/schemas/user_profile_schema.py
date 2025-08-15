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
    runPreference: Optional[RunPreference]
    longestRun: Optional[int] = None  # <-- add this line
