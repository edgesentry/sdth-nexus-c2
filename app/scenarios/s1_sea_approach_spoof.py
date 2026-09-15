"""S1 — Sea approach AIS spoof (tactical MDA / minutes of warning)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph

from app.agent import make_tier1_coa, max_pairwise_mismatch_m, observations_for_track, speed_kt
from app.scenarios.base import Finding, Scenario


def _build_events() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    # ~850 m NE offset between AIS (spoofed stationary) and radar/EO (real approach)
    ais_lat, ais_lon = 1.2345, 103.8567
    radar_lat, radar_lon = 1.2395, 103.8620
    return [
        {
            "source_id": "AIS_BROADCAST",
            "entity_id": "AIS-MMSI-563000111",
            "latitude": ais_lat,
            "longitude": ais_lon,
            "speed_kt": 0.1,
            "heading_deg": 0.0,
            "confidence": 0.92,
            "observed_at": (now - timedelta(seconds=12)).isoformat(),
            "modality": "ais",
            "note": "adversarial_or_manipulable",
            "vendor_track": "AIS-MMSI-563000111",
        },
        {
            "source_id": "COASTAL_RADAR_NORTH",
            "entity_id": "RADAR-TRK-7742",
            "latitude": radar_lat,
            "longitude": radar_lon,
            "speed_kt": 19.5,
            "heading_deg": 214.0,
            "confidence": 0.86,
            "observed_at": (now - timedelta(seconds=4)).isoformat(),
            "modality": "radar",
            "note": "inbound_sea_approach",
            "vendor_track": "RADAR-TRK-7742",
        },
        {
            "source_id": "PORT_EO_04",
            "entity_id": "EO-CAM-04-OBJ-19",
            "latitude": radar_lat + 0.00025,
            "longitude": radar_lon + 0.00015,
            "speed_kt": 20.2,
            "heading_deg": 215.0,
            "confidence": 0.8,
            "observed_at": now.isoformat(),
            "modality": "optical",
            "note": "visual_inbound",
            "vendor_track": "EO-CAM-04-OBJ-19",
        },
        {
            "source_id": "RF_CUAS_NODE",
            "entity_id": "RF-BEARING-09",
            "latitude": radar_lat,
            "longitude": radar_lon,
            "speed_kt": 0.0,
            "confidence": 0.65,
            "observed_at": (now - timedelta(seconds=2)).isoformat(),
            "modality": "rf",
            "note": "drone_control_band_near_contact",
            "band_mhz": 2400,
            "vendor_track": "RF-BEARING-09",
        },
    ]


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    for track in graph.all_tracks():
        obs = observations_for_track(graph, track.track_id)
        if len(obs) < 2:
            continue
        spoof = [o for o in obs if speed_kt(o) <= 1.0 and o.modality == "ais"]
        approach = [o for o in obs if speed_kt(o) >= 10.0]
        rf = [o for o in obs if o.modality == "rf"]
        if not spoof or not approach:
            continue
        mismatch = max_pairwise_mismatch_m(spoof, approach)
        if mismatch < 500.0:
            continue
        vendor_ids = sorted({str(o.attributes.get("vendor_track", o.entity_hint)) for o in obs})
        conf = min(0.95, 0.55 + 0.1 * len(approach) + (0.08 if rf else 0.0))
        warning_min = max(3.0, 18.0 - mismatch / 100.0)
        picture = (
            f"SEA APPROACH WARNING (~{warning_min:.0f} min): geometry/motion associate "
            f"{len(vendor_ids)} vendor track IDs without a shared identifier. "
            f"AIS reports nearly stationary while radar/EO show ~20 kt inbound "
            f"(~{mismatch:.0f} m disagreement)."
        )
        hypo = (
            "If AIS_BROADCAST is false/spoofed, the fused picture remains an inbound surface "
            "contact on the sea approach (radar+EO). If radar/EO are false, the threat collapses "
            "to a benign AIS track — do not task on AIS alone."
        )
        return Finding(
            scenario_id="S1",
            track_id=track.track_id,
            threat_class="sea_approach_deception",
            warning_minutes_est=warning_min,
            mismatch_m=mismatch,
            confidence=conf,
            picture_summary=picture,
            adversarial_hypothesis=hypo,
            spoof_sources=[o.source_id for o in spoof],
            approach_sources=[o.source_id for o in approach],
            other_sources=[o.source_id for o in rf],
            message=picture,
        )
    return None


def _build_coa(
    graph: SpatialEntityGraph, finding: Finding, timeout_seconds: float
) -> CourseOfAction:
    return make_tier1_coa(
        graph,
        finding,
        intent="ISR_IDENTIFY_CONTACT",
        timeout_seconds=timeout_seconds,
    )


SPEC = Scenario(
    id="S1",
    title="Sea Approach — Adversarial AIS Spoof",
    threat_class="sea_approach_deception",
    warning_minutes_est=8.0,
    narrative=(
        "Everything that can hurt arrives on the sea approaches. AIS is manipulable; "
        "radar and EO disagree with the broadcast. Fuse without shared IDs and task ISR "
        "before the minutes run out."
    ),
    asset_label="Coastal ISR USV-01",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
