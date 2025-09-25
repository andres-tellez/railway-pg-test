from enum import Enum


class PastRace(str, Enum):
    FIVE_K = "5K"
    TEN_K = "10K"
    HALF_MARATHON = "Half Marathon"
    MARATHON = "Marathon"
    ULTRA = "Ultra"
    NONE = "Haven't raced yet"


class Motivation(str, Enum):
    HEALTH = "Health"
    STRESS_RELIEF = "Stress relief"
    COMPETITION = "Competition"
    ENJOYMENT = "Enjoyment"
    OTHER = "Other"


class TrainingDay(str, Enum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"
