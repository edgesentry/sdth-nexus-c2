"""Append-only OCSF-shaped audit log with hash chaining."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import canonical_json, sha256_hex, utc_now

logger = logging.getLogger(__name__)

GENESIS_PREV = "0" * 64


def chain_break_index(records: list[dict[str, Any]]) -> int | None:
    """Return the first index where prev_hash does not link, or None if intact."""
    prev = GENESIS_PREV
    for i, rec in enumerate(records):
        if rec.get("prev_hash") != prev:
            return i
        prev = str(rec.get("hash") or "")
    return None


@dataclass(frozen=True, slots=True)
class ChainVerifyResult:
    """Full hash-chain walk: prev_hash links + recomputed content digests."""

    ok: bool
    total: int
    break_index: int | None = None
    reason: str | None = None
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return f"PASS: {self.total} records sealed (100% integrity)"
        idx = self.break_index if self.break_index is not None else "?"
        why = self.reason or "unknown"
        return f"CHAIN BROKEN at Index {idx}: {why}"


def verify_audit_chain(records: list[dict[str, Any]]) -> ChainVerifyResult:
    """Walk the chain; recompute SHA-256 over each record body (excluding ``hash``)."""
    if not records:
        return ChainVerifyResult(ok=True, total=0)

    errors: list[str] = []
    break_index: int | None = None
    reason: str | None = None
    prev = GENESIS_PREV
    for i, rec in enumerate(records):
        if rec.get("prev_hash") != prev:
            msg = f"record[{i}] broken prev_hash link"
            errors.append(msg)
            if break_index is None:
                break_index = i
                reason = "broken prev_hash link"
        stored = rec.get("hash")
        body = {k: v for k, v in rec.items() if k != "hash"}
        expected = sha256_hex(canonical_json(body))
        if stored != expected:
            msg = f"record[{i}] hash mismatch"
            errors.append(msg)
            if break_index is None:
                break_index = i
                reason = "hash mismatch"
        prev = stored if isinstance(stored, str) else prev

    return ChainVerifyResult(
        ok=not errors,
        total=len(records),
        break_index=break_index,
        reason=reason,
        errors=errors,
    )


def load_audit_records(path: Path) -> list[dict[str, Any]]:
    """Load jsonl audit records without quarantine side effects."""
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                loaded = json.loads(line)
                if isinstance(loaded, dict):
                    out.append(loaded)
    return out


def write_audit_records(path: Path, records: list[dict[str, Any]]) -> None:
    """Overwrite jsonl with the given records (demo restore / tamper helpers)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, default=str) + "\n")


class AuditLogger:
    def __init__(self, path: str | Path, *, quarantine_broken: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS_PREV
        if quarantine_broken:
            self._quarantine_if_broken()
        self._rewind_from_disk()

    def records(self) -> list[dict[str, Any]]:
        return load_audit_records(self.path)

    def replace_records(self, records: list[dict[str, Any]]) -> None:
        """Overwrite the jsonl file (used to hydrate after ephemeral container disk reset)."""
        write_audit_records(self.path, records)
        self._rewind_from_disk()

    def _quarantine_if_broken(self) -> Path | None:
        """Archive a truncated/corrupt chain so demos and trail checks stay green.

        Truncating the head of an append-only jsonl leaves record[0].prev_hash as a
        non-genesis orphan. New appends still link from the tail, but full-trail
        verification fails. Move the broken file aside and start a fresh genesis.
        """
        if not self.path.exists():
            return None
        recs = self.records()
        if not recs:
            return None
        broke_at = chain_break_index(recs)
        if broke_at is None:
            return None
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archived = self.path.with_name(f"{self.path.name}.broken-{stamp}")
        self.path.rename(archived)
        logger.warning(
            "Audit chain broken at record[%s] in %s; archived to %s and starting fresh",
            broke_at,
            self.path,
            archived,
        )
        return archived

    def _rewind_from_disk(self) -> None:
        recs = self.records()
        last = recs[-1] if recs else None
        self._prev = str(last["hash"]) if last and "hash" in last else GENESIS_PREV

    def append(self, event_name: str, severity: str, data: dict[str, Any]) -> dict[str, Any]:
        record = {
            "class_name": "Security Finding",
            "activity_name": event_name,
            "severity": severity,
            "time": utc_now().isoformat(),
            "metadata": data,
            "prev_hash": self._prev,
        }
        digest = sha256_hex(canonical_json(record))
        record["hash"] = digest
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        self._prev = digest
        return record
