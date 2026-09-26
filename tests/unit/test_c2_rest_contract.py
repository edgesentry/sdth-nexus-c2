"""Frozen C2 REST contract: required response keys for Phase 3 clients."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import app
from fastapi.testclient import TestClient

ONTOLOGY_KEYS = {
    "scenario_id",
    "tracks",
    "observations",
    "amber_alert",
    "pending_proposals",
    "inbox_depth",
}
TRACK_KEYS = {
    "track_id",
    "latitude",
    "longitude",
    "speed_mps",
    "confidence",
    "source_ids",
    "modalities",
    "updated_at",
    "attributes",
}
OBSERVATION_KEYS = {
    "observation_id",
    "source_id",
    "entity_hint",
    "latitude",
    "longitude",
    "altitude_m",
    "speed_mps",
    "heading_deg",
    "confidence",
    "observed_at",
    "modality",
    "attributes",
    "raw_digest",
}
AMBER_ALERT_KEYS = {
    "alert",
    "threat_class",
    "mismatch_m",
    "picture_summary",
    "source_breakdown",
    "scenario_id",
}
PROPOSAL_QUEUED_KEYS = {"status", "coa", "finding"}
PROPOSAL_APPROVED_KEYS = {"status", "coa", "token", "finding"}
PROPOSAL_REJECTED_KEYS = {"status", "reason", "coa", "token"}
APPROVE_KEYS = {"status", "coa", "token"}
INBOX_KEYS = {"unit_id", "taskings", "count"}
ACK_KEYS = {"status", "ack", "audit_hash"}
AUDIT_KEYS = {"count", "path", "records"}
AUDIT_HEALTH_KEYS = {"verified", "broken", "count", "label"}
AUDIT_RECORD_KEYS = {
    "class_name",
    "activity_name",
    "severity",
    "time",
    "metadata",
    "prev_hash",
    "hash",
}
TOKEN_KEYS = {"token_id", "coa_id", "verdict", "issued_at", "operator_id", "reason", "digest"}
ACK_RECORD_KEYS = {
    "ack_id",
    "coa_id",
    "unit_id",
    "status",
    "message",
    "telemetry",
    "signature",
    "token_digest",
    "acked_at",
}
COA_KEYS = {
    "coa_id",
    "tier",
    "target_entity_id",
    "target_coordinates",
    "intent",
    "timeout_seconds",
    "pre_conditions",
    "post_conditions",
    "invariants",
    "confidence",
    "corroborating_sources",
    "raw_input_digest",
    "speed_kt",
    "metadata",
}
# Outside demo_no_go; non-null so interlocks pass.
_SAFE_COA = {
    "target_entity_id": "cue-target",
    "target_coordinates": [1.3618, 103.99],
    "intent": "CUE_AND_IDENTIFY",
    "confidence": 0.9,
    "corroborating_sources": ["A", "B"],
    "raw_input_digest": "b" * 64,
    "speed_kt": 5.0,
}


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c
    c2_server._runtime.reset()


def _assert_keys(body: dict, required: set[str], *, label: str) -> None:
    missing = required - set(body)
    assert not missing, f"{label} missing keys: {sorted(missing)}"


def test_frozen_contract_shapes(client: TestClient) -> None:
    empty = client.get("/api/ontology/state")
    assert empty.status_code == 200
    _assert_keys(empty.json(), ONTOLOGY_KEYS, label="ontology/state")

    queued = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2_osint_swarm", "unit_id": "CUE-NODE-01"},
    )
    assert queued.status_code == 200
    q = queued.json()
    assert q["status"] == "QUEUED"
    _assert_keys(q, PROPOSAL_QUEUED_KEYS, label="gate/proposals QUEUED")
    _assert_keys(q["coa"], COA_KEYS, label="coa")
    coa_id = q["coa"]["coa_id"]

    state = client.get("/api/ontology/state").json()
    _assert_keys(state, ONTOLOGY_KEYS, label="ontology/state after propose")
    assert coa_id in state["pending_proposals"]
    assert state["tracks"]
    _assert_keys(state["tracks"][0], TRACK_KEYS, label="track")
    assert state["observations"]
    _assert_keys(state["observations"][0], OBSERVATION_KEYS, label="observation")
    assert state["amber_alert"] is not None
    _assert_keys(state["amber_alert"], AMBER_ALERT_KEYS, label="amber_alert envelope")
    # Naming divergence: ontology uses "alert"; Finding uses "amber_alert".
    assert state["amber_alert"]["alert"] == q["finding"]["amber_alert"]

    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "op-contract"},
    )
    assert approved.status_code == 200
    a = approved.json()
    assert a["status"] == "APPROVED"
    _assert_keys(a, APPROVE_KEYS, label="gate/approve")
    _assert_keys(a["token"], TOKEN_KEYS, label="DecisionToken")
    assert a["token"]["digest"]

    inbox = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"})
    assert inbox.status_code == 200
    ib = inbox.json()
    _assert_keys(ib, INBOX_KEYS, label="recipient/inbox")
    assert ib["count"] == 1
    tasking = ib["taskings"][0]
    assert {"coa", "token", "unit_id", "issued_at", "status"} <= set(tasking)

    ack = client.post(
        "/api/recipient/ack",
        json={
            "coa_id": coa_id,
            "unit_id": "CUE-NODE-01",
            "message": "contract proof",
            "telemetry": {"mode": "cue"},
        },
    )
    assert ack.status_code == 200
    ack_body = ack.json()
    _assert_keys(ack_body, ACK_KEYS, label="recipient/ack")
    _assert_keys(ack_body["ack"], ACK_RECORD_KEYS, label="ack record")

    trail = client.get("/api/audit/trail")
    assert trail.status_code == 200
    tr = trail.json()
    _assert_keys(tr, AUDIT_KEYS, label="audit/trail")
    assert tr["count"] >= 1
    for rec in tr["records"]:
        _assert_keys(rec, AUDIT_RECORD_KEYS, label="audit record")

    health = client.get("/api/audit/health")
    assert health.status_code == 200
    hh = health.json()
    _assert_keys(hh, AUDIT_HEALTH_KEYS, label="audit/health")
    assert hh["verified"] is True
    assert hh["broken"] == 0
    assert hh["count"] == tr["count"]
    assert hh["label"] == f"{hh['broken']} of {hh['count']}"

    reset = client.post("/api/admin/reset")
    assert reset.status_code == 200
    assert reset.json() == {"status": "reset"}


def test_frozen_contract_rejected_operator_shape(client: TestClient) -> None:
    queued = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2_osint_swarm", "unit_id": "CUE-NODE-01"},
    )
    assert queued.status_code == 200
    coa_id = queued.json()["coa"]["coa_id"]

    denied = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "n", "operator_id": "op-contract"},
    )
    assert denied.status_code == 200
    d = denied.json()
    assert d["status"] == "REJECTED_OPERATOR"
    _assert_keys(d, APPROVE_KEYS, label="gate/approve REJECTED_OPERATOR")
    _assert_keys(d["token"], TOKEN_KEYS, label="DecisionToken deny")
    assert d["token"]["verdict"] == "REJECTED_OPERATOR"
    assert d["token"]["digest"]

    inbox = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"})
    assert inbox.json()["count"] == 0


def test_frozen_contract_tier0_auto_approve_shape(client: TestClient) -> None:
    proposed = client.post(
        "/api/gate/proposals",
        json={
            "coa": {**_SAFE_COA, "tier": 0},
            "unit_id": "AUTO-NODE-01",
        },
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "APPROVED"
    _assert_keys(body, PROPOSAL_APPROVED_KEYS, label="gate/proposals Tier-0 APPROVED")
    _assert_keys(body["coa"], COA_KEYS, label="tier0 coa")
    _assert_keys(body["token"], TOKEN_KEYS, label="tier0 token")
    assert body["coa"]["tier"] == 0
    assert body["token"]["digest"]
    assert body["token"]["verdict"] == "APPROVED"

    inbox = client.get("/api/recipient/inbox", params={"unit_id": "AUTO-NODE-01"})
    assert inbox.status_code == 200
    ib = inbox.json()
    _assert_keys(ib, INBOX_KEYS, label="recipient/inbox after tier0")
    assert ib["count"] == 1
    assert ib["taskings"][0]["coa"]["coa_id"] == body["coa"]["coa_id"]


def test_frozen_contract_rejected_fast_shape(client: TestClient) -> None:
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
    body = bad.json()
    assert body["status"] == "REJECTED_FAST"
    _assert_keys(body, PROPOSAL_REJECTED_KEYS, label="gate/proposals REJECTED_FAST")
    _assert_keys(body["token"], TOKEN_KEYS, label="REJECTED_FAST token")
    assert body["token"]["digest"]
