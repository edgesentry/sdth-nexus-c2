"""Shared helpers for scenario detectors and COA construction."""

from __future__ import annotations

from core.coa import ActionTier, CourseOfAction
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

from app.scenarios.base import Finding


def speed_kt(obs: Observation) -> float:
    return float(obs.attributes.get("speed_kt", obs.speed_mps / 0.514444))


def observations_for_track(graph: SpatialEntityGraph, track_id: str) -> list[Observation]:
    track = graph.get_track(track_id)
    if track is None:
        return []
    return [o for o in graph.observations if o.observation_id in track.observation_ids]


def max_pairwise_mismatch_m(group_a: list[Observation], group_b: list[Observation]) -> float:
    max_d = 0.0
    for a in group_a:
        for b in group_b:
            max_d = max(max_d, haversine_m(a.latitude, a.longitude, b.latitude, b.longitude))
    return max_d


def preferred_tasking_coords(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    prefer_fast: bool = True,
) -> tuple[float, float, float]:
    """Return lat, lon, speed_kt for tasking."""
    track = graph.get_track(finding.track_id)
    assert track is not None
    obs = observations_for_track(graph, finding.track_id)
    if prefer_fast:
        fast = [o for o in obs if speed_kt(o) >= 5.0]
        if fast:
            best = max(fast, key=lambda o: o.confidence)
            return best.latitude, best.longitude, speed_kt(best)
    if obs:
        best = max(obs, key=lambda o: o.confidence)
        return best.latitude, best.longitude, speed_kt(best)
    return track.latitude, track.longitude, track.speed_mps / 0.514444


def make_tier1_coa(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    intent: str,
    timeout_seconds: float = 5.0,
    speed_kt_override: float | None = None,
    apply_contact_speed: bool = True,
) -> CourseOfAction:
    track = graph.get_track(finding.track_id)
    assert track is not None
    lat, lon, contact_speed = preferred_tasking_coords(graph, finding)
    skt: float | None
    if speed_kt_override is not None:
        skt = speed_kt_override
    elif not apply_contact_speed:
        skt = None
    else:
        skt = contact_speed
    return CourseOfAction(
        tier=ActionTier.TIER_1_HITL,
        target_entity_id=finding.track_id,
        target_coordinates=(lat, lon),
        intent=intent,
        timeout_seconds=timeout_seconds,
        confidence=finding.confidence,
        corroborating_sources=finding.all_sources(),
        raw_input_digest=track.fused_digest(),
        speed_kt=skt,
        pre_conditions={
            "contradiction": True,
            "mismatch_m": finding.mismatch_m,
            "threat_class": finding.threat_class,
            "warning_minutes_est": finding.warning_minutes_est,
        },
        post_conditions={"identify_or_clarify": True},
        invariants={"fail_safe": "STATION_KEEP", "comm_loss": "STATION_KEEP"},
        metadata={
            "scenario_id": finding.scenario_id,
            "picture_summary": finding.picture_summary,
            "adversarial_hypothesis": finding.adversarial_hypothesis,
            "finding": finding.message or finding.picture_summary,
            "contact_speed_kt": preferred_tasking_coords(graph, finding)[2],
        },
    )
