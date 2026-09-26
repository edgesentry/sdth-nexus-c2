"""Defense scenarios S1-S4."""

from __future__ import annotations

import pytest
from app.adapters.southbound_sensor import normalize_sensor_event
from app.main import run_c2_cycle
from app.scenarios.base import get_scenario, list_scenario_ids
from core.coa import ActionTier, GateVerdict
from core.ontology import SpatialEntityGraph


@pytest.mark.parametrize(
    "sid",
    ["S1_ais_spoof", "S2_osint_swarm", "S3_sar_ais", "S4_fusion_disagreement"],
)
def test_scenario_builds_finding_and_tier1_coa(sid: str) -> None:
    scenario = get_scenario(sid)
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    events = scenario.build_events()
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None, f"{sid} produced no finding"
    assert finding.picture_summary
    assert finding.adversarial_hypothesis
    assert finding.warning_minutes_est > 0
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.tier == ActionTier.TIER_1_HITL
    assert len(coa.corroborating_sources) >= 1
    assert len(coa.raw_input_digest) == 64


def test_s1_no_shared_entity_id() -> None:
    scenario = get_scenario("S1_ais_spoof")
    events = scenario.build_events()
    entity_ids = [e["entity_id"] for e in events]
    assert len(set(entity_ids)) == len(entity_ids)
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.mismatch_m > 500
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.intent == "ISR_IDENTIFY_CONTACT"


def test_s2_hero_count_and_bearing_amber() -> None:
    scenario = get_scenario("S2_osint_swarm")
    events = scenario.build_events()
    social = [e for e in events if e.get("modality") == "social"]
    assert social
    assert social[0].get("claimed_count") == 50
    assert any(e.get("modality") == "acoustic" for e in events)
    assert "intel_text" in social[0]
    optical = [e for e in events if e.get("modality") == "optical"]
    assert optical and optical[0]["confidence"] == 0.42

    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert == "COUNT_AND_BEARING_MISMATCH"
    assert finding.mismatch_m >= 1_000.0
    assert finding.source_breakdown.get("social", {}).get("claimed_count") == 50
    assert finding.source_breakdown.get("radar", {}).get("contact_count") == 4
    assert "AMBER" in finding.picture_summary or "COUNT_AND_BEARING" in finding.picture_summary
    assert finding.source_breakdown.get("rf", {}).get("finding") == "RF_SILENT_AUTONOMOUS"
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.intent == "GNSS_DENIAL_AND_GBAD_CUE"
    assert coa.metadata.get("amber_alert") == "COUNT_AND_BEARING_MISMATCH"


def test_s3_sar_ais_picture() -> None:
    scenario = get_scenario("S3_sar_ais")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in scenario.build_events()])
    finding = scenario.detect(graph)
    assert finding is not None
    text = finding.picture_summary.lower()
    assert "sar" in text or "space" in text
    assert finding.amber_alert == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
    assert finding.source_breakdown.get("kinematics", {}).get("radar_in_envelope") is True
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.intent == "APPROACH_PATROL"


def test_s4_fusion_disagreement_picture() -> None:
    scenario = get_scenario("S4_fusion_disagreement")
    events = scenario.build_events()
    assert len(events) >= 40
    sources = {e.get("source") for e in events}
    assert "AIR_RADAR" in sources
    assert "AIR_EOIR" in sources
    assert "ARMY_EOIR" in sources
    assert "NAVY_COASTAL_RADAR" in sources

    graph = SpatialEntityGraph(associate_radius_m=50_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert is not None
    assert "MULTI_SITE_COUNT_DISAGREEMENT" in finding.amber_alert
    assert finding.source_breakdown.get("ew_negative") is True
    assert len(finding.source_breakdown.get("mpstar_tracks", [])) >= 5
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.intent == "CUE_AND_IDENTIFY"


@pytest.mark.parametrize("sid", list_scenario_ids())
@pytest.mark.asyncio
async def test_c2_cycle_stub_approve_each_scenario(sid: str) -> None:
    verdict = await run_c2_cycle(
        scenario_id=sid,
        auto_decision="y",
        use_stub=True,
        gate_timeout_sec=2.0,
    )
    assert verdict == GateVerdict.APPROVED
