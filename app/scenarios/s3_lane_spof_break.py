"""S3 — Shipping-lane SPOF / pattern break (strategic fragment → tactical tasking)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph, haversine_m

from app.agent import make_tier1_coa, observations_for_track
from app.scenarios.base import Finding, Scenario


def _build_events() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    # Residual "normal" AIS ghosts far from real contacts; coastal radars see new uncorrelated tracks
    return [
        {
            "source_id": "OPEN_AIS_SNAPSHOT",
            "entity_id": "AIS-HIST-LANE-A",
            "latitude": 1.2100,
            "longitude": 103.8200,
            "speed_kt": 8.0,
            "heading_deg": 90.0,
            "confidence": 0.5,
            "observed_at": (now - timedelta(minutes=25)).isoformat(),
            "modality": "ais",
            "note": "stale_open_ais_residue",
            "lane_density_index": 0.15,
            "vendor_track": "AIS-HIST-LANE-A",
        },
        {
            "source_id": "OPEN_AIS_SNAPSHOT",
            "entity_id": "AIS-HIST-LANE-B",
            "latitude": 1.2050,
            "longitude": 103.8400,
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
            "entity_id": "RADAR-NEW-901",
            "latitude": 1.2480,
            "longitude": 103.8700,
            "speed_kt": 16.0,
            "heading_deg": 200.0,
            "confidence": 0.88,
            "observed_at": (now - timedelta(seconds=5)).isoformat(),
            "modality": "radar",
            "note": "uncorrelated_new_contact",
            "vendor_track": "RADAR-NEW-901",
        },
        {
            "source_id": "COASTAL_RADAR_EAST",
            "entity_id": "RADAR-NEW-902",
            "latitude": 1.2505,
            "longitude": 103.8735,
            "speed_kt": 15.5,
            "heading_deg": 198.0,
            "confidence": 0.85,
            "observed_at": now.isoformat(),
            "modality": "radar",
            "note": "uncorrelated_new_contact",
            "vendor_track": "RADAR-NEW-902",
        },
    ]


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    ais = [o for o in graph.observations if o.modality == "ais"]
    radar = [o for o in graph.observations if o.modality == "radar"]
    if len(ais) < 1 or len(radar) < 1:
        return None

    # Lane SPOF signature: open AIS looks quiet/stale while fresh radar contacts appear elsewhere
    density = min(float(o.attributes.get("lane_density_index", 1.0)) for o in ais)
    if density > 0.4:
        return None

    # Find a radar-dominated track (new contact) that is far from stale AIS positions
    for track in graph.all_tracks():
        obs = observations_for_track(graph, track.track_id)
        track_radar = [o for o in obs if o.modality == "radar"]
        if not track_radar:
            continue
        # Distance from this track to nearest stale AIS observation
        min_ais_d = min(
            haversine_m(track.latitude, track.longitude, a.latitude, a.longitude) for a in ais
        )
        if min_ais_d < 2_000.0:
            continue
        conf = min(0.9, 0.6 + 0.1 * len(track_radar))
        warning_min = 12.0
        picture = (
            f"LANE SPOF / PATTERN BREAK (~{warning_min:.0f} min): open shipping picture is thin "
            f"(lane_density_index={density:.2f}) while coastal radars hold uncorrelated inbound "
            f"contact(s) ~{min_ais_d:.0f} m from stale AIS residue. "
            "The shipping lane is strategic terrain — collection is not the bottleneck; joining is."
        )
        hypo = (
            "If OPEN_AIS_SNAPSHOT is merely delayed, density may recover — but radar contacts still "
            "require identification. If coastal radars are false, do not escalate on open AIS silence alone."
        )
        return Finding(
            scenario_id="S3",
            track_id=track.track_id,
            threat_class="lane_spof_pattern_break",
            warning_minutes_est=warning_min,
            mismatch_m=min_ais_d,
            confidence=conf,
            picture_summary=picture,
            adversarial_hypothesis=hypo,
            spoof_sources=[o.source_id for o in ais],
            approach_sources=[o.source_id for o in track_radar],
            other_sources=[],
            message=picture,
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
    title="Shipping Lane SPOF — Pattern Break",
    threat_class="lane_spof_pattern_break",
    warning_minutes_est=12.0,
    narrative=(
        "Any one shipping lane can gate a capability. When open AIS thins and coastal radars "
        "see what open data does not, span strategic pattern-break into tactical approach patrol."
    ),
    asset_label="Approach Patrol USV-02",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
