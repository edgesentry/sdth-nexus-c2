"""Append-only OCSF-shaped audit log with hash chaining.

Optionally dual-writes a parallel edgesentry-rs AuditRecord chain
(``eds_chain.json``) via :mod:`core.audit_eds` for BLAKE3 + Ed25519 sealing.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.schema import canonical_json, sha256_hex, utc_now

if TYPE_CHECKING:
    from core.audit_eds import EdsChainWriter

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


def broken_link_count(records: list[dict[str, Any]]) -> int:
    """Count records whose prev_hash does not link to the prior digest."""
    prev = GENESIS_PREV
    broken = 0
    for rec in records:
        if rec.get("prev_hash") != prev:
            broken += 1
        prev = str(rec.get("hash") or "")
    return broken


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
            return f"broken links: 0 of {self.total}"
        broken = len(self.errors) if self.errors else 1
        return f"broken links: {broken} of {self.total}"


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


def inject_one_char_tamper(
    records: list[dict[str, Any]], index: int = 1
) -> list[dict[str, Any]]:
    """Flip one character in record[index] payload without updating ``hash``.

    Demo / pitch helper (issues #74 / #88): content digest diverges while the
    stored ``hash`` and ``prev_hash`` links stay as sealed — full
    :func:`verify_audit_chain` reports ``hash mismatch``.
    """
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


class AuditLogger:
    def __init__(
        self,
        path: str | Path,
        *,
        quarantine_broken: bool = True,
        eds_chain_path: str | Path | None = None,
        eds_enabled: bool | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS_PREV
        self._eds: EdsChainWriter | None = None
        if eds_enabled is None:
            # Dual-write when the bridge is loadable (opt-out via C2_EDS=0).
            import os

            eds_enabled = os.environ.get("C2_EDS", "1").strip() not in {"0", "false", "no"}
        if eds_enabled:
            self._init_eds(eds_chain_path)
        if quarantine_broken:
            self._quarantine_if_broken()
        self._rewind_from_disk()

    def _init_eds(self, eds_chain_path: str | Path | None) -> None:
        try:
            from core.audit_eds import EdsChainWriter

            chain = (
                Path(eds_chain_path) if eds_chain_path else self.path.with_name("eds_chain.json")
            )
            key = chain.with_name("eds_key.json")
            writer = EdsChainWriter(path=chain, key_path=key)
            if writer.available:
                self._eds = writer
                # Backfill EDS sidecar if OCSF trail already exists.
                ocsf = load_audit_records(self.path)
                if ocsf and not writer.records():
                    for i, rec in enumerate(ocsf, start=1):
                        body = {k: v for k, v in rec.items() if k != "hash"}
                        payload = canonical_json(body).encode("utf-8")
                        activity = str(rec.get("activity_name") or "event")
                        writer.append_payload(payload, object_ref=f"gate/{i}/{activity}")
                logger.info("EDS dual-write enabled (%s) → %s", writer.backend, chain)
            else:
                logger.debug("EDS dual-write unavailable (backend=%s)", writer.backend)
        except Exception as exc:
            logger.warning("EDS dual-write init failed: %s", exc)

    @property
    def eds(self) -> EdsChainWriter | None:
        return self._eds

    def records(self) -> list[dict[str, Any]]:
        return load_audit_records(self.path)

    def replace_records(self, records: list[dict[str, Any]]) -> None:
        """Overwrite the jsonl file (used to hydrate after ephemeral container disk reset)."""
        write_audit_records(self.path, records)
        self._rewind_from_disk()
        if self._eds is not None:
            # Rebuild EDS sidecar from OCSF bodies (best-effort).
            self._eds.clear()
            for i, rec in enumerate(records, start=1):
                body = {k: v for k, v in rec.items() if k != "hash"}
                payload = canonical_json(body).encode("utf-8")
                activity = str(rec.get("activity_name") or "event")
                self._eds.append_payload(payload, object_ref=f"gate/{i}/{activity}")

    def overwrite_ocsf_keep_eds(self, records: list[dict[str, Any]]) -> None:
        """Overwrite OCSF jsonl without rebuilding the EDS sidecar (tamper demo)."""
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
        if self._eds is not None:
            self._eds.clear()
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
        # Seal OCSF body (pre-hash) into the EDS sidecar when available.
        if self._eds is not None:
            seq = self._eds.next_sequence
            payload = canonical_json(record).encode("utf-8")
            self._eds.append_payload(payload, object_ref=f"gate/{seq}/{event_name}")
        record["hash"] = digest
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        self._prev = digest
        return record
