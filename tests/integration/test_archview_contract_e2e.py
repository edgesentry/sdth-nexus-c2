"""Integration: ARCHVIEW Core contract — audit health + CORS (#93).

CI-safe (TestClient / live uvicorn). ARCHVIEW browser UI E2E is local-only (#99).
"""

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
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

AUDIT_HEALTH_KEYS = {"verified", "broken", "count", "label"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def c2_client(tmp_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "archview93_gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


@pytest.fixture()
def live_c2(tmp_path: Path) -> Iterator[str]:
    """Process-style C2 server on a free port (uvicorn thread)."""
    port = _free_port()
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "archview93_live.jsonl")
    config = uvicorn.Config(c2_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            httpx.get(f"{base}/health", timeout=0.2).raise_for_status()
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


def _handshake(client: TestClient | httpx.Client) -> str:
    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    coa_id = proposed.json()["coa"]["coa_id"]

    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "ci-archview"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    ack = client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": "CUE-NODE-01", "message": "ci health"},
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKED"
    return coa_id


def test_audit_health_empty_chain(c2_client: TestClient) -> None:
    c2_client.post("/api/admin/reset")
    res = c2_client.get("/api/audit/health")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == AUDIT_HEALTH_KEYS
    assert body["verified"] is True
    assert body["broken"] == 0
    assert body["count"] == 0
    assert body["label"] == "0 of 0"


def test_audit_health_after_two_screen_handshake(c2_client: TestClient) -> None:
    c2_client.post("/api/admin/reset")
    _handshake(c2_client)

    trail = c2_client.get("/api/audit/trail").json()
    health = c2_client.get("/api/audit/health").json()

    assert set(health) == AUDIT_HEALTH_KEYS
    assert health["verified"] is True
    assert health["broken"] == 0
    assert health["count"] == trail["count"]
    assert health["count"] >= 1
    assert health["label"] == f"0 of {health['count']}"


def test_audit_health_live_http(live_c2: str) -> None:
    with httpx.Client(base_url=live_c2, timeout=5.0) as client:
        _handshake(client)
        trail = client.get("/api/audit/trail").json()
        health = client.get("/api/audit/health").json()
        assert set(health) == AUDIT_HEALTH_KEYS
        assert health["verified"] is True
        assert health["count"] == trail["count"]
        assert health["label"] == f"{health['broken']} of {health['count']}"


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
)
def test_cors_archview_origins_live_http(live_c2: str, origin: str) -> None:
    """Direct-origin demos from ARCHVIEW Vite (:3001) / generic Vite (:5173)."""
    with httpx.Client(base_url=live_c2, timeout=5.0) as client:
        preflight = client.options(
            "/api/audit/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code in (200, 204)
        assert preflight.headers.get("access-control-allow-origin") == origin

        health = client.get("/api/audit/health", headers={"Origin": origin})
        assert health.status_code == 200
        assert health.headers.get("access-control-allow-origin") == origin
        assert set(health.json()) == AUDIT_HEALTH_KEYS
