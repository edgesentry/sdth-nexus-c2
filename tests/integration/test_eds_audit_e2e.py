"""Integration: C2 closed loop dual-writes EDS chain; verify-chain is out-of-process (#83)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import app as c2_app
from core.audit import verify_audit_chain
from core.audit_eds import bridge_available, eds_cli_available, verify_eds_chain
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

requires_bridge = pytest.mark.skipif(
    not bridge_available(),
    reason="libedgesentry_bridge not loadable (run scripts/build_eds_bridge_dylib.sh)",
)
requires_eds_cli = pytest.mark.skipif(
    not eds_cli_available(),
    reason="eds binary not on PATH (brew install edgesentry/tap/eds)",
)


@pytest.fixture()
def c2_audit_path(tmp_path: Path) -> Path:
    return tmp_path / "eds_e2e_gate.jsonl"


@pytest.fixture()
def c2_client(c2_audit_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("C2_EDS", "1")
    c2_server._runtime = c2_server.C2Runtime(audit_path=c2_audit_path)
    with TestClient(c2_app) as client:
        yield client


def _closed_loop(client: TestClient, *, unit_id: str = "EDS-NODE-01") -> str:
    """Propose S2 → Approve → Ack; return coa_id."""
    proposed = client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2", "unit_id": unit_id},
    )
    assert proposed.status_code == 200, proposed.text
    coa_id = proposed.json()["coa"]["coa_id"]

    approved = client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "eds-e2e"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    inbox = client.get("/api/recipient/inbox", params={"unit_id": unit_id})
    assert inbox.status_code == 200
    assert inbox.json()["count"] >= 1

    acked = client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": unit_id, "message": "eds-e2e"},
    )
    assert acked.status_code == 200, acked.text
    assert acked.json()["status"] == "ACKED"
    return coa_id


@requires_bridge
@requires_eds_cli
def test_c2_closed_loop_eds_verify_chain_roundtrip(
    c2_client: TestClient,
    c2_audit_path: Path,
) -> None:
    """REST handshake dual-writes EDS sidecar; separate ``eds`` binary reports 0 of n."""
    _closed_loop(c2_client)

    runtime = c2_server._runtime
    assert runtime is not None
    assert runtime.audit.eds is not None
    assert runtime.audit.eds.available

    ocsf = verify_audit_chain(runtime.audit.records())
    assert ocsf.ok, ocsf.summary()
    assert ocsf.total >= 3
    assert ocsf.summary() == f"broken links: 0 of {ocsf.total}"

    eds_path = runtime.audit.eds.path
    assert eds_path.is_file()
    assert eds_path.name == "eds_chain.json"

    eds = verify_eds_chain(eds_path)
    assert eds.ok, f"{eds.summary()} stdout={eds.stdout!r} stderr={eds.stderr!r}"
    assert eds.total == ocsf.total
    assert eds.broken_links == 0
    assert eds.summary() == f"broken links: 0 of {eds.total}"
    assert "CHAIN_VALID" in eds.stdout
    assert "100%" not in eds.summary()


@requires_bridge
@requires_eds_cli
def test_c2_closed_loop_eds_tamper_fails_verify_chain(
    c2_client: TestClient,
    c2_audit_path: Path,
) -> None:
    """Tampering the EDS sidecar is caught by out-of-process verify-chain."""
    _closed_loop(c2_client)

    runtime = c2_server._runtime
    assert runtime is not None and runtime.audit.eds is not None
    eds_path = runtime.audit.eds.path

    before = verify_eds_chain(eds_path)
    assert before.ok
    assert before.summary() == f"broken links: 0 of {before.total}"

    records = json.loads(eds_path.read_text(encoding="utf-8"))
    assert isinstance(records, list) and len(records) >= 2
    # Corrupt middle record so postcard hash no longer links the chain.
    records[1]["payload_hash"][0] = (int(records[1]["payload_hash"][0]) + 1) % 256
    eds_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    after = verify_eds_chain(eds_path)
    assert not after.ok
    assert after.broken_links == after.total
    assert after.summary() == f"broken links: {after.total} of {after.total}"
    assert "100%" not in after.summary()
