"""Zero-internet offline resilience suite (issue #76).

Blocks non-loopback outbound sockets and verifies S1–S3, /verify WebUI,
Indago DuckDB, SIA Sentinel fixture, GLINT mock, and pull→fixture fail-safes
run without external network access.
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from app import c2_server
from app.adapters.glint_client import SOURCE_FIXTURE, SOURCE_UPSTREAM, resolve_glint_events
from app.adapters.open_feed import resolve_open_ais_payload
from app.adapters.sentinel_imagery import resolve_sentinel_events
from app.c2_server import app as c2_app
from app.main import run_c2_cycle
from core.coa import GateVerdict
from fastapi.testclient import TestClient
from mocks.glint import app as glint_mock_app

pytestmark = pytest.mark.integration

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_loopback_host(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode()
    if not isinstance(host, str):
        return False
    return host in _LOOPBACK_HOSTS or host.startswith("127.")


@pytest.fixture(autouse=True)
def block_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject non-loopback TCP connects (venue / air-gap rehearsal)."""
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def guarded_connect(self: socket.socket, address: object) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
            host = address[0]
            if not _is_loopback_host(host):
                raise OSError(f"outbound blocked (zero-internet): {host!r}")
        return real_connect(self, address)

    def guarded_create(address: object, *args: object, **kwargs: object) -> socket.socket:
        host = address[0] if isinstance(address, tuple) and address else None
        if not _is_loopback_host(host):
            raise OSError(f"outbound blocked (zero-internet): {host!r}")
        return real_create(address, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create)


@pytest.fixture()
def c2_client(tmp_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "zero_net_gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


def _write_mini_indago_db(path: Path) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE ais_positions (
            mmsi VARCHAR, timestamp TIMESTAMPTZ, lat DOUBLE, lon DOUBLE,
            sog FLOAT, cog FLOAT, nav_status TINYINT, ship_type TINYINT
        );
        CREATE TABLE vessel_meta (
            mmsi VARCHAR PRIMARY KEY, imo VARCHAR, name VARCHAR,
            flag VARCHAR, ship_type TINYINT, gross_tonnage FLOAT
        );
        """
    )
    con.execute(
        """
        INSERT INTO ais_positions VALUES
          ('563000001', CURRENT_TIMESTAMP, 1.26, 103.82, 8.5, 210, 0, 70),
          ('563000001', CURRENT_TIMESTAMP - INTERVAL '10 minutes', 1.25, 103.81, 7.0, 200, 0, 70),
          ('563000002', CURRENT_TIMESTAMP, 1.27, 103.83, 4.2, 95, 0, 52);
        INSERT INTO vessel_meta VALUES
          ('563000001', NULL, 'TEST CARGO', 'SG', 70, 1000),
          ('563000002', NULL, 'TEST TUG', 'SG', 52, 200);
        """
    )
    con.close()


def test_s1_s2_s3_stub_cycles_offline() -> None:
    for scenario_id in ("S1", "S2", "S3"):
        verdict = asyncio.run(
            run_c2_cycle(
                scenario_id=scenario_id,
                auto_decision="y",
                use_stub=True,
                gate_timeout_sec=2.0,
            )
        )
        assert verdict == GateVerdict.APPROVED, scenario_id


def test_verify_ui_hub_and_propose_offline(c2_client: TestClient) -> None:
    hub = c2_client.get("/verify")
    assert hub.status_code == 200
    assert b"NexusGate" in hub.content or b"verify" in hub.content.lower()

    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"COUNT_AND_BEARING_MISMATCH" in proposed.content or b"coa" in proposed.content.lower()


def test_indago_duckdb_reader_offline(
    c2_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "singapore.duckdb"
    _write_mini_indago_db(db)
    monkeypatch.setenv("INDAGO_DUCKDB_PATH", str(db))

    resp = c2_client.post(
        "/api/ingress/open-feed",
        json={"feed": "ais", "source": "indago", "limit": 10},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["resolved_sources"]["ais"] == "indago"
    assert body["count"] == 2


def test_sia_sentinel_fixture_offline(c2_client: TestClient) -> None:
    resp = c2_client.post(
        "/api/ingress/candidate-event",
        json={"use_sentinel_fixture": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "INGESTED"
    assert body["source"] == "fixture"
    assert body["count"] >= 1


def test_glint_mock_client_on_loopback() -> None:
    port = _free_port()
    config = uvicorn.Config(glint_mock_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5.0
    try:
        while time.time() < deadline:
            try:
                httpx.get(f"{base}/health", timeout=0.2).raise_for_status()
                break
            except (httpx.HTTPError, OSError):
                time.sleep(0.05)
        else:
            raise RuntimeError("GLINT mock failed to start on loopback")

        events, source = resolve_glint_events(pull_upstream=True, base_url=base, timeout_s=1.0)
        assert source == SOURCE_UPSTREAM
        assert len(events) == 1
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_pull_fail_safes_activate_when_live_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live endpoints absent → clean fixture fail-safe under outbound block."""
    unreachable = "http://203.0.113.1:1"

    sia_events, sia_source = resolve_sentinel_events(
        pull_upstream=True,
        base_url=unreachable,
        timeout_s=0.1,
    )
    assert sia_source == "fixture"
    assert len(sia_events) >= 1

    glint_events, glint_source = resolve_glint_events(
        pull_upstream=True,
        base_url=unreachable,
        timeout_s=0.1,
    )
    assert glint_source == SOURCE_FIXTURE
    assert len(glint_events) == 1

    # Force Indago miss so auto ladder reaches live → fixture.
    monkeypatch.setattr(
        "app.adapters.open_feed.resolve_indago_duckdb_path",
        lambda *args, **kwargs: None,
    )
    monkeypatch.delenv("INDAGO_DUCKDB_PATH", raising=False)
    _payload, ais_source = resolve_open_ais_payload(source="auto")
    assert ais_source == "fixture"
    assert isinstance(_payload.get("vessels"), list)
    assert len(_payload["vessels"]) >= 1
