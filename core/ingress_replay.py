"""Append-only ingress replay log (not gate authority).

Successful CandidateEvent / open-feed POSTs can be re-run from
``.audit/ingress.jsonl`` without re-collecting upstream data.
Write failures must never fail the ingress path (warn only).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.schema import utc_now

logger = logging.getLogger(__name__)


class IngressReplayLog:
    """Plain jsonl append log — no hash chain (that remains ``gate.jsonl``)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def records(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.path.exists():
            return out
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                loaded = json.loads(line)
                if isinstance(loaded, dict):
                    out.append(loaded)
        return out

    def append(
        self,
        *,
        source: str,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Append one replayable ingress record. Returns None on write failure."""
        record: dict[str, Any] = {
            "received_at": utc_now().isoformat(),
            "source": source,
            "endpoint": endpoint,
            "payload": payload,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            logger.warning(
                "ingress replay log write failed (%s); ingress continues: %s",
                self.path,
                exc,
            )
            return None
        return record
