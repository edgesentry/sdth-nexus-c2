"""S4 Fusion Disagreement — SensorSim scenario_02 multi-site bench (auxiliary).

Consumes exports/s4_fusion_disagreement_scenario.jsonl. Surfaces count/subset
disagreement across Air / Army / Navy without collapsing into a fused track.
Distinct from Pillar-1 S2_osint_swarm.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph
from core.schema import Observation

from app.adapters.sensorsim_canonical import load_scenario_jsonl
from app.adapters.southbound_sensor import canonical_row_to_event
from app.agent import make_tier1_coa
from app.scenarios.base import Finding, Scenario

SCENARIO_ID = "S4_fusion_disagreement"


def _build_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in load_scenario_jsonl(SCENARIO_ID):
        converted = canonical_row_to_event(row)
        if converted is not None:
            events.append(converted)
    return events


def _by_source(graph: SpatialEntityGraph, source: str) -> list[Observation]:
    return [o for o in graph.observations if str(o.attributes.get("source")) == source]


def _unique_tracks(obs: list[Observation]) -> set[str]:
    out: set[str] = set()
    for o in obs:
        tid = o.attributes.get("track_id") or o.entity_hint
        if tid:
            out.add(str(tid))
    return out


def _early_stamp(obs: Observation) -> bool:
    """Wall-clock early window (~14:30) via compressed time_s ≈ 0."""
    t = obs.attributes.get("time_s")
    if t is None:
        return True
    return float(t) <= 2.0


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    air_radar = _by_source(graph, "AIR_RADAR")
    air_eoir = _by_source(graph, "AIR_EOIR")
    army_eoir = _by_source(graph, "ARMY_EOIR")
    air_ew = _by_source(graph, "AIR_EW")
    army_ew = _by_source(graph, "ARMY_EW")
    navy_radar = _by_source(graph, "NAVY_COASTAL_RADAR")

    if not air_radar:
        return None

    radar_tracks = _unique_tracks(air_radar)
    air_eo_early = _unique_tracks([o for o in air_eoir if _early_stamp(o)])
    army_eo_early = _unique_tracks([o for o in army_eoir if _early_stamp(o)])
    # Fall back to all EO if early filter empties (fixture may be sparse).
    if not air_eo_early:
        air_eo_early = _unique_tracks(air_eoir)
    if not army_eo_early:
        army_eo_early = _unique_tracks(army_eoir)

    radar_n = len(radar_tracks)
    air_eo_n = len(air_eo_early)
    army_eo_n = len(army_eo_early)
    if radar_n < 2:
        return None
    # Disagreement: EO subsets resolve fewer / different members than MPSTAR.
    count_disagree = air_eo_n < radar_n or army_eo_n < radar_n or air_eo_n != army_eo_n

    ew_negative = bool(air_ew or army_ew) and all(
        o.attributes.get("detected") is False
        or o.attributes.get("rf_negative")
        or str(o.attributes.get("classification", "")).startswith("no_relevant")
        for o in air_ew + army_ew
    )

    navy_airborne = [
        o
        for o in navy_radar
        if str(o.attributes.get("classification", "")).upper() == "UNKNOWN"
        or str(o.attributes.get("track_id", "")).startswith("NAVY-UNK")
    ]
    navy_air_n = len(_unique_tracks(navy_airborne))
    navy_late = navy_air_n > 0

    if not count_disagree and not (ew_negative and radar_n >= 5):
        return None

    # Prefer an MPSTAR track for tasking cue.
    track_id = None
    for tid, track in graph.tracks.items():
        for o in air_radar:
            if o.observation_id in track.observation_ids:
                track_id = tid
                break
        if track_id:
            break
    if track_id is None:
        return None

    mismatch_m = float(abs(radar_n - air_eo_n) + abs(radar_n - army_eo_n)) * 500.0
    amber = "MULTI_SITE_COUNT_DISAGREEMENT"
    if ew_negative:
        amber += "+EW_NON_CORROBORATION"
    if navy_late:
        amber += "+NAVY_DELAYED_UNKNOWN"

    picture = (
        f"Air MPSTAR resolves {radar_n} UAS while Air EO/IR sees {air_eo_n} and "
        f"Army EO/IR sees {army_eo_n} in the early window — multi-site disagreement."
    )
    if ew_negative:
        picture += " EW reports no relevant RF; absence of RF must not invalidate radar/EO."
    if navy_late:
        picture += (
            f" Navy coastal later acquires {navy_air_n} UNKNOWN airborne contacts "
            "(missing early tracks = not yet detected, not nonexistent)."
        )

    return Finding(
        scenario_id=SCENARIO_ID,
        track_id=track_id,
        threat_class="multi_site_uas_disagreement",
        warning_minutes_est=12.0,
        mismatch_m=mismatch_m,
        confidence=0.82,
        picture_summary=picture,
        adversarial_hypothesis=(
            "Five physical UAS share one southeast approach; site geometry and modality "
            "limits produce different resolved counts/subtypes. Do not fuse into one "
            "hallucinated super-track — correlate and cue identify."
        ),
        spoof_sources=[],
        approach_sources=[o.source_id for o in air_radar[:5]],
        other_sources=[o.source_id for o in air_ew + army_ew + navy_airborne[:5]],
        message=picture,
        amber_alert=amber,
        source_breakdown={
            "mpstar_tracks": sorted(radar_tracks),
            "air_eoir_early": sorted(air_eo_early),
            "army_eoir_early": sorted(army_eo_early),
            "ew_negative": ew_negative,
            "navy_unknown_airborne": navy_air_n,
            "classification_counts": dict(
                Counter(str(o.attributes.get("classification")) for o in air_radar + air_eoir)
            ),
        },
    )


def _build_coa(
    graph: SpatialEntityGraph,
    finding: Finding,
    timeout_seconds: float,
) -> CourseOfAction:
    return make_tier1_coa(
        graph,
        finding,
        intent="CUE_AND_IDENTIFY",
        timeout_seconds=timeout_seconds,
        apply_contact_speed=False,
        speed_kt_override=None,
    )


SPEC = Scenario(
    id=SCENARIO_ID,
    title="Multi-Sensor Disagreement — Air/Army/Navy fusion bench",
    threat_class="multi_site_uas_disagreement",
    warning_minutes_est=12.0,
    narrative=(
        "SensorSim scenario_02_conflicting: five fixed-wing UAS approach from the "
        "southeast. Airbase MPSTAR holds five shahed-type tracks while EO/IR sites "
        "resolve different subsets; EW stays RF-silent; Navy coastal acquires five "
        "UNKNOWN airborne contacts only after range gate. Auxiliary bench — not "
        "Pillar-1 S2_osint_swarm."
    ),
    asset_label="RDR-00x / EO / NAVY-UNK",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
