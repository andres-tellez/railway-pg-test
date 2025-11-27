from typing import List, Optional, Union, Literal
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
    height: Optional[Height] = None
    weight: Optional[int] = None
    max_hr: Optional[int] = Field(None, ge=120, le=220)  # Max heart rate in bpm
