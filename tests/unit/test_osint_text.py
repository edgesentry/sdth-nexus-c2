"""Unit tests for Synthetic OSINT text parser (issue #59)."""

from __future__ import annotations

from app.adapters.osint_text import enrich_social_event, parse_osint_text
from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import get_scenario
from app.scenarios.s2_air_corridor_attritable import _INTEL_TEXT
from core.ontology import SpatialEntityGraph


def test_parse_s2_intel_prefers_filtered_estimate() -> None:
    result = parse_osint_text(_INTEL_TEXT)
    assert result.claimed_count == 3
    assert result.objective == "Objective Bravo"
    assert "filtered_estimate" in result.notes
    assert result.raw_count_match is not None
    assert "3" in result.raw_count_match


def test_parse_avoids_exaggerated_lead_number() -> None:
    text = "Telegram: ~20 cheap drones inbound — filtered OSINT estimate 3 airframes."
    assert parse_osint_text(text).claimed_count == 3


def test_parse_airframe_count_without_filtered_phrase() -> None:
    result = parse_osint_text("Recon: 4 Shahed-136 class airframes inbound.")
    assert result.claimed_count == 4
    assert "airframe_count" in result.notes


def test_parse_bearing_numeric_and_cardinal() -> None:
    assert parse_osint_text("swarm bearing 248°").bearing_deg == 248.0
    assert parse_osint_text("contact from the north").bearing_deg == 0.0
    assert parse_osint_text("inbound from the southwest").bearing_deg == 225.0


def test_parse_fallback_when_unparseable() -> None:
    result = parse_osint_text("Telegram chatter: many drones — unverified.", fallback_count=3)
    assert result.claimed_count == 3
    assert "fallback_count" in result.notes


def test_parse_empty_uses_fallback() -> None:
    assert parse_osint_text("", fallback_count=3).claimed_count == 3
    assert parse_osint_text(None).claimed_count is None


def test_enrich_social_event_fills_claimed_count() -> None:
    event = enrich_social_event(
        {"modality": "social", "intel_text": _INTEL_TEXT},
        fallback_count=3,
    )
    assert event["claimed_count"] == 3
    assert event.get("objective") == "Objective Bravo"
    assert "osint_parse_notes" in event


def test_enrich_keeps_explicit_claimed_count() -> None:
    event = enrich_social_event(
        {"modality": "social", "intel_text": _INTEL_TEXT, "claimed_count": 5},
        fallback_count=3,
    )
    assert event["claimed_count"] == 5


def test_s2_scenario_uses_parsed_count() -> None:
    scenario = get_scenario("S2")
    events = scenario.build_events()
    social = [e for e in events if e.get("modality") == "social"]
    assert social
    assert social[0]["claimed_count"] == 3
    assert "intel_text" in social[0]
    assert "filtered_estimate" in social[0].get("osint_parse_notes", [])

    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert == "COUNT_AND_BEARING_MISMATCH"
    assert finding.source_breakdown["social"]["claimed_count"] == 3
