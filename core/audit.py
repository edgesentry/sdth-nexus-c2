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
        if self.path.exists():
            last = None
            with self.path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        last = json.loads(line)
            if last and "hash" in last:
                self._prev = last["hash"]

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
