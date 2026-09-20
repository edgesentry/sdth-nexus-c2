"""S2 — Air corridor Shahed swarm contradiction (Slide 04 hero)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

from app.adapters.osint_text import enrich_social_event, parse_osint_text
from app.agent import make_tier1_coa
from app.scenarios.base import Finding, Scenario

# ~1,200 m due north of the social/EO cue (Objective Bravo approach corridor)
_CUE_LAT, _CUE_LON = 1.3510, 103.9900
_RADAR_LAT, _RADAR_LON = 1.3618, 103.9900  # ≈1,200 m north

_INTEL_TEXT = (
    "Telegram/Instagram recon: ~20 cheap drones inbound — filtered OSINT estimate "
    "3 Shahed-136 class airframes toward Objective Bravo, T+4 min."
)
# Hardcoded fallback if OSINT parse fails (issue #59).
_FALLBACK_CLAIMED_COUNT = 3


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
            "note": "exaggerated_then_filtered_swarm_claim",
            "intel_text": _INTEL_TEXT,
            "objective": "Objective Bravo",
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
            "entity_id": "EO-BLUR-OBJ-BRAVO",
            "latitude": _CUE_LAT,
            "longitude": _CUE_LON,
            "speed_kt": 70.0,
            "heading_deg": 250.0,
            "confidence": 0.42,
            "observed_at": (now - timedelta(seconds=8)).isoformat(),
            "modality": "optical",
            "note": "low_confidence_blur_yolo_box",
            "altitude_m_est": 160,
            "blur": True,
            "vendor_track": "EO-BLUR-OBJ-BRAVO",
        },
        {
            "source_id": "GAP_FILLER_RADAR",
            "entity_id": "RADAR-AIR-551",
            "latitude": _RADAR_LAT,
            "longitude": _RADAR_LON,
            "speed_kt": 90.0,
            "heading_deg": 248.0,
            "confidence": 0.84,
            "observed_at": now.isoformat(),
            "modality": "radar",
            "note": "single_weak_return_fast_inbound",
            "altitude_m_est": 200,
            "contact_count": 1,
            "vendor_track": "RADAR-AIR-551",
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
            "note": "no_emitter_detected",
            "rf_silent": True,
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

    if not social or not optical or not radar:
        return None

    social_count = max((_claimed_count(o) for o in social), default=0)
    radar_count = sum(int(o.attributes.get("contact_count", 1)) for o in radar)
    blur_optical = [o for o in optical if o.confidence <= 0.45 or bool(o.attributes.get("blur"))]
    if social_count < 3 or radar_count != 1 or not blur_optical:
        return None

    # Bearing / position disagreement between social-EO cue and radar contact
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
        f"AMBER {amber} (~{warning_min:.0f} min): civilian social/recon claims "
        f"{social_count} inbound airframes; gap-filler radar holds {radar_count} contact "
        f"~{mismatch:.0f} m north; EO/IR blur conf={eo_conf:.2f}. RF-silent, no ADS-B — "
        "do not fuse into one hallucinated track; cue identify only."
    )
    hypo = (
        "If CIVILIAN_SOCIAL_RECON is exaggerated rumor, radar+EO still warrant a cue "
        f"(not a kinetic shot). If GAP_FILLER_RADAR is false, the social claim of "
        f"{social_count} remains unverified and collapses. Low-confidence EO blur alone "
        "must not task."
    )
    # Task the radar contact track (best kinematic truth for cue waypoint)
    track = graph.get_track(rad.entity_hint or rad.source_id)
    if track is None:
        # Nearby association may have folded radar into another track id
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
            "claim": f"{social_count} Shahed-class toward Objective Bravo",
        },
        "radar": {
            "sources": [o.source_id for o in radar],
            "contact_count": radar_count,
            "claim": f"1 contact ~{mismatch:.0f} m north of cue",
        },
        "optical": {
            "sources": [o.source_id for o in blur_optical],
            "confidence": eo_conf,
            "claim": "low-confidence blur / YOLO box",
        },
        "adsb": {"sources": [o.source_id for o in adsb], "claim": "empty sector"},
        "rf": {"sources": [o.source_id for o in rf], "claim": "RF silent"},
        "amber_alert": amber,
    }

    return Finding(
        scenario_id="S2",
        track_id=track.track_id,
        threat_class="attritable_air_incursion",
        warning_minutes_est=warning_min,
        mismatch_m=mismatch,
        confidence=min(0.88, 0.45 + 0.1 * social_count + 0.15 * len(radar)),
        picture_summary=picture,
        adversarial_hypothesis=hypo,
        spoof_sources=[o.source_id for o in social + adsb],
        approach_sources=[o.source_id for o in radar + blur_optical],
        other_sources=[o.source_id for o in rf],
        message=picture,
        amber_alert=amber,
        source_breakdown=breakdown,
    )


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
    title="Air Corridor — Shahed Swarm Contradiction",
    threat_class="attritable_air_incursion",
    warning_minutes_est=4.0,
    narrative=(
        "Slide 04 hero: civilian social/recon says three cheap airframes; radar sees one "
        "contact a kilometre north; EO shows only blur. Flag the count-and-bearing amber "
        "contradiction and cue identification — not a polished kinetic demo."
    ),
    asset_label="Cue / ISR node Proxy-01",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
