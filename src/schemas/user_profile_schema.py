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

    # Race Details
    raceDate: Optional[str]
    raceDistance: Optional[RaceDistance]
    raceName: Optional[str]
    raceLocation: Optional[str]

    # Training Schedule
    trainingDays: Optional[List[str]]

    # Physical Stats
    ageGroup: AgeGroup
    height: Height
    weight: Optional[int]

    # Legacy fields for backward compatibility (optional)
    runnerLevel: Optional[RunnerLevel] = None
    raceHistory: Optional[bool] = None
    pastRaces: Optional[List[PastRace]] = None
    mainGoal: Optional[Goal] = None
    motivation: Optional[List[Motivation]] = None
    runPreference: Optional[RunPreference] = None
    longestRun: Optional[int] = None
