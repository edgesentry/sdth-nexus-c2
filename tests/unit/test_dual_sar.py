"""Unit tests for Dual-SAR corroborator (issue #56)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app import c2_server
from app.adapters.dual_sar import (
    COMPOSITE_SOURCE_ID,
    SOURCE_DUAL_SAR,
    SOURCE_SIA_ONLY,
    STATUS_CORROBORATED,
    STATUS_SIA_ONLY,
    corroborate,
    fuse_pair,
    point_in_bbox,
    resolve_dual_sar_events,
    sector_aligns,
)
from app.adapters.glint_client import load_glint_fixture
from app.adapters.sar_candidate_event import (
    SPACE_SAR_MODALITY,
    CandidateEventBoundingBox,
    CandidateEventLocation,
    candidate_event_to_observation,
)
from app.adapters.sentinel_imagery import resolve_sentinel_events
from app.c2_server import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def test_sector_aligns_fixture_pair() -> None:
    macro = load_glint_fixture()
    micros, _ = resolve_sentinel_events(use_fixture=True)
    assert sector_aligns(macro, micros[0])
    assert sector_aligns(macro, micros[1])


def test_sector_rejects_far_micro() -> None:
    macro = load_glint_fixture()
    micros, _ = resolve_sentinel_events(use_fixture=True)
    far = micros[0].model_copy(
        update={"location": CandidateEventLocation(latitude=1.40, longitude=104.10)}
    )
    assert not sector_aligns(macro, far)


def test_fuse_pair_boosts_confidence_and_keeps_obb() -> None:
    macro = load_glint_fixture()
    micros, _ = resolve_sentinel_events(use_fixture=True)
    fused = fuse_pair(macro, micros[0])
    assert fused.source_id == COMPOSITE_SOURCE_ID
    assert fused.confidence == pytest.approx(min(0.98, max(0.88, 0.91) + 0.1))
    assert fused.attributes["dual_sar_status"] == STATUS_CORROBORATED
    assert fused.attributes["ingress"] == "dual_sar"
    assert fused.attributes["vessel_length_m"] == pytest.approx(78.2)
    assert fused.attributes["evidence_image_uri"]
    assert fused.attributes["macro_event_type"] == "UNANNOUNCED_DARK_VESSEL_CLUSTER"
    obs = candidate_event_to_observation(fused)
    assert obs.modality == SPACE_SAR_MODALITY
    assert obs.confidence == pytest.approx(fused.confidence)


def test_corroborate_marks_out_of_sector_sia_only() -> None:
    macro = load_glint_fixture()
    micros, _ = resolve_sentinel_events(use_fixture=True)
    far = micros[0].model_copy(
        update={
            "event_id": "FAR-1",
            "location": CandidateEventLocation(latitude=1.40, longitude=104.10),
        }
    )
    out = corroborate([macro], [far])
    assert len(out) == 1
    assert out[0].attributes["dual_sar_status"] == STATUS_SIA_ONLY
    assert out[0].confidence == pytest.approx(far.confidence)


def test_resolve_fixtures_corroborates() -> None:
    events, source = resolve_dual_sar_events(use_fixture=True)
    assert source == SOURCE_DUAL_SAR
    assert len(events) == 2
    assert all(e.attributes["dual_sar_status"] == STATUS_CORROBORATED for e in events)
    assert all(e.source_id == COMPOSITE_SOURCE_ID for e in events)


def test_resolve_glint_unreachable_fails_safe_to_sia(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**_kwargs: Any) -> tuple[list[Any], str]:
        raise ValueError("glint down")

    monkeypatch.setattr("app.adapters.dual_sar.resolve_glint_events", _boom)
    events, source = resolve_dual_sar_events(use_fixture=True)
    assert source == SOURCE_SIA_ONLY
    assert len(events) == 2
    assert all(e.attributes["dual_sar_status"] == STATUS_SIA_ONLY for e in events)
    assert all(e.source_id != COMPOSITE_SOURCE_ID for e in events)


def test_resolve_glint_oserror_fails_safe_to_sia(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**_kwargs: Any) -> tuple[list[Any], str]:
        raise FileNotFoundError("missing glint fixture")

    monkeypatch.setattr("app.adapters.dual_sar.resolve_glint_events", _boom)
    events, source = resolve_dual_sar_events(use_fixture=True)
    assert source == SOURCE_SIA_ONLY
    assert len(events) == 2
    assert all(e.attributes["dual_sar_status"] == STATUS_SIA_ONLY for e in events)


def test_point_in_bbox_tolerates_inverted_bounds() -> None:
    inverted = CandidateEventBoundingBox(
        min_lat=1.258,
        max_lat=1.25,
        min_lon=103.816,
        max_lon=103.808,
    )
    assert point_in_bbox(1.254, 103.812, inverted)
    assert not point_in_bbox(1.40, 104.10, inverted)


def test_ingress_dual_sar_fixture(client: TestClient) -> None:
    resp = client.post("/api/ingress/candidate-event", json={"dual_sar": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["source"] == SOURCE_DUAL_SAR
    assert body["count"] == 2
    first = body["observation"]
    assert first["source_id"] == COMPOSITE_SOURCE_ID
    assert first["attributes"]["dual_sar_status"] == STATUS_CORROBORATED
    assert first["attributes"]["vessel_length_m"] == pytest.approx(78.2)
    assert first["confidence"] >= 0.91


def test_ingress_pull_dual_sar_falls_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.adapters.sentinel_imagery.fetch_run_cv", lambda **_k: None)
    monkeypatch.setattr("app.adapters.glint_client.fetch_glint_event", lambda **_k: None)
    resp = client.post("/api/ingress/candidate-event", json={"pull_dual_sar": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == SOURCE_DUAL_SAR
    assert body["count"] == 2
