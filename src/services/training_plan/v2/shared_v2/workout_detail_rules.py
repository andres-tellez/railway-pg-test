"""
Workout Detail Rules Configuration (V2 copy)
"""

PHASE = {"BASE": "Base", "BUILD": "Build", "PEAK": "Peak", "TAPER": "Taper"}
PHASES_LIST = [PHASE["BASE"], PHASE["BUILD"], PHASE["PEAK"], PHASE["TAPER"]]
QUALITY_ENABLED_PHASES = {PHASE["BUILD"], PHASE["PEAK"]}

WU_CD_MI = {
    "easy": {"wu": 0.5, "cd": 0.5},
    "steady": {"wu": 1.0, "cd": 1.0},
    "endurance": {"wu": 1.0, "cd": 1.0},
    "long": {"wu": 0.0, "cd": 0.0},
}

STRIDES = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 4.0,
    "reps": 4,
    "on_sec": 20,
    "off_sec": 40,
}

MARATHON_FINISH = {
    "enabled_phases": {PHASE["PEAK"]},
    "min_lr_mi": 16.0,
    "finish_fraction": 0.25,
    "min_finish_mi": 2.0,
}

INTENSITY_MAP = {
    "easy": "E",
    "steady": "S",
    "endurance": "S",
    "long": "E",
}

FOCUS_TAGS = {
    "easy": "Recovery",
    "steady": "Aerobic",
    "endurance": "Medium-Long",
    "long": "Long – fueling practice",
}

SEGMENT_SUM_TOLERANCE = 0.11

THRESHOLD_INTERVALS = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 5.0,
    "interval_types": {
        "short": {"reps": 4, "interval_mi": 0.25, "rest_mi": 0.25},
        "medium": {"reps": 5, "interval_mi": 0.5, "rest_mi": 0.25},
        "long": {"reps": 4, "interval_mi": 0.75, "rest_mi": 0.25},
    },
}

TEMPO_BLOCKS = {
    "enabled_phases": {PHASE["BUILD"], PHASE["PEAK"]},
    "min_run_mi": 6.0,
    "block_mi": 2.0,
    "recovery_mi": 0.5,
    "max_blocks": 3,
}

DEFAULT_UNITS = "mi"
