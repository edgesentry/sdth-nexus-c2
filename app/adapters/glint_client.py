"""GLINT Assumed-mock HTTP client (issue #55).

Pulls CandidateEvent v1.3.0 from a local stub (default ``http://127.0.0.1:5051``)
or Team 02 live URL via ``GLINT_BASE_URL``. When unreachable, falls back to
``tests/fixtures/candidate_event_assumed.json`` (Core untouched on schema handover).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from app.adapters.sar_candidate_event import (
    DEFAULT_FIXTURE,
    CandidateEvent,
    load_assumed_fixture,
    parse_candidate_event,
)

DEFAULT_GLINT_BASE_URL = "http://127.0.0.1:5051"
DEFAULT_GLINT_TIMEOUT_S = 3.0
GLINT_EVENT_PATH = "/api/candidate-event"

SOURCE_UPSTREAM = "glint"
SOURCE_FIXTURE = "glint_fixture"


def resolve_glint_base_url(explicit: str | None = None) -> str:
    return (explicit or os.environ.get("GLINT_BASE_URL") or DEFAULT_GLINT_BASE_URL).rstrip("/")


def resolve_glint_timeout_s(explicit: float | None = None) -> float:
    if explicit is not None:
        return explicit
    raw = os.environ.get("GLINT_TIMEOUT_S")
    if raw is None or not raw.strip():
        return DEFAULT_GLINT_TIMEOUT_S
    return float(raw)


def annotate_glint_event(event: CandidateEvent) -> CandidateEvent:
    """Tag ingress provenance for Dual-SAR (#56) without rewriting Core fields."""
    attrs: dict[str, Any] = {
        **event.attributes,
        "ingress": "glint",
        "provenance": "assumed-mock",
        "schema_version": "1.3.0",
    }
    return event.model_copy(update={"attributes": attrs})


def load_glint_fixture(path: Path | None = None) -> CandidateEvent:
    return annotate_glint_event(
        parse_candidate_event(load_assumed_fixture(path or DEFAULT_FIXTURE))
    )


def fetch_glint_event(
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> CandidateEvent | None:
    """GET ``/api/candidate-event`` from GLINT mock/live. None on any failure."""
    url = f"{resolve_glint_base_url(base_url)}{GLINT_EVENT_PATH}"
    timeout = resolve_glint_timeout_s(timeout_s)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, OSError, ValueError, TypeError):
        return None
    if not isinstance(body, dict):
        return None
    try:
        return annotate_glint_event(parse_candidate_event(body))
    except ValueError:
        return None


def resolve_glint_events(
    *,
    pull_upstream: bool = False,
    use_fixture: bool = False,
    base_url: str | None = None,
    timeout_s: float | None = None,
    fixture_path: Path | None = None,
) -> tuple[list[CandidateEvent], str]:
    """Resolve GLINT macro events.

    Returns ``(events, source)`` where source is ``glint`` | ``glint_fixture``.
    """
    if pull_upstream:
        remote = fetch_glint_event(base_url=base_url, timeout_s=timeout_s)
        if remote is not None:
            return [remote], SOURCE_UPSTREAM
        return [load_glint_fixture(fixture_path)], SOURCE_FIXTURE

    if use_fixture:
        return [load_glint_fixture(fixture_path)], SOURCE_FIXTURE

    raise ValueError("Provide pull_glint=true or use_glint_fixture=true")
