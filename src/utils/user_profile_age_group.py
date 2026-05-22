"""Age-group labels derived from birth year for user_profile.age_group."""

from __future__ import annotations

from datetime import date


def age_group_band_from_birth_year(birth_year: int) -> str:
    """Decade band like '30–39'; age floor 13 for minor-safety."""
    y = date.today().year
    age = max(13, min(110, y - int(birth_year)))
    bracket = (age // 10) * 10
    return f"{bracket}-{bracket + 9}"
