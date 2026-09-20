"""C2 REST server: propose → approve → inbox → ack → audit."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def test_c2_two_screen_handshake(client: TestClient) -> None:
    empty = client.get("/api/ontology/state")
    assert empty.status_code == 200
    assert empty.json()["tracks"] == []

    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "QUEUED"
    coa_id = body["coa"]["coa_id"]
    assert body["finding"]["amber_alert"] == "COUNT_AND_BEARING_MISMATCH"

    state = client.get("/api/ontology/state")
    assert state.status_code == 200
    st = state.json()
    assert st["scenario_id"] == "S2"
    assert len(st["tracks"]) >= 1
    assert st["amber_alert"]["alert"] == "COUNT_AND_BEARING_MISMATCH"
    assert coa_id in st["pending_proposals"]

    denied = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "n", "operator_id": "op-1"},
    )
    assert denied.status_code == 200
    assert denied.json()["status"] == "REJECTED_OPERATOR"

    # Re-propose after deny
    proposed2 = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    coa_id2 = proposed2.json()["coa"]["coa_id"]

    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id2, "decision": "y", "operator_id": "op-1"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    token = approved.json()["token"]
    assert token["digest"]
    assert token["verdict"] == "APPROVED"

    inbox = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"})
    assert inbox.status_code == 200
    assert inbox.json()["count"] == 1
    assert inbox.json()["taskings"][0]["coa"]["coa_id"] == coa_id2

    other = client.get("/api/recipient/inbox", params={"unit_id": "OTHER"})
    assert other.json()["count"] == 0

    ack = client.post(
        "/api/recipient/ack",
        json={
            "coa_id": coa_id2,
            "unit_id": "CUE-NODE-01",
            "message": "on station",
            "telemetry": {"mode": "cue"},
        },
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKED"
    assert ack.json()["ack"]["signature"]
    assert ack.json()["audit_hash"]

    inbox_after = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"})
    assert inbox_after.json()["count"] == 0

    trail = client.get("/api/audit/trail")
    assert trail.status_code == 200
    records = trail.json()["records"]
    assert len(records) >= 4
    names = [r["activity_name"] for r in records]
    assert "coa_proposed" in names
    assert "gate_decision" in names
    assert "recipient_ack" in names
    # Hash chain integrity
    prev = "0" * 64
    for rec in records:
        assert rec["prev_hash"] == prev
        prev = rec["hash"]


def test_c2_geofence_rejects_proposal(client: TestClient) -> None:
    bad = client.post(
        "/api/gate/proposals",
        json={
            "coa": {
                "target_entity_id": "x",
                "target_coordinates": [1.2310, 103.8510],
                "intent": "ISR_IDENTIFY_CONTACT",
                "confidence": 0.9,
                "corroborating_sources": ["A", "B"],
                "raw_input_digest": "a" * 64,
                "speed_kt": 5.0,
            },
            "unit_id": "USV-01",
        },
    )
    assert bad.status_code == 200
    assert bad.json()["status"] == "REJECTED_FAST"
    assert "Geofence" in (bad.json().get("reason") or "")


def test_health_ok(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_cors_allows_nexusgate_verify_origin(client: TestClient) -> None:
    origin = "http://localhost:3000"
    preflight = client.options(
        "/api/ontology/state",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code in (200, 204)
    assert preflight.headers.get("access-control-allow-origin") == origin

    state = client.get("/api/ontology/state", headers={"Origin": origin})
    assert state.status_code == 200
    assert state.headers.get("access-control-allow-origin") == origin


def test_static_fixture_sentinel_chip(client: TestClient) -> None:
    res = client.get("/static/fixtures/sentinel_chip.jpg")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("image/")
    assert len(res.content) > 100


def test_admin_audit_snapshot_hydrates_chain(client: TestClient) -> None:
    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    snapshot = client.get("/api/audit/trail").json()["records"]
    assert snapshot

    wiped = client.put("/api/admin/audit/snapshot", json={"records": []})
    assert wiped.status_code == 200
    assert wiped.json() == {"status": "restored", "count": 0}
    assert client.get("/api/audit/trail").json()["count"] == 0

    restored = client.put("/api/admin/audit/snapshot", json={"records": snapshot})
    assert restored.status_code == 200
    assert restored.json()["count"] == len(snapshot)
    assert client.get("/api/audit/trail").json()["records"] == snapshot
