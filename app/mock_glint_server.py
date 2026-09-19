"""GLINT Assumed-mock HTTP stub (issue #55).

Serves CandidateEvent v1.3.0 from ``tests/fixtures/candidate_event_assumed.json``
on ``http://127.0.0.1:5051`` until Team 02 live schema handover (Phase 4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

from app.adapters.sar_candidate_event import load_assumed_fixture

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 5051

app = FastAPI(title="GLINT Assumed-mock", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "glint-mock"}


@app.get("/api/candidate-event")
async def candidate_event() -> dict[str, Any]:
    """Return the assumed macro SAR CandidateEvent (v1.3.0)."""
    return load_assumed_fixture()


def cli_main() -> None:
    uvicorn.run("app.mock_glint_server:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)


if __name__ == "__main__":
    cli_main()
