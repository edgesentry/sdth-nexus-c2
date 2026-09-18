"""Unit tests for Sentinel-Imagery-Analysis → CandidateEvent bridge (#47)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app import c2_server
from app.adapters.sar_candidate_event import SPACE_SAR_MODALITY, candidate_event_to_observation
from app.adapters.sentinel_imagery import (
    DARK_VESSEL_EVENT_TYPE,
    load_sentinel_run_cv_fixture,
    resolve_sentinel_events,
    sentinel_detection_to_candidate_event,
    sentinel_run_cv_to_candidate_events,
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


def test_fixture_maps_uncorrelated_only() -> None:
    payload = load_sentinel_run_cv_fixture()
    events = sentinel_run_cv_to_candidate_events(payload)
    assert len(events) == 2
    assert all(e.event_type == DARK_VESSEL_EVENT_TYPE for e in events)
    assert all(e.attributes.get("ais_absent") is True for e in events)
    assert events[0].location.latitude == pytest.approx(1.2542)
    assert events[0].attributes.get("vessel_length_m") == pytest.approx(78.2)
    assert events[0].attributes.get("vessel_count_est") == 2
    assert events[0].attributes.get("evidence_image_uri") == "tests/fixtures/sentinel_chip.jpg"
    assert events[0].bounding_box is not None


def test_correlated_detection_raises() -> None:
    payload = load_sentinel_run_cv_fixture()
    correlated = next(d for d in payload["detections"] if d["correlation_status"] == "inside_box")
    with pytest.raises(ValueError, match="not uncorrelated"):
        sentinel_detection_to_candidate_event(correlated, scan_id="x")


def test_candidate_event_to_observation_ais_absent() -> None:
    events = sentinel_run_cv_to_candidate_events(load_sentinel_run_cv_fixture())
    obs = candidate_event_to_observation(events[0])
    assert obs.modality == SPACE_SAR_MODALITY
    assert obs.attributes.get("ais_absent") is True
    assert obs.entity_hint == DARK_VESSEL_EVENT_TYPE


def test_resolve_fixture_source() -> None:
    events, source = resolve_sentinel_events(use_fixture=True)
    assert source == "fixture"
    assert len(events) == 2


def test_resolve_pull_falls_back_to_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.adapters.sentinel_imagery.fetch_run_cv",
        lambda **_kwargs: None,
    )
    events, source = resolve_sentinel_events(pull_upstream=True)
    assert source == "fixture"
    assert len(events) == 2


def test_resolve_pull_uses_upstream_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    remote = {**load_sentinel_run_cv_fixture(), "scan_id": "live_scan"}

    def _fake_fetch(**_kwargs: Any) -> dict[str, Any]:
        return remote

    monkeypatch.setattr("app.adapters.sentinel_imagery.fetch_run_cv", _fake_fetch)
    events, source = resolve_sentinel_events(pull_upstream=True)
    assert source == "upstream"
    assert events[0].event_id.startswith("EVT-SAR-SG-live_scan-")


def test_ingress_sentinel_fixture(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"use_sentinel_fixture": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["source"] == "fixture"
    assert body["count"] == 2
    assert body["observation"]["modality"] == SPACE_SAR_MODALITY
    assert body["observation"]["attributes"]["ais_absent"] is True
    assert len(body["observations"]) == 2
    assert len(body["track_ids"]) == 2


def test_ingress_pull_upstream_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.adapters.sentinel_imagery.fetch_run_cv",
        lambda **_kwargs: None,
    )
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"pull_upstream": True},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "fixture"
    assert resp.json()["count"] == 2


def test_ingress_run_cv_push(client: TestClient) -> None:
    payload = load_sentinel_run_cv_fixture()
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"run_cv": payload},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "run_cv"
    assert resp.json()["count"] == 2


def test_sentinel_events_drive_s3_amber() -> None:
    """Sentinel dark vessels near fixture coords still contradict thin AIS in S3."""
    scenario = get_scenario("S3")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    events = scenario.build_events()
    sentinel_obs = candidate_event_to_observation(
        sentinel_run_cv_to_candidate_events(load_sentinel_run_cv_fixture())[0]
    )
    rebuilt: list[dict[str, Any]] = []
    for e in events:
        if e.get("modality") == SPACE_SAR_MODALITY:
            rebuilt.append(
                {
                    "source_id": sentinel_obs.source_id,
                    "entity_id": sentinel_obs.entity_hint,
                    "observation_id": sentinel_obs.observation_id,
                    "latitude": sentinel_obs.latitude,
                    "longitude": sentinel_obs.longitude,
                    "speed_kt": 0.0,
                    "confidence": sentinel_obs.confidence,
                    "observed_at": sentinel_obs.observed_at.isoformat(),
                    "modality": SPACE_SAR_MODALITY,
                    **sentinel_obs.attributes,
                }
            )
        else:
            rebuilt.append(e)
    graph.ingest_many([normalize_sensor_event(e) for e in rebuilt])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
