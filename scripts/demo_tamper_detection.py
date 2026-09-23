#!/usr/bin/env python3
"""Pitch-day OCSF audit tamper detection demo (issue #74).

Shows defense evaluators that a 1-character insider edit of ``gate.jsonl``
is detected immediately via SHA-256 hash-chain verification, and that
tasking must halt until the chain is restored.

Usage:
  uv run python scripts/demo_tamper_detection.py
  uv run python scripts/demo_tamper_detection.py --path /tmp/tamper-demo.jsonl

Exit 0 on successful detect + restore; non-zero on unexpected failure.
Target wall time: < 3 s.
"""

from __future__ import annotations

import argparse
import copy
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from core.audit import (
    AuditLogger,
    load_audit_records,
    verify_audit_chain,
    write_audit_records,
)


def _build_legitimate_chain(path: Path) -> list[dict[str, Any]]:
    """Seal a minimal closed-loop: propose → approve → ack (≥3 chained records)."""
    if path.exists():
        path.unlink()
    logger = AuditLogger(path, quarantine_broken=False)
    logger.append(
        "coa_proposed",
        "Info",
        {"coa_id": "demo-tamper-coa", "scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    logger.append(
        "gate_decision",
        "High",
        {
            "coa_id": "demo-tamper-coa",
            "decision": "y",
            "status": "APPROVED",
            "operator_id": "pitch-demo",
        },
    )
    logger.append(
        "tasking_issued",
        "High",
        {"coa_id": "demo-tamper-coa", "unit_id": "CUE-NODE-01"},
    )
    logger.append(
        "recipient_ack",
        "High",
        {"coa_id": "demo-tamper-coa", "unit_id": "CUE-NODE-01", "message": "field-ack"},
    )
    return logger.records()


def _inject_one_char_tamper(records: list[dict[str, Any]], index: int = 1) -> list[dict[str, Any]]:
    """Flip one character in record[index] payload without updating ``hash``."""
    if index < 0 or index >= len(records):
        raise IndexError(f"tamper index {index} out of range (n={len(records)})")
    tampered = copy.deepcopy(records)
    meta = tampered[index].setdefault("metadata", {})
    if not isinstance(meta, dict):
        raise TypeError("record metadata must be a dict")

    def _flip_approved(key: str) -> bool:
        value = meta.get(key)
        if isinstance(value, str) and value == "APPROVED":
            # 1-char flip: APPROVED → XPPROVED (content digests diverge).
            meta[key] = "XPPROVED"
            return True
        if isinstance(value, str) and len(value) >= 1:
            meta[key] = ("X" if value[0] != "X" else "Y") + value[1:]
            return True
        return False

    # C2 gate_decision seals ``verdict``; demo logger uses ``status``.
    if _flip_approved("status") or _flip_approved("verdict"):
        return tampered

    # Fallback: flip one digit in the timestamp string.
    ts = str(tampered[index].get("time") or "")
    if not ts:
        raise ValueError("no status/verdict or time field to tamper")
    chars = list(ts)
    for i, ch in enumerate(chars):
        if ch.isdigit():
            chars[i] = "0" if ch != "0" else "1"
            break
    else:
        chars[0] = "X" if chars[0] != "X" else "Y"
    tampered[index]["time"] = "".join(chars)
    return tampered


def run_demo(*, path: Path, quiet: bool = False) -> int:
    """Execute intact → tamper → detect → restore → re-verify. Returns process exit code."""
    started = time.perf_counter()
    lines: list[str] = []

    def say(msg: str) -> None:
        lines.append(msg)
        if not quiet:
            print(msg)

    say("=== NexusGate OCSF Tamper Detection Demo (#74) ===")
    say(f"audit path: {path}")

    # 1) Legitimate closed loop
    original = _build_legitimate_chain(path)
    say(f"[1] Sealed legitimate closed loop: {len(original)} OCSF records")

    # 2) Verify intact
    before = verify_audit_chain(original)
    say(f"[2] Integrity check: {before.summary()}")
    if not before.ok or before.total < 3:
        say("FAIL: expected intact chain with ≥3 records before tamper")
        return 1

    # 3) Inject 1-character tamper into record[1]
    tampered = _inject_one_char_tamper(original, index=1)
    write_audit_records(path, tampered)
    flipped_meta = tampered[1].get("metadata", {})
    flipped = None
    if isinstance(flipped_meta, dict):
        flipped = flipped_meta.get("status") or flipped_meta.get("verdict")
    say(f"[3] Injected 1-char tamper into record[1] (decision field → {flipped!r})")

    # 4) Detect + halt tasking
    after = verify_audit_chain(load_audit_records(path))
    say(f"[4] Integrity check: {after.summary()}")
    if after.ok or after.break_index != 1 or after.reason != "hash mismatch":
        say(
            "FAIL: expected hash mismatch at Index 1 "
            f"(got ok={after.ok} index={after.break_index} reason={after.reason} "
            f"summary={after.summary()!r})"
        )
        return 1
    say(f"     {after.summary()} — HALT tasking (security violation)")
    say("     Operator alert: do not dispatch; preserve forensic copy of tampered jsonl")

    # 5) Restore + recover
    write_audit_records(path, original)
    restored = verify_audit_chain(load_audit_records(path))
    say(f"[5] Restored original chain: {restored.summary()}")
    if not restored.ok:
        say("FAIL: restore did not recover integrity")
        return 1

    elapsed = time.perf_counter() - started
    say(f"Done in {elapsed:.3f}s (target < 3.0s)")
    if elapsed >= 3.0:
        say("WARN: exceeded 3s pitch budget (still functionally OK)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OCSF audit tamper detection demo (#74)")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Audit jsonl path (default: temporary file under /tmp)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout (tests)")
    args = parser.parse_args(argv)

    if args.path is not None:
        return run_demo(path=args.path, quiet=args.quiet)

    with tempfile.TemporaryDirectory(prefix="nexusgate-tamper-") as tmp:
        return run_demo(path=Path(tmp) / "gate.jsonl", quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
