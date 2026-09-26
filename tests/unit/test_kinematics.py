"""Unit tests for SAR dead-reckoning kinematics (issue #57)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import cos, radians, sin, tan

import pytest
from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import get_scenario
from core.kinematics import (
    DEFAULT_HEADING_SIGMA_DEG,
    DEFAULT_SIGMA_NAV_M,
    DEFAULT_V_EST_KT,
    DEFAULT_V_MAX_KT,
    DEFAULT_V_MIN_KT,
    KT_TO_MPS,
    M_PER_DEG_LAT,
    MAX_DT_SEC,
    associate_kinematically,
    in_reachability_envelope,
    kt_to_mps,
    project_dead_reckoning,
    project_observation,
    projected_separation_m,
    uncertainty_radius_m,
)
from core.ontology import SpatialEntityGraph, haversine_m
from core.schema import Observation

# Fixed dt fixture: assumed SAR cell, 30 min latency, 12 kt at heading 200 deg.
FIXED_DT_SEC = 1800.0
FIXED_LAT = 1.254
FIXED_LON = 103.812
FIXED_HEADING_DEG = 200.0
FIXED_SPEED_KT = 12.0
FIXED_T0 = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _expected_projection(
    lat: float,
    lon: float,
    heading_deg: float,
    speed_kt: float,
    dt_sec: float,
) -> tuple[float, float]:
    dist = speed_kt * KT_TO_MPS * dt_sec
    heading = radians(heading_deg)
    m_per_deg_lon = M_PER_DEG_LAT * cos(radians(lat))
    return (
        lat + (dist * cos(heading)) / M_PER_DEG_LAT,
        lon + (dist * sin(heading)) / m_per_deg_lon,
    )


def _sar_obs(**overrides: object) -> Observation:
    body: dict[str, object] = {
        "source_id": "SPACE_SAR_SCENE_DIFF",
        "entity_hint": "UNANNOUNCED_DARK_VESSEL_CLUSTER",
        "latitude": FIXED_LAT,
        "longitude": FIXED_LON,
        "speed_mps": kt_to_mps(FIXED_SPEED_KT),
        "heading_deg": FIXED_HEADING_DEG,
        "confidence": 0.88,
        "observed_at": FIXED_T0,
        "modality": "space_sar",
        "attributes": {"speed_kt": FIXED_SPEED_KT, "vessel_count_est": 2},
    }
    body.update(overrides)
    return Observation.model_validate(body)


def _radar_obs(lat: float, lon: float, *, dt_sec: float = FIXED_DT_SEC) -> Observation:
    return Observation(
        source_id="COASTAL_RADAR_WEST",
        entity_hint="RADAR-SAR-CUE-901",
        latitude=lat,
        longitude=lon,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        heading_deg=FIXED_HEADING_DEG,
        confidence=0.86,
        observed_at=FIXED_T0 + timedelta(seconds=dt_sec),
        modality="radar",
        attributes={"speed_kt": FIXED_SPEED_KT},
    )


def displace_east(lat: float, lon: float, distance_m: float) -> tuple[float, float]:
    m_per_deg_lon = M_PER_DEG_LAT * cos(radians(lat))
    return lat, lon + distance_m / m_per_deg_lon


def test_uncertainty_radius_matches_documented_formula() -> None:
    v_min = kt_to_mps(DEFAULT_V_MIN_KT)
    v_max = kt_to_mps(DEFAULT_V_MAX_KT)
    expected = FIXED_DT_SEC * (v_max - v_min) / 2.0 + DEFAULT_SIGMA_NAV_M
    assert uncertainty_radius_m(FIXED_DT_SEC) == pytest.approx(expected)
    assert uncertainty_radius_m(-FIXED_DT_SEC) == pytest.approx(expected)


def test_fixed_dt_projects_sar_contact() -> None:
    exp_lat, exp_lon = _expected_projection(
        FIXED_LAT, FIXED_LON, FIXED_HEADING_DEG, FIXED_SPEED_KT, FIXED_DT_SEC
    )
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=FIXED_HEADING_DEG,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    assert proj.latitude == pytest.approx(exp_lat, abs=1e-8)
    assert proj.longitude == pytest.approx(exp_lon, abs=1e-8)
    assert proj.dt_sec == pytest.approx(FIXED_DT_SEC)
    assert proj.radius_m == pytest.approx(uncertainty_radius_m(FIXED_DT_SEC))
    traveled = kt_to_mps(FIXED_SPEED_KT) * FIXED_DT_SEC
    assert proj.cross_m == pytest.approx(
        DEFAULT_SIGMA_NAV_M + abs(traveled) * tan(radians(DEFAULT_HEADING_SIGMA_DEG))
    )
    # ~11 km along-track at 12 kt * 30 min -- well beyond a 2 km static gate.
    assert haversine_m(FIXED_LAT, FIXED_LON, proj.latitude, proj.longitude) > 10_000.0


def test_radar_at_projected_point_is_inside_envelope() -> None:
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=FIXED_HEADING_DEG,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    assert in_reachability_envelope(proj, proj.latitude, proj.longitude)
    sar = _sar_obs()
    radar = _radar_obs(proj.latitude, proj.longitude)
    assert associate_kinematically(sar, radar)
    sep = projected_separation_m(sar, radar)
    assert sep is not None
    assert sep == pytest.approx(0.0, abs=1.0)


def test_abeam_radar_outside_ellipse() -> None:
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=FIXED_HEADING_DEG,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    far_lat, far_lon = displace_east(proj.latitude, proj.longitude, 15_000.0)
    assert not in_reachability_envelope(proj, far_lat, far_lon)
    sar = _sar_obs()
    radar = _radar_obs(far_lat, far_lon)
    assert not associate_kinematically(sar, radar)


def test_unknown_heading_uses_isotropic_disc() -> None:
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=None,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    assert proj.latitude == pytest.approx(FIXED_LAT)
    assert proj.longitude == pytest.approx(FIXED_LON)
    assert proj.along_m == pytest.approx(proj.cross_m)
    assert proj.radius_m == pytest.approx(
        FIXED_DT_SEC * kt_to_mps(DEFAULT_V_MAX_KT) + DEFAULT_SIGMA_NAV_M
    )
    near_lat = FIXED_LAT + 5_000.0 / M_PER_DEG_LAT
    assert in_reachability_envelope(proj, near_lat, FIXED_LON)


def test_zero_speed_sar_uses_default_v_est() -> None:
    sar = _sar_obs(speed_mps=0.0, attributes={"speed_kt": 0.0, "vessel_count_est": 2})
    t_now = FIXED_T0 + timedelta(seconds=FIXED_DT_SEC)
    proj = project_observation(sar, t_now)
    exp_lat, exp_lon = _expected_projection(
        FIXED_LAT, FIXED_LON, FIXED_HEADING_DEG, DEFAULT_V_EST_KT, FIXED_DT_SEC
    )
    assert proj.latitude == pytest.approx(exp_lat, abs=1e-8)
    assert proj.longitude == pytest.approx(exp_lon, abs=1e-8)


def test_stale_dt_beyond_max_does_not_associate() -> None:
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=FIXED_HEADING_DEG,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    sar = _sar_obs()
    radar = _radar_obs(proj.latitude, proj.longitude, dt_sec=MAX_DT_SEC + 60.0)
    assert not associate_kinematically(sar, radar)


def test_ais_does_not_kinematically_pair() -> None:
    sar = _sar_obs()
    ais = Observation(
        source_id="OPEN_AIS_SNAPSHOT",
        entity_hint="AIS-HIST-LANE-A",
        latitude=FIXED_LAT,
        longitude=FIXED_LON,
        speed_mps=kt_to_mps(8.0),
        heading_deg=90.0,
        observed_at=FIXED_T0 + timedelta(seconds=FIXED_DT_SEC),
        modality="ais",
    )
    assert not associate_kinematically(sar, ais)


def test_graph_associates_radar_via_envelope_not_static_radius() -> None:
    proj = project_dead_reckoning(
        FIXED_LAT,
        FIXED_LON,
        heading_deg=FIXED_HEADING_DEG,
        speed_mps=kt_to_mps(FIXED_SPEED_KT),
        dt_sec=FIXED_DT_SEC,
    )
    sar = _sar_obs()
    radar = _radar_obs(proj.latitude, proj.longitude)
    assert haversine_m(sar.latitude, sar.longitude, radar.latitude, radar.longitude) > 2_000.0

    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest(sar)
    track = graph.ingest(radar)
    assert "radar" in track.modalities
    assert "space_sar" in track.modalities
    assert radar.observation_id in track.observation_ids


def test_graph_rejects_far_radar() -> None:
    sar = _sar_obs()
    far_lat, far_lon = displace_east(FIXED_LAT, FIXED_LON, 40_000.0)
    radar = _radar_obs(far_lat, far_lon)
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest(sar)
    radar_track = graph.ingest(radar)
    sar_track = graph.get_track(sar.entity_hint)
    assert sar_track is not None
    assert radar_track.track_id != sar_track.track_id


def test_s3_radar_is_outside_static_cell_inside_envelope() -> None:
    scenario = get_scenario("S3_sar_ais")
    events = scenario.build_events()
    sar_ev = next(e for e in events if e["modality"] == "space_sar")
    radar_ev = next(e for e in events if e["modality"] == "radar")
    static_d = haversine_m(
        float(sar_ev["latitude"]),
        float(sar_ev["longitude"]),
        float(radar_ev["latitude"]),
        float(radar_ev["longitude"]),
    )
    assert static_d > 1_500.0
    assert static_d > 2_000.0

    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    kinematics = finding.source_breakdown["kinematics"]
    assert kinematics["radar_in_envelope"] is True
    assert kinematics["dt_sec"] == pytest.approx(1795.0, abs=5.0)
    assert kinematics["radar_distance_to_projected_m"] == pytest.approx(0.0, abs=25.0)
    assert "Dead-reckoned" in finding.picture_summary

    sar_obs = next(o for o in graph.observations if o.modality == "space_sar")
    radar_obs = next(o for o in graph.observations if o.modality == "radar")
    track = graph.get_track(sar_obs.entity_hint)
    assert track is not None
    assert radar_obs.observation_id in track.observation_ids
