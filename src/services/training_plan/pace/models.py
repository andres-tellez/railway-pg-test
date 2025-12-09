"""
Pace Zone Models

Simple dataclass for pace zones. No logic, just data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PaceSeed:
    """Training pace zones in seconds per mile."""

    E_min: float  # Easy pace min
    E_max: float  # Easy pace max
    S_min: float  # Steady pace min
    S_max: float  # Steady pace max
    M: float  # Marathon pace (single value)
    T_min: float  # Threshold pace min
    T_max: float  # Threshold pace max
    week1_long_cap: float = 8.0  # Max long run for week 1
