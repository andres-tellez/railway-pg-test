"""
Build the `run` object for SmartCoach POST /analyze-run from DB rows.

Rules (product spec):
- duration_seconds: activity.moving_time, else activity.elapsed_time.
- Per split, segment duration uses moving_time, else elapsed_time, else 0.
- Cumulative distance uses Split.distance (Strava-style meters). Last sample uses
  max(cumulative, activity.distance) when activity.distance is set so totals align
  with the activity record without decreasing distance_meters.
- Last sample elapsed_seconds is snapped to duration_seconds; if split times sum
  above duration, mapping fails (no rescaling).
- heart_rate: if any split lacks average_heartrate, omit heart_rate on all samples;
  otherwise each post-split point uses that split's average (integer bpm).
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.db.models.activities import Activity
from src.db.models.splits import Split


def build_smartcoach_run(activity: Activity, splits: List[Split]) -> Dict[str, Any]:
    if not splits:
        raise ValueError(
            "No split rows for this activity; enrich the activity to load splits first."
        )

    duration = activity.moving_time or activity.elapsed_time
    if duration is None or int(duration) <= 0:
        raise ValueError("Activity is missing moving_time (and elapsed_time).")

    duration = int(duration)

    include_hr = all(s.average_heartrate is not None for s in splits)

    samples: List[Dict[str, Any]] = [{"elapsed_seconds": 0, "distance_meters": 0.0}]
    cum_t = 0
    cum_d = 0.0

    for s in splits:
        seg_t = s.moving_time
        if seg_t is None:
            seg_t = s.elapsed_time or 0
        seg_t = int(seg_t)
        seg_d = float(s.distance or 0.0)
        cum_t += seg_t
        cum_d += seg_d
        point: Dict[str, Any] = {
            "elapsed_seconds": cum_t,
            "distance_meters": cum_d,
        }
        if include_hr:
            point["heart_rate"] = int(round(float(s.average_heartrate)))
        samples.append(point)

    if cum_t > duration:
        raise ValueError(
            "Split segment times sum to more than activity moving_time; refusing to map."
        )

    samples[-1]["elapsed_seconds"] = duration

    if activity.distance is not None:
        samples[-1]["distance_meters"] = max(
            samples[-1]["distance_meters"],
            float(activity.distance),
        )

    _assert_run_invariants(duration, samples)
    return {"duration_seconds": duration, "samples": samples}


def _assert_run_invariants(duration: int, samples: List[Dict[str, Any]]) -> None:
    if len(samples) < 2:
        raise ValueError("Expected at least two samples (start + end of run).")
    if samples[0]["elapsed_seconds"] != 0 or samples[0]["distance_meters"] != 0:
        raise ValueError("First sample must be elapsed_seconds=0, distance_meters=0.")
    if samples[-1]["elapsed_seconds"] != duration:
        raise ValueError("Last sample elapsed_seconds must equal duration_seconds.")
    for i in range(1, len(samples)):
        if samples[i]["elapsed_seconds"] <= samples[i - 1]["elapsed_seconds"]:
            raise ValueError("samples elapsed_seconds must be strictly increasing.")
        if samples[i]["distance_meters"] < samples[i - 1]["distance_meters"]:
            raise ValueError("samples distance_meters must be non-decreasing.")
