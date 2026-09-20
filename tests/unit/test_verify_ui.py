"""NexusGate Verify UI (Jinja2/HTMX) — Phase 2 #65."""

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


def test_verify_hub_and_screens(client: TestClient) -> None:
    hub = client.get("/verify")
    assert hub.status_code == 200
    assert b"NexusGate Verify" in hub.content
    assert b"FastAPI + Jinja2/HTMX" in hub.content

    cmd = client.get("/verify/command")
    assert cmd.status_code == 200
    assert b"Screen 1" in cmd.content

    recv = client.get("/verify/recipient")
    assert recv.status_code == 200
    assert b"Screen 2" in recv.content


def test_verify_path_f_handshake(client: TestClient) -> None:
    proposed = client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"COUNT_AND_BEARING_MISMATCH" in proposed.content
    assert b"Queued" in proposed.content

    # Extract coa_id from pending form hidden field
    body = proposed.text
    marker = 'name="coa_id" value="'
    assert marker in body
    coa_id = body.split(marker, 1)[1].split('"', 1)[0]
    assert coa_id

    approved = client.post(
        "/verify/command/approve",
        data={
            "coa_id": coa_id,
            "decision": "y",
            "unit_id": "CUE-NODE-01",
            "scenario_id": "S2",
        },
    )
    assert approved.status_code == 200
    assert b"APPROVED" in approved.content

    inbox = client.get("/verify/recipient", params={"unit_id": "CUE-NODE-01"})
    assert inbox.status_code == 200
    assert coa_id.encode() in inbox.content

    acked = client.post(
        "/verify/recipient/ack",
        data={"coa_id": coa_id, "unit_id": "CUE-NODE-01"},
    )
    assert acked.status_code == 200
    assert b"Ack" in acked.content


def test_verify_dual_sar_ingress(client: TestClient) -> None:
    resp = client.post(
        "/verify/command/ingress",
        data={"mode": "dual_sar", "unit_id": "CUE-NODE-01", "scenario_id": "S3"},
    )
    assert resp.status_code == 200
    assert b"Ingested" in resp.content or b"ingested" in resp.content
    assert b"dual_sar" in resp.content.lower() or b"Dual-SAR" in resp.content


def test_verify_glint_and_sia_ingress_modes(client: TestClient) -> None:
    cmd = client.get("/verify/command")
    assert b"Ingress SIA only" in cmd.content
    assert b"Ingress GLINT only" in cmd.content
    assert b"Ingress Dual-SAR" in cmd.content

    sia = client.post(
        "/verify/command/ingress",
        data={"mode": "sentinel", "unit_id": "CUE-NODE-01", "scenario_id": "S3"},
    )
    assert sia.status_code == 200
    assert b"SIA only" in sia.content
    assert b"SENTINEL_IMAGERY_ANALYSIS" in sia.content

    client.post("/verify/command/reset", data={"unit_id": "CUE-NODE-01", "scenario_id": "S3"})
    glint = client.post(
        "/verify/command/ingress",
        data={"mode": "glint", "unit_id": "CUE-NODE-01", "scenario_id": "S3"},
    )
    assert glint.status_code == 200
    assert b"GLINT only" in glint.content
    assert b"glint" in glint.content.lower()


def test_root_redirects_to_verify(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/verify"
