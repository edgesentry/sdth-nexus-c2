"""OCSF hash-chain logger, including container hydrate replace_records."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest
from core.audit import (
    GENESIS_PREV,
    AuditLogger,
    chain_break_index,
    inject_one_char_tamper,
    load_audit_records,
    verify_audit_chain,
    write_audit_records,
)
from scripts.demo_tamper_detection import run_demo


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


def test_verify_audit_chain_intact(tmp_path: Path) -> None:
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path)
    logger.append("coa_proposed", "Info", {"coa_id": "a"})
    logger.append("gate_decision", "High", {"status": "APPROVED"})
    logger.append("recipient_ack", "High", {"coa_id": "a"})
    result = verify_audit_chain(logger.records())
    assert result.ok
    assert result.total == 3
    assert result.break_index is None
    assert "broken links: 0 of 3" in result.summary()


def test_verify_detects_content_tamper_hash_mismatch(tmp_path: Path) -> None:
    """Insider flips APPROVED→XPPROVED without updating hash (#74)."""
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path)
    logger.append("coa_proposed", "Info", {"coa_id": "a"})
    logger.append("gate_decision", "High", {"status": "APPROVED", "coa_id": "a"})
    logger.append("recipient_ack", "High", {"coa_id": "a"})
    original = logger.records()
    assert verify_audit_chain(original).ok

    tampered = inject_one_char_tamper(original, index=1)
    assert tampered[1]["metadata"]["status"] == "XPPROVED"
    # prev_hash links still look contiguous — only content digest fails
    assert chain_break_index(tampered) is None
    result = verify_audit_chain(tampered)
    assert not result.ok
    assert result.break_index == 1
    assert result.reason == "hash mismatch"
    assert result.summary() == "broken links: 1 of 3"


def test_verify_detects_broken_prev_hash_link(tmp_path: Path) -> None:
    path = tmp_path / "gate.jsonl"
    logger = AuditLogger(path)
    logger.append("coa_proposed", "Info", {"coa_id": "a"})
    logger.append("gate_decision", "High", {"status": "APPROVED"})
    records = logger.records()
    records[1]["prev_hash"] = "0" * 63 + "1"
    result = verify_audit_chain(records)
    assert not result.ok
    assert result.break_index == 1
    assert result.reason == "broken prev_hash link"


def test_demo_tamper_detection_roundtrip(tmp_path: Path) -> None:
    """Full demo: seal → verify → tamper → detect → restore (<3s)."""
    path = tmp_path / "gate.jsonl"
    t0 = time.perf_counter()
    rc = run_demo(path=path, quiet=True)
    elapsed = time.perf_counter() - t0
    assert rc == 0
    assert elapsed < 3.0
    assert verify_audit_chain(load_audit_records(path)).ok
    write_audit_records(path, load_audit_records(path))
    assert verify_audit_chain(load_audit_records(path)).ok


def test_demo_cli_main_temp_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import demo_tamper_detection as demo

    real_tmp = tempfile.TemporaryDirectory

    class _Tmp(real_tmp):  # type: ignore[misc,valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs = dict(kwargs)
            kwargs["dir"] = str(tmp_path)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(demo.tempfile, "TemporaryDirectory", _Tmp)
    assert demo.main([]) == 0
