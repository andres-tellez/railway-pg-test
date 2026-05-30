"""
Canonical run-type registry for plan, scoring, and Insights zone mapping.

Single source of truth for:
- Legacy alias → canonical key normalization
- Pace/HR zone keys per run type
- Insights system mapping (Z2=Easy, Z3=Tempo, Z4=Threshold)
- Display names and scoring tolerances
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Canonical keys (scoring / API wire)
# ---------------------------------------------------------------------------
RUN_TYPE_EASY = "easy"
RUN_TYPE_TEMPO = "tempo"
RUN_TYPE_THRESHOLD = "threshold"
RUN_TYPE_LONG = "long"
RUN_TYPE_INTERVALS = "intervals"
RUN_TYPE_HILLS = "hills"

# Deprecated legacy key strings — normalize to easy; not in CANONICAL_RUN_TYPES.
RUN_TYPE_RECOVERY = "recovery"
RUN_TYPE_STEADY = "steady"

TIER_PRIMARY = "primary"
TIER_SECONDARY = "secondary"

PRIMARY_RUN_TYPES = (
    RUN_TYPE_EASY,
    RUN_TYPE_TEMPO,
    RUN_TYPE_THRESHOLD,
    RUN_TYPE_LONG,
)
SECONDARY_RUN_TYPES = (RUN_TYPE_INTERVALS, RUN_TYPE_HILLS)
CANONICAL_RUN_TYPES = PRIMARY_RUN_TYPES + SECONDARY_RUN_TYPES


@dataclass(frozen=True)
class ToleranceProfile:
    """Simple v1 tolerance thresholds used for score bucketing."""

    green_min_compliance: float
    yellow_min_compliance: float
    green_max_above: float
    yellow_max_above: float


@dataclass(frozen=True)
class RunTypeSpec:
    """Full run-type definition: zones, naming, scoring, taxonomy link."""

    canonical_key: str
    display_name: str
    taxonomy_key: str
    pace_zone_key: str
    hr_zone_key: str
    insights_system: str | None
    target_zone_ids: tuple[int, ...]
    acceptable_zone_min: int
    acceptable_zone_max: int
    tier: str = TIER_PRIMARY
    primary_run_type: str | None = None
    min_duration_seconds: int | None = None
    tolerance: ToleranceProfile | None = None

    @property
    def key(self) -> str:
        """Back-compat alias used by plan wire and scoring modules."""
        return self.canonical_key


# Registry keyed by canonical run type
_RUN_TYPE_SPECS: dict[str, RunTypeSpec] = {
    RUN_TYPE_EASY: RunTypeSpec(
        canonical_key=RUN_TYPE_EASY,
        display_name="Easy",
        taxonomy_key="easy",
        pace_zone_key="z2",
        hr_zone_key="z2",
        insights_system="easy",
        target_zone_ids=(1, 2),
        acceptable_zone_min=1,
        acceptable_zone_max=3,
        tier=TIER_PRIMARY,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=76.0,
            yellow_min_compliance=60.0,
            green_max_above=10.0,
            yellow_max_above=22.0,
        ),
    ),
    RUN_TYPE_TEMPO: RunTypeSpec(
        canonical_key=RUN_TYPE_TEMPO,
        display_name="Tempo",
        taxonomy_key="tempo",
        pace_zone_key="z3",
        hr_zone_key="z3",
        insights_system="tempo",
        target_zone_ids=(3, 4),
        acceptable_zone_min=3,
        acceptable_zone_max=4,
        tier=TIER_PRIMARY,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=66.0,
            yellow_min_compliance=50.0,
            green_max_above=12.0,
            yellow_max_above=25.0,
        ),
    ),
    RUN_TYPE_THRESHOLD: RunTypeSpec(
        canonical_key=RUN_TYPE_THRESHOLD,
        display_name="Threshold",
        taxonomy_key="threshold",
        pace_zone_key="z4",
        hr_zone_key="z4",
        insights_system="threshold",
        target_zone_ids=(4,),
        acceptable_zone_min=3,
        acceptable_zone_max=5,
        tier=TIER_PRIMARY,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=64.0,
            yellow_min_compliance=48.0,
            green_max_above=14.0,
            yellow_max_above=28.0,
        ),
    ),
    RUN_TYPE_LONG: RunTypeSpec(
        canonical_key=RUN_TYPE_LONG,
        display_name="Long",
        taxonomy_key="long_run",
        pace_zone_key="z2",
        hr_zone_key="z2",
        insights_system="easy",
        target_zone_ids=(2,),
        acceptable_zone_min=1,
        acceptable_zone_max=3,
        tier=TIER_PRIMARY,
        min_duration_seconds=75 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=68.0,
            yellow_min_compliance=52.0,
            green_max_above=14.0,
            yellow_max_above=27.0,
        ),
    ),
    RUN_TYPE_INTERVALS: RunTypeSpec(
        canonical_key=RUN_TYPE_INTERVALS,
        display_name="Intervals",
        taxonomy_key="intervals",
        pace_zone_key="z4",
        hr_zone_key="z4",
        insights_system="threshold",
        target_zone_ids=(4, 5),
        acceptable_zone_min=4,
        acceptable_zone_max=5,
        tier=TIER_SECONDARY,
        primary_run_type=RUN_TYPE_THRESHOLD,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=62.0,
            yellow_min_compliance=46.0,
            green_max_above=16.0,
            yellow_max_above=30.0,
        ),
    ),
    RUN_TYPE_HILLS: RunTypeSpec(
        canonical_key=RUN_TYPE_HILLS,
        display_name="Hills",
        taxonomy_key="hills",
        pace_zone_key="z4",
        hr_zone_key="z4",
        insights_system="threshold",
        target_zone_ids=(4, 5),
        acceptable_zone_min=4,
        acceptable_zone_max=5,
        tier=TIER_SECONDARY,
        primary_run_type=RUN_TYPE_THRESHOLD,
        min_duration_seconds=20 * 60,
        tolerance=ToleranceProfile(
            green_min_compliance=62.0,
            yellow_min_compliance=46.0,
            green_max_above=16.0,
            yellow_max_above=30.0,
        ),
    ),
}

# Legacy / taxonomy aliases → canonical key
_LEGACY_TO_CANONICAL: dict[str, str] = {
    "easy": RUN_TYPE_EASY,
    "recovery": RUN_TYPE_EASY,
    "steady": RUN_TYPE_EASY,
    "fartlek": RUN_TYPE_EASY,
    "shakeout": RUN_TYPE_EASY,
    "endurance": RUN_TYPE_LONG,
    "long": RUN_TYPE_LONG,
    "long_run": RUN_TYPE_LONG,
    "tempo": RUN_TYPE_TEMPO,
    "threshold": RUN_TYPE_THRESHOLD,
    "intervals": RUN_TYPE_INTERVALS,
    "hills": RUN_TYPE_HILLS,
    "vo2": RUN_TYPE_INTERVALS,
    "repetitions": RUN_TYPE_INTERVALS,
    "race": RUN_TYPE_INTERVALS,
}


def normalize_run_type_key(raw_value: str | None) -> str | None:
    """Normalize a raw run/workout type string to a canonical run type key."""
    if not raw_value:
        return None
    raw = str(raw_value).strip().lower()
    if not raw:
        return None
    return _LEGACY_TO_CANONICAL.get(raw)


def get_run_type_spec(canonical_key: str) -> RunTypeSpec | None:
    return _RUN_TYPE_SPECS.get(canonical_key)


def resolve_run_type(raw: str | None) -> RunTypeSpec:
    """
    Resolve any raw/taxonomy/legacy key to a full RunTypeSpec.

    Unknown values fall back to Easy spec.
    """
    canonical = normalize_run_type_key(raw)
    if canonical and canonical in _RUN_TYPE_SPECS:
        return _RUN_TYPE_SPECS[canonical]
    return _RUN_TYPE_SPECS[RUN_TYPE_EASY]


def pace_zone_key_for_run_type(
    run_type_key: str, *, has_marathon_finish: bool = False
) -> str:
    """Resolve pace-band key (z2, z3, z4, m) for a planned workout."""
    run_type_lower = str(run_type_key or "").strip().lower()
    if has_marathon_finish and run_type_lower in {"long", "long_run"}:
        return "m"
    return resolve_run_type(run_type_key).pace_zone_key


def hr_zone_key_for_run_type(run_type_key: str) -> str:
    return resolve_run_type(run_type_key).hr_zone_key


# Back-compat alias for scoring modules (Phase 2)
RunTypeDefinition = RunTypeSpec
RUN_TYPE_DEFINITIONS: dict[str, RunTypeSpec] = _RUN_TYPE_SPECS
LEGACY_TO_CANONICAL_RUN_TYPE = _LEGACY_TO_CANONICAL


def iter_run_type_registry_payload() -> list[dict]:
    """API-serializable registry entries for GET /api/runner-profile/zones."""
    out: list[dict] = []
    for key in CANONICAL_RUN_TYPES:
        spec = _RUN_TYPE_SPECS[key]
        legacy_aliases = sorted(
            alias for alias, canon in _LEGACY_TO_CANONICAL.items() if canon == key
        )
        entry: dict = {
            "key": spec.canonical_key,
            "tier": spec.tier,
            "display_name": spec.display_name,
            "taxonomy_key": spec.taxonomy_key,
            "pace_zone_key": spec.pace_zone_key,
            "hr_zone_key": spec.hr_zone_key,
            "insights_system": spec.insights_system,
            "legacy_aliases": legacy_aliases,
        }
        if spec.primary_run_type:
            entry["primary_run_type"] = spec.primary_run_type
        out.append(entry)
    return out


def _validate_registry() -> None:
    assert set(_RUN_TYPE_SPECS.keys()) == set(CANONICAL_RUN_TYPES)
    for spec in _RUN_TYPE_SPECS.values():
        assert spec.pace_zone_key in {"z2", "z3", "z4", "m"}
        assert spec.hr_zone_key in {"z1", "z2", "z3", "z4", "z5"}
        assert spec.tier in {TIER_PRIMARY, TIER_SECONDARY}
        if spec.tier == TIER_SECONDARY:
            assert spec.primary_run_type in PRIMARY_RUN_TYPES
        else:
            assert spec.primary_run_type is None

    threshold = _RUN_TYPE_SPECS[RUN_TYPE_THRESHOLD]
    assert threshold.pace_zone_key == "z4"
    assert threshold.insights_system == "threshold"
    assert threshold.tier == TIER_PRIMARY

    tempo = _RUN_TYPE_SPECS[RUN_TYPE_TEMPO]
    assert tempo.pace_zone_key == "z3"
    assert tempo.canonical_key != threshold.canonical_key

    assert normalize_run_type_key("endurance") == RUN_TYPE_LONG
    assert normalize_run_type_key("threshold") == RUN_TYPE_THRESHOLD
    assert normalize_run_type_key("steady") == RUN_TYPE_EASY
    assert normalize_run_type_key("recovery") == RUN_TYPE_EASY
    assert normalize_run_type_key("intervals") == RUN_TYPE_INTERVALS
    assert normalize_run_type_key("vo2") == RUN_TYPE_INTERVALS


_validate_registry()
