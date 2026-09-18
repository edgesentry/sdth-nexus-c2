"""OCSF hash-chain logger, including container hydrate replace_records."""

from __future__ import annotations

from pathlib import Path

from core.audit import AuditLogger


def test_replace_records_restores_chain(tmp_path: Path) -> None:
    first = AuditLogger(tmp_path / "gate.jsonl")
    first.append("coa_proposed", "Medium", {"coa_id": "a"})
    first.append("gate_decision", "High", {"verdict": "APPROVED"})
    snapshot = first.records()
    assert len(snapshot) == 2

    empty = tmp_path / "restored.jsonl"
    second = AuditLogger(empty)
    second.replace_records(snapshot)
    assert second.records() == snapshot

    extra = second.append("recipient_ack", "High", {"coa_id": "a"})
    assert extra["prev_hash"] == snapshot[-1]["hash"]
