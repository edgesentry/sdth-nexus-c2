"""Integration tests: S2 hero + C2 two-screen + Clearbot effector."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from app import c2_server
from app.c2_server import app as c2_app
from app.main import run_c2_cycle
from core.coa import GateVerdict
from fastapi.testclient import TestClient
from mocks.usv import app as mock_app

pytestmark = pytest.mark.integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def c2_client(tmp_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


@pytest.fixture()
def live_c2(tmp_path: Path) -> Iterator[str]:
    """Process-style C2 server on a free port (uvicorn thread)."""
    port = _free_port()
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "live_gate.jsonl")
    config = uvicorn.Config(c2_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            httpx.get(f"{base}/api/ontology/state", timeout=0.2).raise_for_status()
            break
        except (httpx.HTTPError, OSError):
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("C2 server failed to start")
    try:
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture()
def live_mock() -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            httpx.get(f"{base}/api/v1/telemetry", timeout=0.2).raise_for_status()
            break
        except (httpx.HTTPError, OSError):
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("Mock Clearbot failed to start")
    try:
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_s2_hero_stub_cycle() -> None:
    import asyncio

    verdict = asyncio.run(
        run_c2_cycle(
            scenario_id="S2",
            auto_decision="y",
            use_stub=True,
            gate_timeout_sec=2.0,
        )
    )
    assert verdict == GateVerdict.APPROVED


def test_s2_two_screen_via_testclient(c2_client: TestClient) -> None:
    proposed = c2_client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    assert body["status"] == "QUEUED"
    assert body["finding"]["amber_alert"] == "COUNT_AND_BEARING_MISMATCH"
    assert body["finding"]["source_breakdown"]["social"]["claimed_count"] == 3
    assert body["finding"]["source_breakdown"]["radar"]["contact_count"] == 1
    assert body["coa"]["intent"] == "CUE_AND_IDENTIFY"
    coa_id = body["coa"]["coa_id"]

    state = c2_client.get("/api/ontology/state").json()
    assert state["amber_alert"]["alert"] == "COUNT_AND_BEARING_MISMATCH"
    assert state["amber_alert"]["mismatch_m"] >= 1_000

    approved = c2_client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "ci"},
    )
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["token"]["digest"]

    inbox = c2_client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"}).json()
    assert inbox["count"] == 1

    ack = c2_client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": "CUE-NODE-01", "message": "ci ack"},
    )
    assert ack.json()["status"] == "ACKED"

    trail = c2_client.get("/api/audit/trail").json()
    prev = "0" * 64
    for rec in trail["records"]:
        assert rec["prev_hash"] == prev
        prev = rec["hash"]
    names = [r["activity_name"] for r in trail["records"]]
    assert "recipient_ack" in names


def test_s2_two_screen_live_http(live_c2: str) -> None:
    with httpx.Client(base_url=live_c2, timeout=5.0) as client:
        proposed = client.post(
            "/api/gate/proposals",
            json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
        )
        assert proposed.status_code == 200
        body = proposed.json()
        assert body["finding"]["amber_alert"] == "COUNT_AND_BEARING_MISMATCH"
        coa_id = body["coa"]["coa_id"]

        approved = client.post(
            "/api/gate/approve",
            json={"coa_id": coa_id, "decision": "y"},
        )
        assert approved.json()["status"] == "APPROVED"

        inbox = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"})
        assert inbox.json()["count"] == 1

        ack = client.post(
            "/api/recipient/ack",
            json={"coa_id": coa_id, "unit_id": "CUE-NODE-01"},
        )
        assert ack.json()["status"] == "ACKED"

        trail = client.get("/api/audit/trail").json()
        assert any(r["activity_name"] == "recipient_ack" for r in trail["records"])


@pytest.mark.asyncio
async def test_s2_with_live_clearbot_mock(live_mock: str, tmp_path: Path) -> None:
    verdict = await run_c2_cycle(
        scenario_id="S2",
        auto_decision="y",
        use_stub=False,
        clearbot_base_url=live_mock,
        audit_path=tmp_path / "effector_gate.jsonl",
        gate_timeout_sec=3.0,
    )
    assert verdict == GateVerdict.APPROVED
    tel = httpx.get(f"{live_mock}/api/v1/telemetry", timeout=5.0)
    assert tel.status_code == 200
    assert tel.json()["mode"] == "navigating"
