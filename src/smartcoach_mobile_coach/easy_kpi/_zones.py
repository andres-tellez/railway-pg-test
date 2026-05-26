from __future__ import annotations

from typing import Any


def kpi_zones_chart_api_payload(
    zones_chart: tuple[dict[str, float | str], ...],
) -> list[dict[str, Any]]:
    """Serialize KPI chart zones for REST payloads (shared by Easy Insights charts)."""
    return [
        {
            "color": str(zone["color"]),
            "min": float(zone["min"]),
            "max": float(zone["max"]),
        }
        for zone in zones_chart
    ]
