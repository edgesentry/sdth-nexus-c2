"""OCSF hash-chain logger, including container hydrate replace_records."""

from __future__ import annotations

import json
from pathlib import Path

from core.audit import GENESIS_PREV, AuditLogger, chain_break_index


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


def test_orphan_head_is_quarantined_on_init(tmp_path: Path) -> None:
    """Truncated jsonl (non-genesis prev on record[0]) must not poison demos."""
    path = tmp_path / "gate.jsonl"
    orphan = {
        "class_name": "Security Finding",
        "activity_name": "coa_rejected_fast",
        "severity": "High",
        "time": "2026-09-20T00:00:00+00:00",
        "metadata": {"reason": "stale"},
        "prev_hash": "a" * 64,  # not genesis — head was truncated
        "hash": "b" * 64,
    }
    path.write_text(json.dumps(orphan) + "\n", encoding="utf-8")

    logger = AuditLogger(path)
    assert logger.records() == []
    archived = list(tmp_path.glob("gate.jsonl.broken-*"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text(encoding="utf-8").strip())["prev_hash"] == "a" * 64

    fresh = logger.append("coa_proposed", "Medium", {"coa_id": "new"})
    assert fresh["prev_hash"] == GENESIS_PREV
    assert chain_break_index(logger.records()) is None


def test_intact_chain_is_not_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path)
    logger.append("coa_proposed", "Medium", {"coa_id": "a"})
    logger.append("recipient_ack", "High", {"coa_id": "a"})
    n = len(logger.records())

    again = AuditLogger(path)
    assert len(again.records()) == n
    assert list(tmp_path.glob("gate.jsonl.broken-*")) == []
