"""
Calibration Pace Zones

Conservative defaults for users without HR zone data.
"""
from .models import PaceSeed

def get_calibration_pace_seed(week1_long: float = 8.0) -> PaceSeed:
    """
    Return conservative pace zones for "Just Finish" runners.
    
    Default: 10:00/mile marathon pace
    """
    M = 600.0  # 10:00/mile
    
    return PaceSeed(
        E_min=660.0,  # 11:00/mile
        E_max=690.0,  # 11:30/mile
        S_min=630.0,  # 10:30/mile
        S_max=660.0,  # 11:00/mile
        M=M,
        T_min=570.0,  # 9:30/mile
        T_max=580.0,  # 9:40/mile
        week1_long_cap=max(week1_long, 8.0),
    )

