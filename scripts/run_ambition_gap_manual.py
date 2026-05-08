"""
Tiny manual runner for the Phase 3 ambition-gap evaluator.

This script is intentionally standalone and read-only:
- imports only evaluate_ambition_gap
- uses hardcoded sample inputs
- prints outputs for quick inspection
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.coaching_intelligence import evaluate_ambition_gap


SAMPLES = [
    {
        "name": "Just finish with moderate baseline",
        "weekly_mileage": 27.5,
        "primary_goal": "Just Finish",
        "target_time": None,
        "longest_run_miles": 12.0,
    },
    {
        "name": "Target time with thin baseline",
        "weekly_mileage": 12.0,
        "primary_goal": "Target Time",
        "target_time": "2:55:00",
        "longest_run_miles": 8.0,
    },
    {
        "name": "Target time with established baseline",
        "weekly_mileage": 48.0,
        "primary_goal": "Target Time",
        "target_time": "3:30:00",
        "longest_run_miles": 18.0,
    },
    {
        "name": "Missing goal context",
        "weekly_mileage": 20.0,
        "primary_goal": None,
        "target_time": None,
        "longest_run_miles": 10.0,
    },
]


def main() -> None:
    for i, sample in enumerate(SAMPLES, start=1):
        payload = {k: v for k, v in sample.items() if k != "name"}
        result = evaluate_ambition_gap(**payload)
        print(f"\n=== Case {i}: {sample['name']} ===")
        print("input:")
        print(json.dumps(payload, indent=2))
        print("output:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
