from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, StrictInt
from src.db.models.user_profile import (
    Motivation,
    TrainingDay,
)


class Height(BaseModel):
    feet: StrictInt = Field(..., ge=3, le=8)
    inches: StrictInt = Field(..., ge=0, le=11)


class UserProfileSchema(BaseModel):
    user_id: str

    # Training Schedule
    trainingDays: Optional[List[str]]

    # Physical Stats
    ageGroup: (
        str  # Changed from enum to string to store user-friendly ranges like "30-39"
    )
    height: Height
    weight: Optional[int]

    # Motivation
    motivation: Optional[List[Motivation]] = None
