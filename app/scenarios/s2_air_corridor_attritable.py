"""S2 — Attritable air-corridor raid (asymmetry / RF-silent gap)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph

from app.agent import make_tier1_coa, max_pairwise_mismatch_m, observations_for_track
from app.scenarios.base import Finding, Scenario


def _build_events() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    # Low-altitude corridor; optical and radar disagree by hundreds of metres; no ADS-B; RF silent
    opt_lat, opt_lon = 1.3510, 103.9900
    rad_lat, rad_lon = 1.3555, 103.9965
    return [
        {
            "source_id": "ADS_B_SECTOR_EMPTY",
            "entity_id": "ADSB-NULL-SECTOR",
            "latitude": opt_lat,
            "longitude": opt_lon,
            "speed_kt": 0.0,
            "confidence": 0.4,
            "observed_at": (now - timedelta(seconds=8)).isoformat(),
            "modality": "adsb",
            "note": "no_cooperative_squawk",
            "vendor_track": "ADSB-NULL",
            "empty_sector": True,
        },
        {
            "source_id": "EO_SKY_WATCH",
            "entity_id": "EO-AIR-OBJ-03",
            "latitude": opt_lat,
            "longitude": opt_lon,
            "speed_kt": 85.0,
            "heading_deg": 250.0,
            "confidence": 0.78,
            "observed_at": (now - timedelta(seconds=3)).isoformat(),
            "modality": "optical",
            "note": "small_attritable_airframe",
            "altitude_m_est": 180,
            "vendor_track": "EO-AIR-OBJ-03",
        },
        {
            "source_id": "GAP_FILLER_RADAR",
            "entity_id": "RADAR-AIR-551",
            "latitude": rad_lat,
            "longitude": rad_lon,
            "speed_kt": 90.0,
            "heading_deg": 248.0,
            "confidence": 0.84,
            "observed_at": now.isoformat(),
            "modality": "radar",
            "note": "weak_return_fast_inbound",
            "altitude_m_est": 200,
            "vendor_track": "RADAR-AIR-551",
        },
        {
            "source_id": "RF_PASSIVE_ARRAY",
            "entity_id": "RF-SILENT-SCAN",
            "latitude": (opt_lat + rad_lat) / 2,
            "longitude": (opt_lon + rad_lon) / 2,
            "speed_kt": 0.0,
            "confidence": 0.7,
            "observed_at": (now - timedelta(seconds=1)).isoformat(),
            "modality": "rf",
            "note": "no_emitter_detected",
            "rf_silent": True,
            "vendor_track": "RF-SILENT-SCAN",
        },
    ]


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    for track in graph.all_tracks():
        obs = observations_for_track(graph, track.track_id)
        optical = [o for o in obs if o.modality == "optical"]
        radar = [o for o in obs if o.modality == "radar"]
        adsb = [o for o in obs if o.modality == "adsb"]
        rf = [o for o in obs if o.modality == "rf"]
        if not optical or not radar:
            continue
        mismatch = max_pairwise_mismatch_m(optical, radar)
        if mismatch < 400.0:
            continue
        any(bool(o.attributes.get("rf_silent")) for o in rf) or not any(
            not bool(o.attributes.get("rf_silent", False)) for o in rf if o.modality == "rf"
        )
        # Treat empty ADS-B / silent RF as the asymmetric cheap-drone signature
        if not adsb and not rf:
            continue
        conf = min(0.93, 0.5 + 0.15 * len(optical) + 0.15 * len(radar))
        warning_min = 4.0
        picture = (
            f"AIR CORRIDOR WARNING (~{warning_min:.0f} min): attritable inbound with "
            f"no cooperative ADS-B, RF-silent, EO vs radar ~{mismatch:.0f} m apart. "
            "Cost-exchange inverted — do not wait for a perfect ID."
        )
        hypo = (
            "If EO_SKY_WATCH is false, radar-only remains a weak cue (high FAR risk). "
            "If GAP_FILLER_RADAR is false, optical alone is insufficient to task. "
            "RF silence removes classic CUAS emitters — spoofed ADS-B absence is expected."
        )
        return Finding(
            scenario_id="S2",
            track_id=track.track_id,
            threat_class="attritable_air_raid",
            warning_minutes_est=warning_min,
            mismatch_m=mismatch,
            confidence=conf,
            picture_summary=picture,
            adversarial_hypothesis=hypo,
            spoof_sources=[o.source_id for o in adsb],
            approach_sources=[o.source_id for o in optical + radar],
            other_sources=[o.source_id for o in rf],
            message=picture,
        )
    return None


def _build_coa(
    graph: SpatialEntityGraph, finding: Finding, timeout_seconds: float
) -> CourseOfAction:
    # Contact airspeed must not trip surface USV speed interlocks — cue node only.
    return make_tier1_coa(
        graph,
        finding,
        intent="CUE_AND_IDENTIFY",
        timeout_seconds=timeout_seconds,
        apply_contact_speed=False,
    )


SPEC = Scenario(
    id="S2",
    title="Air Corridor — Attritable RF-Silent Raid",
    threat_class="attritable_air_raid",
    warning_minutes_est=4.0,
    narrative=(
        "Reach without mass: cheap airframes on the air corridor. No ADS-B, no RF to hunt. "
        "Compose EO+radar disagreement into one picture and cue identification — not a "
        "polished kinetic demo."
    ),
    asset_label="Cue / ISR node Proxy-01",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
