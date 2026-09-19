"""Unit tests for GLINT Assumed-mock client + ingress (issue #55)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app import c2_server
from app.adapters.glint_client import (
    SOURCE_FIXTURE,
    SOURCE_UPSTREAM,
    annotate_glint_event,
    fetch_glint_event,
    load_glint_fixture,
    resolve_glint_events,
)
from app.adapters.sar_candidate_event import (
    SPACE_SAR_MODALITY,
    candidate_event_to_observation,
    load_assumed_fixture,
    parse_candidate_event,
)
from app.c2_server import app
from app.mock_glint_server import app as glint_mock_app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def glint_client() -> TestClient:
    with TestClient(glint_mock_app) as c:
        yield c


def test_mock_health_and_event(glint_client: TestClient) -> None:
    health = glint_client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "glint-mock"

    event = glint_client.get("/api/candidate-event")
    assert event.status_code == 200
    body = event.json()
    assert body["event_id"] == load_assumed_fixture()["event_id"]
    assert body["event_type"] == "UNANNOUNCED_DARK_VESSEL_CLUSTER"
    parse_candidate_event(body)  # validates v1.3.0


def test_load_glint_fixture_annotates_provenance() -> None:
    event = load_glint_fixture()
    assert event.attributes.get("ingress") == "glint"
    assert event.attributes.get("provenance") == "assumed-mock"
    obs = candidate_event_to_observation(event)
    assert obs.modality == SPACE_SAR_MODALITY
    assert obs.confidence == pytest.approx(0.88)


def test_annotate_preserves_macro_fields() -> None:
    raw = parse_candidate_event(load_assumed_fixture())
    tagged = annotate_glint_event(raw)
    assert tagged.event_id == raw.event_id
    assert tagged.location.latitude == pytest.approx(1.254)
    assert tagged.attributes.get("vessel_count_est") == 2


def test_resolve_fixture_only() -> None:
    events, source = resolve_glint_events(use_fixture=True)
    assert source == SOURCE_FIXTURE
    assert len(events) == 1
    assert events[0].event_type == "UNANNOUNCED_DARK_VESSEL_CLUSTER"


def test_resolve_pull_falls_back_to_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.adapters.glint_client.fetch_glint_event",
        lambda **_kwargs: None,
    )
    events, source = resolve_glint_events(pull_upstream=True)
    assert source == SOURCE_FIXTURE
    assert len(events) == 1


def test_resolve_pull_uses_upstream_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    remote = annotate_glint_event(parse_candidate_event(load_assumed_fixture()))
    remote = remote.model_copy(update={"event_id": "evt_glint_live_001"})

    def _fake_fetch(**_kwargs: Any):
        return remote

    monkeypatch.setattr("app.adapters.glint_client.fetch_glint_event", _fake_fetch)
    events, source = resolve_glint_events(pull_upstream=True)
    assert source == SOURCE_UPSTREAM
    assert events[0].event_id == "evt_glint_live_001"


def test_fetch_returns_none_on_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLINT_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("GLINT_TIMEOUT_S", "0.05")
    assert fetch_glint_event() is None


def test_ingress_glint_fixture(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"use_glint_fixture": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["source"] == SOURCE_FIXTURE
    assert body["count"] == 1
    assert body["observation"]["modality"] == SPACE_SAR_MODALITY
    assert body["observation"]["attributes"]["ingress"] == "glint"
    assert body["observation"]["attributes"]["provenance"] == "assumed-mock"
    assert body["observation"]["entity_hint"] == "UNANNOUNCED_DARK_VESSEL_CLUSTER"


def test_ingress_pull_glint_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.adapters.glint_client.fetch_glint_event",
        lambda **_kwargs: None,
    )
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"pull_glint": True},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == SOURCE_FIXTURE
    assert resp.json()["count"] == 1


def test_ingress_pull_glint_upstream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = annotate_glint_event(parse_candidate_event(load_assumed_fixture()))
    remote = remote.model_copy(update={"event_id": "evt_glint_http_001"})
    monkeypatch.setattr(
        "app.adapters.glint_client.fetch_glint_event",
        lambda **_kwargs: remote,
    )
    resp = client.post(
        "/api/ingress/candidate-event",
        json={"pull_glint": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == SOURCE_UPSTREAM
    assert body["observation"]["observation_id"] == "evt_glint_http_001"
