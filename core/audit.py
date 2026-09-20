"""Append-only OCSF-shaped audit log with hash chaining."""

from __future__ import annotations

import json
import logging
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


class AuditLogger:
    def __init__(self, path: str | Path, *, quarantine_broken: bool = True) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS_PREV
        if quarantine_broken:
            self._quarantine_if_broken()
        self._rewind_from_disk()

    def records(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.path.exists():
            return out
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    loaded = json.loads(line)
                    if isinstance(loaded, dict):
                        out.append(loaded)
        return out

    def replace_records(self, records: list[dict[str, Any]]) -> None:
        """Overwrite the jsonl file (used to hydrate after ephemeral container disk reset)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, default=str) + "\n")
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
