"""Pitch-1: SAR CandidateEvent adapter + S3 multimodal harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.adapters.sar_candidate_event import (
    SPACE_SAR_MODALITY,
    candidate_event_to_observation,
    load_assumed_fixture,
    observation_from_assumed_fixture,
)
from app.adapters.southbound_sensor import normalize_sensor_event
from app.c2_server import app
from app.scenarios.base import get_scenario
from core.ontology import SpatialEntityGraph
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def test_fixture_maps_to_space_sar_observation() -> None:
    payload = load_assumed_fixture()
    assert payload["event_id"] == "evt_sar_20260918_001"
    obs = candidate_event_to_observation(payload)
    assert obs.modality == SPACE_SAR_MODALITY
    assert obs.observation_id == "evt_sar_20260918_001"
    assert obs.source_id == "SPACE_SAR_SCENE_DIFF"
    assert obs.entity_hint == "UNANNOUNCED_DARK_VESSEL_CLUSTER"
    assert obs.latitude == pytest.approx(1.254)
    assert obs.longitude == pytest.approx(103.812)
    assert obs.confidence == pytest.approx(0.88)
    assert obs.attributes.get("vessel_count_est") == 2
    assert obs.attributes.get("ais_correlation") == "NONE"
    assert "bounding_box" in obs.attributes
    assert len(obs.raw_digest) == 64


def test_observation_from_assumed_fixture_helper() -> None:
    obs = observation_from_assumed_fixture()
    assert obs.modality == SPACE_SAR_MODALITY


def test_invalid_candidate_event_raises() -> None:
    with pytest.raises(ValueError, match="Invalid CandidateEvent"):
        candidate_event_to_observation({"event_id": "x"})


def test_s3_sar_vs_ais_amber() -> None:
    scenario = get_scenario("S3")
    assert "SAR" in scenario.title or "sar" in scenario.title.lower()
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    events = scenario.build_events()
    modalities = {e["modality"] for e in events}
    assert SPACE_SAR_MODALITY in modalities
    assert "ais" in modalities
    assert "radar" in modalities

    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
    assert finding.mismatch_m >= 2_000.0
    assert finding.source_breakdown.get("space_sar", {}).get("vessel_count_est") == 2
    assert "SAR" in finding.picture_summary or "space-based" in finding.picture_summary.lower()
    coa = scenario.build_coa(graph, finding, timeout_seconds=5.0)
    assert coa.intent == "APPROACH_PATROL"
    assert coa.metadata.get("amber_alert") == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"


def test_ingress_candidate_event_fixture(client: TestClient) -> None:
    resp = client.post("/api/ingress/candidate-event", json={"use_fixture": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["observation"]["modality"] == SPACE_SAR_MODALITY
    assert body["track_id"]

    state = client.get("/api/ontology/state")
    assert state.status_code == 200
    modalities = {o["modality"] for o in state.json()["observations"]}
    assert SPACE_SAR_MODALITY in modalities


def test_ingress_candidate_event_payload(client: TestClient) -> None:
    payload = load_assumed_fixture()
    payload = {**payload, "event_id": "evt_sar_live_push_001"}
    resp = client.post("/api/ingress/candidate-event", json={"event": payload})
    assert resp.status_code == 200
    assert resp.json()["observation"]["observation_id"] == "evt_sar_live_push_001"


def test_s3_gate_proposals_queued(client: TestClient) -> None:
    resp = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S3", "unit_id": "USV-02"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "QUEUED"
    assert body["finding"]["amber_alert"] == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
    assert body["coa"]["intent"] == "APPROACH_PATROL"
