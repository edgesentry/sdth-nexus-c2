"""S2 — Airborne passenger OSINT & autonomous Shahed swarm (docs/scenarios.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

from app.adapters.osint_text import enrich_social_event, parse_osint_text
from app.agent import make_tier1_coa
from app.scenarios.base import Finding, Scenario

# ~1,200 m due north of the social/EO cue (ingress corridor)
_CUE_LAT, _CUE_LON = 1.3510, 103.9900
_RADAR_LAT, _RADAR_LON = 1.3618, 103.9900  # ≈1,200 m north

# Passenger in-flight sighting (Japan-bound commercial flight) — no geo/target context.
_INTEL_TEXT = (
    "In-flight passenger OSINT (commercial flight bound for Japan): smartphone video/photos "
    "of ~50 unknown delta-wing drones / Shahed-class airframes flying low below the aircraft. "
    "No coordinates or destination stated. Estimated vector bearing 248° at ~105 kt. "
    "#ufo #drones"
)
# Hardcoded fallback if OSINT parse fails.
_FALLBACK_CLAIMED_COUNT = 50
_MIN_CLAIMED_COUNT = 40
_EXPECTED_RADAR_CONTACTS = 4


def _build_events() -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    social = enrich_social_event(
        {
            "source_id": "CIVILIAN_SOCIAL_RECON",
            "entity_id": "OSINT-SWARM-CLAIM",
            "latitude": _CUE_LAT,
            "longitude": _CUE_LON,
            "speed_kt": 0.0,
            "confidence": 0.55,
            "observed_at": (now - timedelta(seconds=45)).isoformat(),
            "modality": "social",
            "note": "airborne_passenger_swarm_sighting",
            "intel_text": _INTEL_TEXT,
            "objective": "unknown_ingress",
            "vendor_track": "OSINT-SWARM-CLAIM",
        },
        fallback_count=_FALLBACK_CLAIMED_COUNT,
    )
    return [
        social,
        {
            "source_id": "ADS_B_SECTOR_EMPTY",
            "entity_id": "ADSB-NULL-SECTOR",
            "latitude": _CUE_LAT,
            "longitude": _CUE_LON,
            "speed_kt": 0.0,
            "confidence": 0.4,
            "observed_at": (now - timedelta(seconds=20)).isoformat(),
            "modality": "adsb",
            "note": "no_cooperative_squawk",
            "vendor_track": "ADSB-NULL",
            "empty_sector": True,
        },
        {
            "source_id": "EO_SKY_WATCH",
            "entity_id": "EO-DELTA-WING-BRAVO",
            "latitude": _CUE_LAT,
            "longitude": _CUE_LON,
            "speed_kt": 100.0,
            "heading_deg": 248.0,
            "confidence": 0.42,
            "observed_at": (now - timedelta(seconds=8)).isoformat(),
            "modality": "optical",
            "note": "delta_wing_thermal_silhouette",
            "altitude_m_est": 160,
            "blur": True,
            "vendor_track": "EO-DELTA-WING-BRAVO",
        },
        {
            "source_id": "GAP_FILLER_RADAR",
            "entity_id": "RADAR-AIR-551",
            "latitude": _RADAR_LAT,
            "longitude": _RADAR_LON,
            "speed_kt": 105.0,
            "heading_deg": 248.0,
            "confidence": 0.84,
            "observed_at": now.isoformat(),
            "modality": "radar",
            "note": "intermittent_low_rcs_clutter_contacts",
            "altitude_m_est": 200,
            "contact_count": _EXPECTED_RADAR_CONTACTS,
            "vendor_track": "RADAR-AIR-551",
        },
        {
            "source_id": "COASTAL_ACOUSTIC_ARRAY",
            "entity_id": "ACOUSTIC-SHADED-HARMONIC",
            "latitude": (_CUE_LAT + _RADAR_LAT) / 2,
            "longitude": _CUE_LON,
            "speed_kt": 0.0,
            "confidence": 0.72,
            "observed_at": (now - timedelta(seconds=6)).isoformat(),
            "modality": "acoustic",
            "note": "two_stroke_moped_harmonic_shahed",
            "engine_signature": "2stroke_moped",
            "vendor_track": "ACOUSTIC-SHADED-HARMONIC",
        },
        {
            "source_id": "RF_PASSIVE_ARRAY",
            "entity_id": "RF-SILENT-SCAN",
            "latitude": (_CUE_LAT + _RADAR_LAT) / 2,
            "longitude": _CUE_LON,
            "speed_kt": 0.0,
            "confidence": 0.7,
            "observed_at": (now - timedelta(seconds=2)).isoformat(),
            "modality": "rf",
            "note": "no_emitter_detected_autonomous_gps_ins",
            "rf_silent": True,
            "control_mode": "GPS_INS_WAYPOINT",
            "vendor_track": "RF-SILENT-SCAN",
        },
    ]


def _claimed_count(obs: Observation) -> int:
    raw = obs.attributes.get("claimed_count")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    parsed = parse_osint_text(
        obs.attributes.get("intel_text"),
        fallback_count=_FALLBACK_CLAIMED_COUNT,
    )
    return int(parsed.claimed_count or 0)


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    social = [o for o in graph.observations if o.modality == "social"]
    optical = [o for o in graph.observations if o.modality == "optical"]
    radar = [o for o in graph.observations if o.modality == "radar"]
    adsb = [o for o in graph.observations if o.modality == "adsb"]
    rf = [o for o in graph.observations if o.modality == "rf"]
    acoustic = [o for o in graph.observations if o.modality == "acoustic"]

    if not social or not optical or not radar or not acoustic:
        return None

    social_count = max((_claimed_count(o) for o in social), default=0)
    radar_count = sum(int(o.attributes.get("contact_count", 0) or 0) for o in radar)
    blur_optical = [o for o in optical if o.confidence <= 0.45 or bool(o.attributes.get("blur"))]
    if social_count < _MIN_CLAIMED_COUNT or radar_count != _EXPECTED_RADAR_CONTACTS or not blur_optical:
        return None

    cue = max(social + blur_optical, key=lambda o: o.confidence)
    rad = max(radar, key=lambda o: o.confidence)
    mismatch = haversine_m(cue.latitude, cue.longitude, rad.latitude, rad.longitude)
    if mismatch < 1_000.0:
        return None

    rf_silent = any(bool(o.attributes.get("rf_silent")) for o in rf) or not rf
    empty_adsb = any(bool(o.attributes.get("empty_sector")) for o in adsb) or not adsb
    if not (rf_silent and empty_adsb):
        return None

    eo_conf = min(o.confidence for o in blur_optical)
    warning_min = 4.0
    amber = "COUNT_AND_BEARING_MISMATCH"
    intel = str(social[0].attributes.get("intel_text") or "")
    picture = (
        f"AMBER {amber} (~{warning_min:.0f} min): airborne passenger OSINT claims "
        f"~{social_count} Shahed-class airframes; gap-filler radar holds {radar_count} intermittent "
        f"contacts ~{mismatch:.0f} m north (sea clutter / terrain masking); EO/IR delta-wing "
        f"conf={eo_conf:.2f}; acoustic 2-stroke harmonic corroborates. "
        f"RF_SILENT_AUTONOMOUS (GPS/INS waypoints) — RF C2 jam useless; cue GNSS denial + GBAD."
    )
    hypo = (
        "If CIVILIAN_SOCIAL_RECON exaggerates count, radar+acoustic+EO still warrant non-kinetic "
        f"cueing (not 50× SAM shots). If GAP_FILLER_RADAR under-counts due to clutter, the "
        f"passenger claim of ~{social_count} remains the saturation planning figure. "
        "Autonomous GPS/INS flight invalidates conventional RF soft-kill as primary defeat."
    )
    track = graph.get_track(rad.entity_hint or rad.source_id)
    if track is None:
        for candidate in graph.all_tracks():
            if (
                rad.source_id in candidate.source_ids
                or rad.observation_id in candidate.observation_ids
            ):
                track = candidate
                break
    if track is None:
        return None

    breakdown = {
        "social": {
            "sources": [o.source_id for o in social],
            "claimed_count": social_count,
            "intel_text": intel,
            "claim": f"~{social_count} Shahed-class (airborne passenger OSINT)",
        },
        "radar": {
            "sources": [o.source_id for o in radar],
            "contact_count": radar_count,
            "claim": f"{radar_count} intermittent contacts (clutter blindspots)",
        },
        "optical": {
            "sources": [o.source_id for o in blur_optical],
            "confidence": eo_conf,
            "claim": "delta-wing thermal / low-confidence EO",
        },
        "acoustic": {
            "sources": [o.source_id for o in acoustic],
            "claim": "2-stroke moped harmonic (Shahed-class)",
        },
        "adsb": {"sources": [o.source_id for o in adsb], "claim": "empty sector"},
        "rf": {
            "sources": [o.source_id for o in rf],
            "claim": "RF_SILENT_AUTONOMOUS — GPS/INS waypoint",
            "finding": "RF_SILENT_AUTONOMOUS",
        },
        "amber_alert": amber,
        "resolution_path": ["CUE_AND_IDENTIFY", "GNSS_DENIAL_AND_GBAD_CUE"],
    }

    return Finding(
        scenario_id="S2_osint_swarm",
        track_id=track.track_id,
        threat_class="attritable_air_incursion",
        warning_minutes_est=warning_min,
        mismatch_m=mismatch,
        confidence=min(0.88, 0.45 + 0.005 * social_count + 0.08 * radar_count),
        picture_summary=picture,
        adversarial_hypothesis=hypo,
        spoof_sources=[o.source_id for o in social + adsb],
        approach_sources=[o.source_id for o in radar + blur_optical + acoustic],
        other_sources=[o.source_id for o in rf],
        message=picture,
        amber_alert=amber,
        source_breakdown=breakdown,
    )


def _build_coa(
    graph: SpatialEntityGraph, finding: Finding, timeout_seconds: float
) -> CourseOfAction:
    # Final sealed tasking after cue: local GNSS denial + GBAD point-defense cue.
    # Contact airspeed must not trip surface USV speed interlocks.
    return make_tier1_coa(
        graph,
        finding,
        intent="GNSS_DENIAL_AND_GBAD_CUE",
        timeout_seconds=timeout_seconds,
        apply_contact_speed=False,
    )


SPEC = Scenario(
    id="S2_osint_swarm",
    title="Airborne OSINT & Autonomous Shahed Swarm",
    threat_class="attritable_air_incursion",
    warning_minutes_est=4.0,
    narrative=(
        "Airborne passenger OSINT cues ~50 Shahed-class airframes; gap-filler radar holds only "
        "intermittent clutter contacts; RF silence proves GPS/INS autonomy. Correlate acoustic + "
        "EO, then task GNSS denial alongside GBAD point-defense cue — not kinetic exhaustion."
    ),
    asset_label="Cue / EW / GBAD Proxy-01",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
