"""Append-only OCSF-shaped audit log with hash chaining."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.schema import canonical_json, sha256_hex, utc_now


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = "0" * 64
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

    def _rewind_from_disk(self) -> None:
        recs = self.records()
        last = recs[-1] if recs else None
        self._prev = str(last["hash"]) if last and "hash" in last else "0" * 64

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
