"""Integration: OCSF tamper detection against a live C2 closed loop (#74)."""

from __future__ import annotations

import copy
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app import c2_server
from app.c2_server import app as c2_app
from core.audit import load_audit_records, verify_audit_chain, write_audit_records
from fastapi.testclient import TestClient
from scripts.demo_tamper_detection import _inject_one_char_tamper, run_demo

pytestmark = pytest.mark.integration


@pytest.fixture()
def c2_audit_path(tmp_path: Path) -> Path:
    return tmp_path / "tamper_e2e_gate.jsonl"


@pytest.fixture()
def c2_client(c2_audit_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=c2_audit_path)
    with TestClient(c2_app) as client:
        yield client


def _closed_loop(client: TestClient, *, unit_id: str = "CUE-NODE-01") -> str:
    """Propose S2 → Approve → Ack; return coa_id."""
    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": unit_id},
    )
    assert proposed.status_code == 200, proposed.text
    coa_id = proposed.json()["coa"]["coa_id"]

    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "tamper-e2e"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    inbox = client.get("/api/recipient/inbox", params={"unit_id": unit_id})
    assert inbox.status_code == 200
    assert inbox.json()["count"] >= 1

    acked = client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": unit_id, "message": "tamper-e2e"},
    )
    assert acked.status_code == 200, acked.text
    assert acked.json()["status"] == "ACKED"
    return coa_id


def _gate_decision_index(records: list[dict[str, Any]]) -> int:
    for i, rec in enumerate(records):
        if rec.get("activity_name") != "gate_decision":
            continue
        meta = rec.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("verdict") == "APPROVED":
            return i
    raise AssertionError("no APPROVED gate_decision record in audit trail")


def test_c2_closed_loop_audit_tamper_detect_and_restore(
    c2_client: TestClient,
    c2_audit_path: Path,
) -> None:
    """Live REST handshake seals OCSF chain; 1-char edit is detected; restore recovers."""
    coa_id = _closed_loop(c2_client)
    original = load_audit_records(c2_audit_path)
    assert len(original) >= 3

    before = verify_audit_chain(original)
    assert before.ok, before.summary()
    assert before.total == len(original)

    idx = _gate_decision_index(original)
    assert original[idx]["metadata"]["verdict"] == "APPROVED"

    tampered = _inject_one_char_tamper(copy.deepcopy(original), index=idx)
    assert tampered[idx]["metadata"]["verdict"] == "XPPROVED"
    write_audit_records(c2_audit_path, tampered)

    after = verify_audit_chain(load_audit_records(c2_audit_path))
    assert not after.ok
    assert after.break_index == idx
    assert after.reason == "hash mismatch"
    assert after.summary() == f"broken links: 1 of {after.total}"

    # Trail API still serves records, but integrity check fails → tasking must halt.
    trail = c2_client.get("/api/audit/trail")
    assert trail.status_code == 200
    body = trail.json()
    assert body["count"] == len(tampered)
    assert not verify_audit_chain(body["records"]).ok

    write_audit_records(c2_audit_path, original)
    restored = verify_audit_chain(load_audit_records(c2_audit_path))
    assert restored.ok, restored.summary()
    restored_records = load_audit_records(c2_audit_path)
    assert any(
        (r.get("metadata") or {}).get("coa_id") == coa_id
        or ((r.get("metadata") or {}).get("token") or {}).get("coa_id") == coa_id
        for r in restored_records
    )


def test_demo_script_against_isolated_path_is_fast(tmp_path: Path) -> None:
    """Pitch CLI roundtrip stays under 3s on an isolated path."""
    path = tmp_path / "pitch_tamper.jsonl"
    t0 = time.perf_counter()
    assert run_demo(path=path, quiet=True) == 0
    assert time.perf_counter() - t0 < 3.0
    assert verify_audit_chain(load_audit_records(path)).ok
