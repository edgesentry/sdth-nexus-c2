"""19-step temporal event timelines for demo playback (PS 04 §2-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.scenarios.base import get_scenario

# S2 cue / radar geometry (must match s2_air_corridor_attritable)
_CUE_LAT, _CUE_LON = 1.3510, 103.9900
_RADAR_LAT, _RADAR_LON = 1.3618, 103.9900

_INTEL_RUMOR = "Telegram chatter: many drones over the coast - unverified."
_INTEL_FILTERED = (
    "Telegram/Instagram recon: ~20 cheap drones inbound - filtered OSINT estimate "
    "3 Shahed-136 class airframes toward Objective Bravo, T+4 min."
)

# Wall-clock offsets (seconds before T-00) for steps 01-19
_T_MINUS: tuple[int, ...] = (
    60,
    56,
    52,
    48,
    45,  # 01-05 early recon
    40,
    36,
    32,
    28,
    25,  # 06-10 radar lock + optical slew
    20,
    17,
    15,
    12,
    10,  # 11-15 EO blur + amber
    5,
    3,
    1,
    0,  # 16-19 warning -> HITL -> tasking cue
)


@dataclass(frozen=True)
class StreamStep:
    step: int
    t_minus_s: int
    band: str
    label: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def observed_at(self, t0: datetime) -> str:
        return (t0 - timedelta(seconds=self.t_minus_s)).isoformat()


def _band_for(step: int) -> str:
    if step <= 5:
        return "early_recon"
    if step <= 10:
        return "radar_optical_lock"
    if step <= 15:
        return "amber_contradiction"
    return "warning_tasking"


def _evt(
    *,
    t0: datetime,
    t_minus: int,
    source_id: str,
    entity_id: str,
    modality: str,
    lat: float,
    lon: float,
    confidence: float,
    speed_kt: float = 0.0,
    heading_deg: float | None = None,
    **attrs: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "source_id": source_id,
        "entity_id": entity_id,
        "latitude": lat,
        "longitude": lon,
        "speed_kt": speed_kt,
        "confidence": confidence,
        "observed_at": (t0 - timedelta(seconds=t_minus)).isoformat(),
        "modality": modality,
        **attrs,
    }
    if heading_deg is not None:
        body["heading_deg"] = heading_deg
    return body


def _build_s2_timeline(t0: datetime) -> list[StreamStep]:
    """Hero timeline: Amber must not fire before band 11-15."""
    steps: list[StreamStep] = []

    # --- 01-05: early recon / rumors / sparse radar ---
    early: list[tuple[str, list[dict[str, Any]]]] = [
        (
            "social_rumor_seed",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[0],
                    source_id="CIVILIAN_SOCIAL_RECON",
                    entity_id="OSINT-SWARM-CLAIM",
                    modality="social",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.28,
                    note="unfiltered_coastal_rumor",
                    intel_text=_INTEL_RUMOR,
                    claimed_count=0,
                    objective="Objective Bravo",
                    vendor_track="OSINT-SWARM-CLAIM",
                )
            ],
        ),
        (
            "social_rumor_amplify",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[1],
                    source_id="CIVILIAN_SOCIAL_RECON",
                    entity_id="OSINT-SWARM-CLAIM",
                    modality="social",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.35,
                    note="exaggerated_swarm_chatter",
                    intel_text="Instagram: '20 drones' - still unfiltered.",
                    claimed_count=0,
                    objective="Objective Bravo",
                    vendor_track="OSINT-SWARM-CLAIM",
                )
            ],
        ),
        (
            "sparse_radar_noise",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[2],
                    source_id="GAP_FILLER_RADAR",
                    entity_id="RADAR-NOISE-EARLY",
                    modality="radar",
                    lat=_CUE_LAT + 0.002,
                    lon=_CUE_LON + 0.001,
                    confidence=0.22,
                    speed_kt=40.0,
                    heading_deg=240.0,
                    note="sparse_unassociated_blip",
                    contact_count=0,
                    vendor_track="RADAR-NOISE-EARLY",
                )
            ],
        ),
        (
            "recon_chatter_persist",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[3],
                    source_id="CIVILIAN_SOCIAL_RECON",
                    entity_id="OSINT-SWARM-CLAIM",
                    modality="social",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.40,
                    note="recon_net_still_noisy",
                    intel_text=_INTEL_RUMOR,
                    claimed_count=0,
                    vendor_track="OSINT-SWARM-CLAIM",
                )
            ],
        ),
        (
            "sparse_radar_fade",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[4],
                    source_id="GAP_FILLER_RADAR",
                    entity_id="RADAR-NOISE-EARLY",
                    modality="radar",
                    lat=_CUE_LAT + 0.0015,
                    lon=_CUE_LON + 0.0008,
                    confidence=0.18,
                    speed_kt=35.0,
                    note="blip_fading",
                    contact_count=0,
                    vendor_track="RADAR-NOISE-EARLY",
                )
            ],
        ),
    ]

    # --- 06-10: coastal radar lock + optical slew ---
    mid: list[tuple[str, list[dict[str, Any]]]] = [
        (
            "radar_lock_inbound",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[5],
                    source_id="GAP_FILLER_RADAR",
                    entity_id="RADAR-AIR-551",
                    modality="radar",
                    lat=_RADAR_LAT,
                    lon=_RADAR_LON,
                    confidence=0.70,
                    speed_kt=85.0,
                    heading_deg=248.0,
                    note="high_speed_inbound_lock",
                    altitude_m_est=220,
                    contact_count=0,  # building lock; count sealed later so detect sum == 1
                    vendor_track="RADAR-AIR-551",
                )
            ],
        ),
        (
            "radar_lock_strengthen",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[6],
                    source_id="GAP_FILLER_RADAR",
                    entity_id="RADAR-AIR-551",
                    modality="radar",
                    lat=_RADAR_LAT,
                    lon=_RADAR_LON,
                    confidence=0.78,
                    speed_kt=88.0,
                    heading_deg=248.0,
                    note="track_quality_up",
                    altitude_m_est=210,
                    contact_count=0,
                    vendor_track="RADAR-AIR-551",
                )
            ],
        ),
        (
            "optical_slew_start",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[7],
                    source_id="EO_SKY_WATCH",
                    entity_id="EO-BLUR-OBJ-BRAVO",
                    modality="optical",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.68,
                    speed_kt=65.0,
                    heading_deg=250.0,
                    note="camera_slewing_to_cue",
                    altitude_m_est=180,
                    blur=False,
                    vendor_track="EO-BLUR-OBJ-BRAVO",
                )
            ],
        ),
        (
            "optical_slew_hold",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[8],
                    source_id="EO_SKY_WATCH",
                    entity_id="EO-BLUR-OBJ-BRAVO",
                    modality="optical",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.62,
                    speed_kt=68.0,
                    heading_deg=250.0,
                    note="slew_hold_no_id",
                    blur=False,
                    vendor_track="EO-BLUR-OBJ-BRAVO",
                )
            ],
        ),
        (
            "radar_firm_single_contact",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[9],
                    source_id="GAP_FILLER_RADAR",
                    entity_id="RADAR-AIR-551",
                    modality="radar",
                    lat=_RADAR_LAT,
                    lon=_RADAR_LON,
                    confidence=0.84,
                    speed_kt=90.0,
                    heading_deg=248.0,
                    note="single_weak_return_fast_inbound",
                    altitude_m_est=200,
                    contact_count=1,
                    vendor_track="RADAR-AIR-551",
                )
            ],
        ),
    ]

    # --- 11-15: EO blur + amber contradiction ---
    amber: list[tuple[str, list[dict[str, Any]]]] = [
        (
            "social_filtered_count_3",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[10],
                    source_id="CIVILIAN_SOCIAL_RECON",
                    entity_id="OSINT-SWARM-CLAIM",
                    modality="social",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.55,
                    note="exaggerated_then_filtered_swarm_claim",
                    intel_text=_INTEL_FILTERED,
                    claimed_count=3,
                    objective="Objective Bravo",
                    vendor_track="OSINT-SWARM-CLAIM",
                )
            ],
        ),
        (
            "adsb_empty_sector",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[11],
                    source_id="ADS_B_SECTOR_EMPTY",
                    entity_id="ADSB-NULL-SECTOR",
                    modality="adsb",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.4,
                    note="no_cooperative_squawk",
                    vendor_track="ADSB-NULL",
                    empty_sector=True,
                )
            ],
        ),
        (
            "eo_blur_amber_threshold",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[12],
                    source_id="EO_SKY_WATCH",
                    entity_id="EO-BLUR-OBJ-BRAVO",
                    modality="optical",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.42,
                    speed_kt=70.0,
                    heading_deg=250.0,
                    note="low_confidence_blur_yolo_box",
                    altitude_m_est=160,
                    blur=True,
                    vendor_track="EO-BLUR-OBJ-BRAVO",
                )
            ],
        ),
        (
            "rf_silent_confirm",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[13],
                    source_id="RF_PASSIVE_ARRAY",
                    entity_id="RF-SILENT-SCAN",
                    modality="rf",
                    lat=(_CUE_LAT + _RADAR_LAT) / 2,
                    lon=_CUE_LON,
                    confidence=0.7,
                    note="no_emitter_detected",
                    rf_silent=True,
                    vendor_track="RF-SILENT-SCAN",
                )
            ],
        ),
        (
            "amber_reinforced",
            [
                _evt(
                    t0=t0,
                    t_minus=_T_MINUS[14],
                    source_id="CIVILIAN_SOCIAL_RECON",
                    entity_id="OSINT-SWARM-CLAIM",
                    modality="social",
                    lat=_CUE_LAT,
                    lon=_CUE_LON,
                    confidence=0.58,
                    note="count_claim_holds",
                    intel_text=_INTEL_FILTERED,
                    claimed_count=3,
                    objective="Objective Bravo",
                    vendor_track="OSINT-SWARM-CLAIM",
                )
            ],
        ),
    ]

    # --- 16-19: warning picture / HITL / tasking cues (no new sensors required) ---
    late: list[tuple[str, list[dict[str, Any]]]] = [
        ("warning_picture_ready", []),
        ("hitl_gate_countdown", []),
        ("tasking_proposal_cue", []),
        ("recipient_ack_cue", []),
    ]

    packed = early + mid + amber + late
    assert len(packed) == 19
    for i, (label, events) in enumerate(packed, start=1):
        steps.append(
            StreamStep(
                step=i,
                t_minus_s=_T_MINUS[i - 1],
                band=_band_for(i),
                label=label,
                events=events,
            )
        )
    return steps


def _spread_scenario_events(scenario_id: str, t0: datetime) -> list[StreamStep]:
    """Non-S2 fallback: place build_events() across the 19-step clock by observed_at."""
    scenario = get_scenario(scenario_id)
    raw = scenario.build_events()
    # Re-stamp onto the 19-step grid: first events early, last events late.
    n = max(len(raw), 1)
    steps: list[StreamStep] = []
    for i in range(19):
        t_minus = _T_MINUS[i]
        events: list[dict[str, Any]] = []
        # Drop each original event onto the step whose index maps proportionally.
        for j, ev in enumerate(raw):
            target_step = 1 + int(j * 18 / max(n - 1, 1)) if n > 1 else 10
            target_step = min(19, max(1, target_step))
            if target_step == i + 1:
                stamped = dict(ev)
                stamped["observed_at"] = (t0 - timedelta(seconds=t_minus)).isoformat()
                events.append(stamped)
        steps.append(
            StreamStep(
                step=i + 1,
                t_minus_s=t_minus,
                band=_band_for(i + 1),
                label=f"{scenario_id.lower()}_step_{i + 1:02d}",
                events=events,
            )
        )
    return steps


def build_stream_timeline(
    scenario_id: str = "S2",
    *,
    t0: datetime | None = None,
) -> list[StreamStep]:
    """Return 19 StreamSteps from T-60s -> T-00s for incremental ontology ingest."""
    anchor = t0 or datetime.now(UTC)
    key = scenario_id.strip().upper()
    if key == "S2":
        return _build_s2_timeline(anchor)
    # Validate scenario exists
    get_scenario(key)
    return _spread_scenario_events(key, anchor)
