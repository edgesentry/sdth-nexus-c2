"""S3 — Shipping lane & coastal anomaly: space SAR diff vs thin AIS."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.kinematics import (
    in_reachability_envelope,
    kt_to_mps,
    project_dead_reckoning,
    project_observation,
)
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

from app.adapters.sar_candidate_event import (
    SPACE_SAR_MODALITY,
    observation_from_assumed_fixture,
)
from app.agent import make_tier1_coa, observations_for_track
from app.scenarios.base import Finding, Scenario

# Thin / stale open-AIS residue well away from the SAR cue cell
_AIS_LAT, _AIS_LON = 1.2100, 103.8200
# SAR latency band (docs: typically 30 min); heading/speed estimated from OBB/COG.
_SAR_AGE = timedelta(minutes=30)
_SAR_HEADING_DEG = 200.0
_SAR_SPEED_KT = 12.0
_STATIC_RADAR_CUE_M = 1_500.0


def _build_events() -> list[dict[str, Any]]:
    """Synthetic multimodal events: space_sar (fixture) + thin AIS + coastal radar."""
    now = datetime.now(UTC)
    sar_obs = observation_from_assumed_fixture()
    # Re-stamp SAR to a delayed pass relative to demo clock while keeping fixture identity
    sar_at = now - _SAR_AGE
    radar_at = now - timedelta(seconds=5)
    sar_obs.observed_at = sar_at
    projected = project_dead_reckoning(
        sar_obs.latitude,
        sar_obs.longitude,
        heading_deg=_SAR_HEADING_DEG,
        speed_mps=kt_to_mps(_SAR_SPEED_KT),
        dt_sec=(radar_at - sar_at).total_seconds(),
    )
    return [
        {
            "source_id": sar_obs.source_id,
            "entity_id": sar_obs.entity_hint,
            "observation_id": sar_obs.observation_id,
            **sar_obs.attributes,
            "latitude": sar_obs.latitude,
            "longitude": sar_obs.longitude,
            "speed_kt": _SAR_SPEED_KT,
            "heading_deg": _SAR_HEADING_DEG,
            "confidence": sar_obs.confidence,
            "observed_at": sar_at.isoformat(),
            "modality": SPACE_SAR_MODALITY,
        },
        {
            "source_id": "OPEN_AIS_SNAPSHOT",
            "entity_id": "AIS-HIST-LANE-A",
            "latitude": _AIS_LAT,
            "longitude": _AIS_LON,
            "speed_kt": 8.0,
            "heading_deg": 90.0,
            "confidence": 0.5,
            "observed_at": (now - timedelta(minutes=25)).isoformat(),
            "modality": "ais",
            "note": "stale_open_ais_residue",
            "lane_density_index": 0.15,
            "ais_correlation": "NONE",
            "vendor_track": "AIS-HIST-LANE-A",
        },
        {
            "source_id": "OPEN_AIS_SNAPSHOT",
            "entity_id": "AIS-HIST-LANE-B",
            "latitude": _AIS_LAT - 0.005,
            "longitude": _AIS_LON + 0.02,
            "speed_kt": 7.5,
            "heading_deg": 85.0,
            "confidence": 0.45,
            "observed_at": (now - timedelta(minutes=22)).isoformat(),
            "modality": "ais",
            "note": "stale_open_ais_residue",
            "lane_density_index": 0.15,
            "vendor_track": "AIS-HIST-LANE-B",
        },
        {
            "source_id": "COASTAL_RADAR_WEST",
            "entity_id": "RADAR-SAR-CUE-901",
            "latitude": projected.latitude,
            "longitude": projected.longitude,
            "speed_kt": _SAR_SPEED_KT,
            "heading_deg": _SAR_HEADING_DEG,
            "confidence": 0.86,
            "observed_at": radar_at.isoformat(),
            "modality": "radar",
            "note": "coastal_cue_in_sar_reachability_envelope",
            "vendor_track": "RADAR-SAR-CUE-901",
        },
    ]


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    sar = [o for o in graph.observations if o.modality == SPACE_SAR_MODALITY]
    ais = [o for o in graph.observations if o.modality == "ais"]
    radar = [o for o in graph.observations if o.modality == "radar"]
    if not sar or not ais:
        return None

    density = min(float(o.attributes.get("lane_density_index", 1.0)) for o in ais)
    if density > 0.4:
        return None

    # Prefer a track that carries the SAR observation (macro baseline cell)
    for track in graph.all_tracks():
        obs = observations_for_track(graph, track.track_id)
        track_sar = [o for o in obs if o.modality == SPACE_SAR_MODALITY]
        if not track_sar:
            continue

        primary = track_sar[0]
        min_ais_d = min(
            haversine_m(primary.latitude, primary.longitude, a.latitude, a.longitude) for a in ais
        )
        if min_ais_d < 2_000.0:
            continue

        t_ref = max((o.observed_at for o in radar), default=primary.observed_at)
        projected = project_observation(primary, t_ref)
        nearby_radar: list[Observation] = []
        radar_in_envelope = False
        radar_distance_m = 0.0
        for o in radar:
            static = (
                haversine_m(primary.latitude, primary.longitude, o.latitude, o.longitude)
                <= _STATIC_RADAR_CUE_M
            )
            inside = in_reachability_envelope(projected, o.latitude, o.longitude)
            if not (static or inside):
                continue
            nearby_radar.append(o)
            if inside:
                radar_in_envelope = True
                radar_distance_m = haversine_m(
                    projected.latitude, projected.longitude, o.latitude, o.longitude
                )

        track_radar = [o for o in obs if o.modality == "radar"]
        approach = list(
            dict.fromkeys([o.source_id for o in track_sar + track_radar + nearby_radar])
        )
        amber = "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
        warning_min = 12.0
        conf = min(0.92, 0.55 + 0.15 * len(track_sar) + 0.1 * len(nearby_radar))
        vessel_est = int(primary.attributes.get("vessel_count_est") or 0)
        dt_min = abs(projected.dt_sec) / 60.0
        envelope_clause = (
            f"Dead-reckoned SAR (Δt={dt_min:.0f} min, envelope {projected.radius_m:.0f} m) "
            "contains coastal radar (no shared MMSI). "
            if radar_in_envelope
            else (
                "Macro SAR is a retrospective baseline — coastal radar cues tactical "
                "confirmation, not a live satellite stream. "
            )
        )
        picture = (
            f"AMBER {amber} (~{warning_min:.0f} min): space-based SAR scene difference flags "
            f"unannounced dark vessel cluster (est. {vessel_est or 'n/a'}) "
            f"in {primary.attributes.get('area_id', 'sector')} "
            f"while open AIS is thin (lane_density_index={density:.2f}) and ~{min_ais_d:.0f} m away. "
            + envelope_clause
        )
        hypo = (
            "If SPACE_SAR_SCENE_DIFF is a false diff product, do not escalate on AIS silence alone. "
            "If open AIS is merely delayed, density may recover — but the SAR cell still warrants approach patrol ID."
        )
        breakdown = {
            "space_sar": {
                "event_type": primary.entity_hint,
                "vessel_count_est": vessel_est,
                "ais_correlation": primary.attributes.get("ais_correlation"),
                "sources": [o.source_id for o in track_sar],
            },
            "ais": {
                "lane_density_index": density,
                "sources": [o.source_id for o in ais],
            },
            "radar": {
                "contact_count": len(nearby_radar) or len(track_radar),
                "sources": [o.source_id for o in nearby_radar or track_radar],
            },
            "kinematics": {
                **projected.as_breakdown(),
                "radar_in_envelope": radar_in_envelope,
                "radar_distance_to_projected_m": radar_distance_m,
            },
        }
        return Finding(
            scenario_id="S3",
            track_id=track.track_id,
            threat_class="lane_sar_ais_dark_cluster",
            warning_minutes_est=warning_min,
            mismatch_m=min_ais_d,
            confidence=conf,
            picture_summary=picture,
            adversarial_hypothesis=hypo,
            spoof_sources=[o.source_id for o in ais],
            approach_sources=approach,
            other_sources=[],
            message=picture,
            amber_alert=amber,
            source_breakdown=breakdown,
        )
    return None


def _build_coa(
    graph: SpatialEntityGraph, finding: Finding, timeout_seconds: float
) -> CourseOfAction:
    return make_tier1_coa(
        graph,
        finding,
        intent="APPROACH_PATROL",
        timeout_seconds=timeout_seconds,
    )


SPEC = Scenario(
    id="S3",
    title="Shipping Lane & Coastal Anomaly — SAR Difference vs AIS",
    threat_class="lane_sar_ais_dark_cluster",
    warning_minutes_est=12.0,
    narrative=(
        "Macro space-based SAR scene difference flags an unannounced dark cluster; open AIS is thin "
        "or silent in the same cell. Dead-reckon the retrospective SAR contact to t_now, join it to "
        "coastal radar without a shared MMSI, and task approach patrol."
    ),
    asset_label="Approach Patrol USV-02",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
