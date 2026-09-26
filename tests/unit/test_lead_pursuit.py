"""Lead-pursuit Point of Interception (issue #58)."""

from __future__ import annotations

from math import cos, radians

import pytest
from app.adapters.southbound_sensor import normalize_sensor_event
from app.agent import make_tier1_coa
from app.scenarios.base import get_scenario
from core.kinematics import (
    DEFAULT_OWN_LATITUDE,
    DEFAULT_OWN_LONGITUDE,
    DEFAULT_OWN_SPEED_MPS,
    KT_TO_MPS,
    M_PER_DEG_LAT,
    compute_lead_pursuit_poi,
    displace_m,
)
from core.ontology import SpatialEntityGraph, haversine_m


def test_static_contact_uses_current_coords() -> None:
    poi = compute_lead_pursuit_poi(
        1.25,
        103.85,
        contact_heading_deg=None,
        contact_speed_mps=0.0,
        own_latitude=1.23,
        own_longitude=103.85,
        own_speed_mps=15.0,
    )
    assert poi.method == "static_contact"
    assert poi.latitude == pytest.approx(1.25)
    assert poi.longitude == pytest.approx(103.85)
    assert poi.eta_sec == pytest.approx(haversine_m(1.23, 103.85, 1.25, 103.85) / 15.0)


def test_collision_course_meets_target_at_eta() -> None:
    """Own platform due south of a northbound contact — intercept ahead on track."""
    contact_lat, contact_lon = 1.2500, 103.8500
    heading = 0.0  # north
    contact_speed = 5.0  # m/s
    own_lat = 1.2400
    own_lon = 103.8500
    own_speed = 10.0

    poi = compute_lead_pursuit_poi(
        contact_lat,
        contact_lon,
        contact_heading_deg=heading,
        contact_speed_mps=contact_speed,
        own_latitude=own_lat,
        own_longitude=own_lon,
        own_speed_mps=own_speed,
    )
    assert poi.method == "collision_course"
    assert poi.eta_sec > 0.0

    # Contact position at ETA must match POI
    expected_lat, expected_lon = displace_m(
        contact_lat, contact_lon, heading, contact_speed * poi.eta_sec
    )
    assert poi.latitude == pytest.approx(expected_lat, abs=1e-6)
    assert poi.longitude == pytest.approx(expected_lon, abs=1e-6)

    # Own platform traveling straight to POI covers the range in ~eta_sec
    # (haversine vs equirectangular ENU solver → allow small geometric residual)
    range_m = haversine_m(own_lat, own_lon, poi.latitude, poi.longitude)
    assert range_m / own_speed == pytest.approx(poi.eta_sec, rel=5e-3)


def test_lead_along_track_when_own_too_slow() -> None:
    """Fast air contact: no catch-up → along-track lead fallback."""
    poi = compute_lead_pursuit_poi(
        1.3618,
        103.9900,
        contact_heading_deg=248.0,
        contact_speed_mps=90.0 * KT_TO_MPS,
        own_latitude=DEFAULT_OWN_LATITUDE,
        own_longitude=DEFAULT_OWN_LONGITUDE,
        own_speed_mps=DEFAULT_OWN_SPEED_MPS,
    )
    assert poi.method == "lead_along_track"
    assert poi.eta_sec > 0.0
    # POI must differ from the historical contact snapshot
    assert haversine_m(poi.latitude, poi.longitude, 1.3618, 103.9900) > 50.0


def test_s3_coa_replaces_coords_with_poi() -> None:
    scenario = get_scenario("S3_sar_ais")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in scenario.build_events()])
    finding = scenario.detect(graph)
    assert finding is not None
    coa = make_tier1_coa(graph, finding, intent="APPROACH_PATROL")
    assert coa.intent == "APPROACH_PATROL"
    assert "poi" in coa.metadata
    assert coa.metadata["eta_sec"] == coa.metadata["poi"]["eta_sec"]
    assert coa.metadata["poi"]["method"] in {
        "collision_course",
        "lead_along_track",
        "static_contact",
    }
    contact = coa.metadata["contact_coordinates"]
    assert coa.target_coordinates[0] == pytest.approx(coa.metadata["poi"]["latitude"])
    assert coa.target_coordinates[1] == pytest.approx(coa.metadata["poi"]["longitude"])
    if coa.metadata["poi"]["method"] != "static_contact":
        assert (
            haversine_m(
                contact[0], contact[1], coa.target_coordinates[0], coa.target_coordinates[1]
            )
            > 1.0
        )
    # Waypoint equals metadata POI
    assert "eta_sec" in coa.metadata


def test_s2_coa_exposes_poi_metadata() -> None:
    scenario = get_scenario("S2_osint_swarm")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in scenario.build_events()])
    finding = scenario.detect(graph)
    assert finding is not None
    coa = make_tier1_coa(graph, finding, intent="GNSS_DENIAL_AND_GBAD_CUE", apply_contact_speed=False)
    assert coa.metadata.get("poi")
    assert coa.metadata["poi"]["method"] in {"collision_course", "lead_along_track"}
    assert coa.speed_kt is None  # cue node must not trip surface interlocks


def test_s1_does_not_apply_lead_pursuit() -> None:
    scenario = get_scenario("S1_ais_spoof")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in scenario.build_events()])
    finding = scenario.detect(graph)
    assert finding is not None
    coa = make_tier1_coa(graph, finding, intent="ISR_IDENTIFY_CONTACT")
    assert "poi" not in coa.metadata
    assert "eta_sec" not in coa.metadata


def test_eastbound_collision_geometry() -> None:
    """Sanity: contact due east of own, heading east — intercept further east."""
    own_lat, own_lon = 1.25, 103.80
    contact_lat = own_lat
    # ~1 km east
    contact_lon = own_lon + 1000.0 / (M_PER_DEG_LAT * cos(radians(own_lat)))
    poi = compute_lead_pursuit_poi(
        contact_lat,
        contact_lon,
        contact_heading_deg=90.0,
        contact_speed_mps=5.0,
        own_latitude=own_lat,
        own_longitude=own_lon,
        own_speed_mps=10.0,
    )
    assert poi.method == "collision_course"
    assert poi.longitude > contact_lon
