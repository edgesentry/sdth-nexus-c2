"""Rule-based contradiction agent → Tier-1 COA (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass

from core.coa import ActionTier, CourseOfAction
from core.ontology import SpatialEntityGraph, Track, haversine_m
from core.schema import Observation


@dataclass
class ContradictionFinding:
    track_id: str
    mismatch_m: float
    spoof_sources: list[str]
    approach_sources: list[str]
    rf_sources: list[str]
    confidence: float
    message: str


def _speed_kt(obs: Observation) -> float:
    return float(obs.attributes.get("speed_kt", obs.speed_mps / 0.514444))


def detect_contradiction(
    graph: SpatialEntityGraph,
    track: Track,
    *,
    mismatch_m_threshold: float = 500.0,
    spoof_speed_kt_threshold: float = 1.0,
    approach_speed_kt_min: float = 10.0,
) -> ContradictionFinding | None:
    obs = [o for o in graph.observations if o.observation_id in track.observation_ids]
    if len(obs) < 2:
        return None

    spoof = [o for o in obs if _speed_kt(o) <= spoof_speed_kt_threshold and o.modality in {"ais", "generic"}]
    approach = [o for o in obs if _speed_kt(o) >= approach_speed_kt_min]
    rf = [o for o in obs if o.modality == "rf"]

    if not spoof or not approach:
        return None

    # Max pairwise distance between spoof and approach reports
    max_d = 0.0
    for s in spoof:
        for a in approach:
            max_d = max(max_d, haversine_m(s.latitude, s.longitude, a.latitude, a.longitude))

    if max_d < mismatch_m_threshold:
        return None

    conf = min(0.95, 0.55 + 0.1 * len(approach) + (0.1 if rf else 0.0))
    return ContradictionFinding(
        track_id=track.track_id,
        mismatch_m=max_d,
        spoof_sources=[o.source_id for o in spoof],
        approach_sources=[o.source_id for o in approach],
        rf_sources=[o.source_id for o in rf],
        confidence=conf,
        message=(
            f"Position/speed contradiction on {track.track_id}: "
            f"~{max_d:.0f} m mismatch; spoof={','.join(o.source_id for o in spoof)}; "
            f"approach={','.join(o.source_id for o in approach)}"
        ),
    )


def propose_inspect_coa(
    graph: SpatialEntityGraph,
    finding: ContradictionFinding,
    *,
    timeout_seconds: float = 5.0,
) -> CourseOfAction:
    track = graph.get_track(finding.track_id)
    assert track is not None
    # Prefer approach kinematics for tasking coordinates
    approach_obs = [
        o for o in graph.observations
        if o.observation_id in track.observation_ids and _speed_kt(o) >= 10.0
    ]
    if approach_obs:
        best = max(approach_obs, key=lambda o: o.confidence)
        lat, lon = best.latitude, best.longitude
        speed_kt = _speed_kt(best)
    else:
        lat, lon = track.latitude, track.longitude
        speed_kt = track.speed_mps / 0.514444

    sources = list(dict.fromkeys(finding.approach_sources + finding.rf_sources + finding.spoof_sources))
    return CourseOfAction(
        tier=ActionTier.TIER_1_HITL,
        target_entity_id=finding.track_id,
        target_coordinates=(lat, lon),
        intent="INTERCEPT_AND_IDENTIFY",
        timeout_seconds=timeout_seconds,
        confidence=finding.confidence,
        corroborating_sources=sources,
        raw_input_digest=track.fused_digest(),
        speed_kt=speed_kt,
        pre_conditions={"contradiction": True, "mismatch_m": finding.mismatch_m},
        post_conditions={"identify_complete": True},
        invariants={"fail_safe": "STATION_KEEP", "comm_loss": "STATION_KEEP"},
        metadata={"finding": finding.message},
    )


def find_first_contradiction_coa(
    graph: SpatialEntityGraph,
    *,
    mismatch_m_threshold: float = 500.0,
    spoof_speed_kt_threshold: float = 1.0,
    approach_speed_kt_min: float = 10.0,
    timeout_seconds: float = 5.0,
) -> tuple[ContradictionFinding, CourseOfAction] | None:
    for track in graph.all_tracks():
        finding = detect_contradiction(
            graph,
            track,
            mismatch_m_threshold=mismatch_m_threshold,
            spoof_speed_kt_threshold=spoof_speed_kt_threshold,
            approach_speed_kt_min=approach_speed_kt_min,
        )
        if finding:
            return finding, propose_inspect_coa(graph, finding, timeout_seconds=timeout_seconds)
    return None
