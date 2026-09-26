"""S1 Trojan — Happy Tug mothership + velocity mismatch (issue #116).

Consumes Arun/marun canonical JSONL. Detects AIS (~6 kt) vs coastal radar (~120 kt)
disagreement and optional Air/Army story LOB triangulation toward the mothership.
"""

from __future__ import annotations

from typing import Any

from core.coa import ActionTier, CourseOfAction
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

from app.adapters.arun_canonical import load_jsonl, load_pois
from app.adapters.southbound_sensor import canonical_row_to_event
from app.agent import make_tier1_coa, speed_kt
from app.scenarios.base import Finding, Scenario

HAPPY_TUG_MMSI = "563098710"
AIS_SLOW_MAX_KT = 15.0
RADAR_FAST_MIN_KT = 80.0
MOTHERSHIP_MATCH_M = 2500.0


def _build_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in load_jsonl():
        converted = canonical_row_to_event(row)
        if converted is not None:
            events.append(converted)
    return events


def _ais_obs(graph: SpatialEntityGraph) -> list[Observation]:
    return [
        o
        for o in graph.observations
        if o.modality == "ais"
        or str(o.attributes.get("source")) == "NAVY_AIS"
        or str(o.attributes.get("mmsi")) == HAPPY_TUG_MMSI
    ]


def _fast_radar(graph: SpatialEntityGraph) -> list[Observation]:
    out: list[Observation] = []
    for o in graph.observations:
        if o.modality != "radar" and str(o.attributes.get("source")) not in {
            "NAVY_COASTAL_RADAR",
            "AIR_RADAR",
        }:
            continue
        if speed_kt(o) >= RADAR_FAST_MIN_KT:
            out.append(o)
    return out


def _story_ew(graph: SpatialEntityGraph) -> list[Observation]:
    return [o for o in graph.observations if o.attributes.get("story_lob")]


def _nearest_pair(
    slow: list[Observation], fast: list[Observation]
) -> tuple[Observation, Observation, float] | None:
    best: tuple[Observation, Observation, float] | None = None
    for a in slow:
        for b in fast:
            d = haversine_m(a.latitude, a.longitude, b.latitude, b.longitude)
            if best is None or d < best[2]:
                best = (a, b, d)
    return best


def _detect(graph: SpatialEntityGraph) -> Finding | None:
    ais = [o for o in _ais_obs(graph) if speed_kt(o) <= AIS_SLOW_MAX_KT]
    radar = _fast_radar(graph)
    if not ais or not radar:
        return None
    pair = _nearest_pair(ais, radar)
    if pair is None:
        return None
    ais_o, radar_o, dist_m = pair
    if dist_m > MOTHERSHIP_MATCH_M * 4:
        # Still flag if both present in scenario (demo may use Jurong AIS + local radar).
        # Prefer collocated; otherwise use the fastest radar + slowest AIS narrative pair.
        pass

    ais_kt = speed_kt(ais_o)
    radar_kt = speed_kt(radar_o)
    if radar_kt < RADAR_FAST_MIN_KT or ais_kt > AIS_SLOW_MAX_KT:
        return None

    track_id = None
    # Prefer track that contains the radar observation (threat kinematics).
    for tid, track in graph.tracks.items():
        if radar_o.observation_id in track.observation_ids:
            track_id = tid
            break
    if track_id is None:
        for tid, track in graph.tracks.items():
            if ais_o.observation_id in track.observation_ids:
                track_id = tid
                break
    if track_id is None:
        return None

    vessel = ais_o.attributes.get("vessel_name", "HAPPY TUG 8")
    mmsi = ais_o.attributes.get("mmsi", HAPPY_TUG_MMSI)
    ew = _story_ew(graph)
    air_ew = [o for o in ew if str(o.attributes.get("service")) == "air_force"]
    army_ew = [o for o in ew if str(o.attributes.get("service")) == "army"]
    triangulated = bool(air_ew and army_ew)

    amber = "VELOCITY_MISMATCH_AIS_VS_RADAR"
    if triangulated:
        amber = "VELOCITY_MISMATCH_AIS_VS_RADAR+TRIANGULATION_MOTHERSHIP"

    # ETA to POI-01 (filled later by COA / impact helper; store rough minutes here)
    pois = load_pois()
    poi01 = next((p for p in pois if p.get("poi_id") == "POI-01"), None)
    warning_min = 3.0
    eta_by_poi: dict[str, float] = {}
    if poi01:
        from core.kinematics import kt_to_mps

        range_m = haversine_m(
            radar_o.latitude,
            radar_o.longitude,
            float(poi01["center_lat"]),
            float(poi01["center_lon"]),
        )
        speed = max(kt_to_mps(radar_kt), 1.0)
        eta_s = range_m / speed
        warning_min = eta_s / 60.0
        for poi in pois:
            d = haversine_m(
                radar_o.latitude,
                radar_o.longitude,
                float(poi["center_lat"]),
                float(poi["center_lon"]),
            )
            eta_by_poi[str(poi["poi_id"])] = round(d / speed, 1)

    return Finding(
        scenario_id="s1_trojan",
        track_id=track_id,
        threat_class="trojan_mothership_uas",
        warning_minutes_est=round(warning_min, 2),
        mismatch_m=round(dist_m, 1),
        confidence=0.91,
        picture_summary=(
            f"Navy AIS reports {vessel} (MMSI {mmsi}) at {ais_kt:.1f} kt while coastal "
            f"radar holds {radar_kt:.1f} kt UAS inbound — kinematic disagreement."
        ),
        adversarial_hypothesis=(
            "Decoy AIS on mothership; launched UAS toward Jurong CNI. "
            + (
                "Air ESM ∩ Army EW story LOBs corroborate launch sector."
                if triangulated
                else "Awaiting dual-LOB corroboration."
            )
        ),
        spoof_sources=[ais_o.source_id],
        approach_sources=[radar_o.source_id],
        other_sources=[o.source_id for o in ew],
        message=(
            f"VELOCITY_MISMATCH: AIS {ais_kt:.1f} kt vs radar {radar_kt:.1f} kt (Δ {dist_m:.0f} m)"
        ),
        amber_alert=amber,
        source_breakdown={
            "ais": {
                "claim": f"{vessel} @ {ais_kt:.1f} kt (routine traffic)",
                "mmsi": mmsi,
                "source_id": ais_o.source_id,
            },
            "radar": {
                "claim": f"UAS @ {radar_kt:.1f} kt alt {radar_o.attributes.get('altitude_m', '?')} m",
                "track_id": radar_o.attributes.get("track_id"),
                "source_id": radar_o.source_id,
            },
            "ew": {
                "air_bearing_deg": air_ew[0].attributes.get("bearing_deg") if air_ew else None,
                "army_bearing_deg": army_ew[0].attributes.get("bearing_deg") if army_ew else None,
                "triangulated": triangulated,
            },
            "poi_eta_sec": eta_by_poi,
        },
    )


def _build_coa(
    graph: SpatialEntityGraph,
    finding: Finding,
    timeout_seconds: float,
) -> CourseOfAction:
    # Dangerous Option A draft metadata (terminal SAM over CNI) — guardrail evaluates live.
    coa = make_tier1_coa(
        graph,
        finding,
        intent="TERMINAL_SAM_INTERCEPT",
        timeout_seconds=timeout_seconds,
        apply_contact_speed=False,
        speed_kt_override=None,
    )
    # Place Option A on POI-01 (overhead) so CNI debris gate fires.
    pois = load_pois()
    poi01 = next((p for p in pois if p.get("poi_id") == "POI-01"), None)
    if poi01:
        coa.target_coordinates = (float(poi01["center_lat"]), float(poi01["center_lon"]))
        coa.metadata["option_id"] = "A"
        coa.metadata["dangerous_proposal_draft"] = True
        coa.metadata["prob_hit"] = 0.98
        coa.metadata["cost_usd"] = 120_000
        coa.metadata["rationale"] = (
            "AI raw: Terminal SPYDER intercept 30 s before POI impact (98% Pk)."
        )
        coa.metadata["poi_eta_sec"] = finding.source_breakdown.get("poi_eta_sec", {})
        # Override intent metadata for interlock classification
        coa.intent = "TERMINAL_SAM_INTERCEPT"
        coa.tier = ActionTier.TIER_1_HITL
    return coa


SPEC = Scenario(
    id="s1_trojan",
    title="Trojan Mothership — Happy Tug 8 + UAS velocity mismatch",
    threat_class="trojan_mothership_uas",
    warning_minutes_est=3.0,
    narrative=(
        "Navy AIS paints Happy Tug 8 as routine 6.1 kt traffic while coastal radar "
        "holds a 120 kt UAS inbound to Jurong CNI. Optional dual EW LOBs triangulate "
        "the launch sector. Guardrail must veto terminal SAM over the tank farm."
    ),
    asset_label="HAPPY TUG 8 / RDR-NAVY-024",
    _build_events=_build_events,
    _detect=_detect,
    _build_coa=_build_coa,
)
