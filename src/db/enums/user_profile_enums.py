from enum import Enum


class Motivation(str, Enum):
    HEALTH = "Health"
    STRESS_RELIEF = "Stress relief"
    COMPETITION = "Competition"
    ENJOYMENT = "Enjoyment"
    WEIGHT_LOSS = "Weight loss"
    OTHER = "Other"


class TrainingDay(str, Enum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"
