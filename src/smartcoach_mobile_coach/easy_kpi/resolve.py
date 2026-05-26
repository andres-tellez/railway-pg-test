from __future__ import annotations

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
    EasyEfficiencyReference,
    build_easy_efficiency_reference,
    default_efficiency_band_config,
)
from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
    EasyHrDriftReference,
    build_easy_hr_drift_reference,
    default_hr_drift_band_config,
)


def resolve_hr_drift_band_config(session: Session, user_id: str):
    """HR drift thresholds for Insights (defaults today; user overrides later)."""
    _ = session, user_id
    return default_hr_drift_band_config()


def resolve_efficiency_band_config(session: Session, user_id: str):
    """Efficiency thresholds for Insights (defaults today; user overrides later)."""
    _ = session, user_id
    return default_efficiency_band_config()


def resolve_easy_hr_drift(session: Session, user_id: str) -> EasyHrDriftReference:
    cfg = resolve_hr_drift_band_config(session, user_id)
    return build_easy_hr_drift_reference(cfg)


def resolve_easy_efficiency(session: Session, user_id: str) -> EasyEfficiencyReference:
    cfg = resolve_efficiency_band_config(session, user_id)
    return build_easy_efficiency_reference(cfg)
