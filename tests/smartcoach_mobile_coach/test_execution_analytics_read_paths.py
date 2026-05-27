"""Guardrails: read paths must not recompute tempo segment from splits."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

READ_PATH_MODULES = [
    REPO_ROOT / "src/smartcoach_mobile_coach/training_kpi_service.py",
    REPO_ROOT / "src/smartcoach_mobile_coach/agent_tools.py",
    REPO_ROOT / "src/smartcoach_mobile_coach/weekly_insights_service.py",
]

FORBIDDEN_IMPORTS = {
    "compute_run_tempo_segment_pace",
    "select_qualifying_tempo_splits",
}

FORBIDDEN_SQL = {"v_easy_runs", "v_run_metrics"}


def _module_import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_read_path_modules_do_not_import_tempo_segment_compute():
    violations: list[str] = []
    for path in READ_PATH_MODULES:
        if not path.exists():
            continue
        imported = _module_import_names(path)
        bad = imported & FORBIDDEN_IMPORTS
        if bad:
            violations.append(f"{path.name}: {sorted(bad)}")
    assert (
        violations == []
    ), f"Read paths must not recompute tempo segment: {violations}"


def test_read_path_modules_have_no_view_references():
    violations: list[str] = []
    for path in READ_PATH_MODULES:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SQL:
            if token in text:
                violations.append(f"{path.name}: {token}")
    assert violations == [], f"Read paths must not reference SQL views: {violations}"


def test_execution_analytics_package_has_no_view_references():
    pkg = REPO_ROOT / "src/smartcoach_mobile_coach/execution_analytics"
    for path in pkg.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SQL:
            assert token not in text, f"{path.name} must not reference {token}"
