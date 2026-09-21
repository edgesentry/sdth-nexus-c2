"""edgesentry-rs dual-write + out-of-process verify-chain roundtrip (#83)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core.audit import AuditLogger, verify_audit_chain
from core.audit_eds import (
    EdsChainWriter,
    bridge_available,
    eds_cli_available,
    verify_eds_chain,
)

requires_bridge = pytest.mark.skipif(
    not bridge_available(),
    reason="libedgesentry_bridge not loadable (run scripts/build_eds_bridge_dylib.sh)",
)
requires_eds_cli = pytest.mark.skipif(
    not eds_cli_available(),
    reason="eds binary not on PATH (brew install edgesentry/tap/eds)",
)


@requires_bridge
@requires_eds_cli
def test_eds_sign_verify_chain_roundtrip(tmp_path: Path) -> None:
    writer = EdsChainWriter(
        path=tmp_path / "eds_chain.json",
        key_path=tmp_path / "eds_key.json",
    )
    assert writer.available
    assert writer.backend == "ctypes"

    n = 5
    for i in range(n):
        payload = json.dumps({"i": i, "event": "bench"}, sort_keys=True).encode()
        rec = writer.append_payload(payload, object_ref=f"gate/{i + 1}/bench")
        assert rec is not None
        assert rec["sequence"] == i + 1

    result = verify_eds_chain(writer.path)
    assert result.ok
    assert result.total == n
    assert result.broken_links == 0
    assert result.summary() == f"broken links: 0 of {n}"
    assert "CHAIN_VALID" in result.stdout
    assert "100%" not in result.summary()


@requires_bridge
@requires_eds_cli
def test_eds_verify_detects_tamper(tmp_path: Path) -> None:
    writer = EdsChainWriter(
        path=tmp_path / "eds_chain.json",
        key_path=tmp_path / "eds_key.json",
    )
    for i in range(3):
        writer.append_payload(f"row-{i}".encode(), object_ref=f"gate/{i + 1}/t")

    before = verify_eds_chain(writer.path)
    assert before.ok
    assert before.summary() == "broken links: 0 of 3"

    records = writer.records()
    # Flip one byte in the middle record's payload_hash
    records[1]["payload_hash"][0] = (int(records[1]["payload_hash"][0]) + 1) % 256
    writer.replace_records(records)

    after = verify_eds_chain(writer.path)
    assert not after.ok
    assert after.broken_links == after.total == 3
    assert after.summary() == "broken links: 3 of 3"
    assert "100%" not in after.summary()


@requires_bridge
@requires_eds_cli
def test_audit_logger_dual_write_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path, eds_enabled=True)
    assert logger.eds is not None
    assert logger.eds.available

    logger.append("coa_proposed", "Info", {"coa_id": "a"})
    logger.append("gate_decision", "High", {"status": "APPROVED"})
    logger.append("recipient_ack", "High", {"coa_id": "a"})

    ocsf = verify_audit_chain(logger.records())
    assert ocsf.ok
    assert ocsf.summary() == "broken links: 0 of 3"

    eds = verify_eds_chain(logger.eds.path)
    assert eds.ok
    assert eds.total == 3
    assert eds.summary() == "broken links: 0 of 3"


def test_audit_logger_works_without_eds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("C2_EDS", "0")
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path)
    assert logger.eds is None
    logger.append("coa_proposed", "Info", {"coa_id": "x"})
    assert verify_audit_chain(logger.records()).ok


@requires_eds_cli
def test_verify_chain_via_eds_cli_demo(tmp_path: Path) -> None:
    """KPI #5 path: verify-chain in a separate process (no ctypes required)."""
    import subprocess

    from core.audit_eds import resolve_eds_bin

    eds = resolve_eds_bin()
    assert eds is not None
    out = tmp_path / "lift.json"
    proc = subprocess.run(
        [
            str(eds),
            "audit",
            "demo-lift-inspection",
            "--out-file",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    result = verify_eds_chain(out)
    assert result.ok
    assert result.total >= 1
    assert result.summary() == f"broken links: 0 of {result.total}"
