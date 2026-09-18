"""Normalize assumed upstream CandidateEvent (v1.3.0) into core Observations.

Sovereign-neutral ingress for macro space-based SAR scene-difference evidence.
Live upstream services are optional — demos use `tests/fixtures/candidate_event_assumed.json`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.schema import Observation
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "candidate_event_assumed.json"

SPACE_SAR_MODALITY = "space_sar"


class CandidateEventLocation(BaseModel):
    latitude: float
    longitude: float


class CandidateEventBoundingBox(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class CandidateEvent(BaseModel):
    """Assumed wire contract for upstream macro intelligence (v1.3.0)."""

    event_id: str
    timestamp: datetime
    source_id: str
    area_id: str = ""
    event_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    location: CandidateEventLocation
    bounding_box: CandidateEventBoundingBox | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


def load_assumed_fixture(path: Path | None = None) -> dict[str, Any]:
    """Load the offline CandidateEvent JSON fixture (stand-alone demos / tests)."""
    fixture_path = path or DEFAULT_FIXTURE
    with fixture_path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def parse_candidate_event(payload: dict[str, Any] | CandidateEvent) -> CandidateEvent:
    if isinstance(payload, CandidateEvent):
        return payload
    try:
        return CandidateEvent.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid CandidateEvent payload: {exc}") from exc


def candidate_event_to_observation(
    payload: dict[str, Any] | CandidateEvent,
) -> Observation:
    """Map CandidateEvent → Observation with modality ``space_sar``."""
    event = parse_candidate_event(payload)
    observed_at = event.timestamp
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    attrs: dict[str, Any] = {
        "area_id": event.area_id,
        "event_type": event.event_type,
        "ingress": "candidate_event",
        "schema_version": "1.3.0",
        **event.attributes,
    }
    if event.bounding_box is not None:
        attrs["bounding_box"] = event.bounding_box.model_dump()

    obs = Observation(
        observation_id=event.event_id,
        source_id=event.source_id,
        entity_hint=event.event_type,
        latitude=event.location.latitude,
        longitude=event.location.longitude,
        speed_mps=0.0,
        confidence=event.confidence,
        observed_at=observed_at,
        modality=SPACE_SAR_MODALITY,
        attributes=attrs,
    )
    obs.ensure_digest()
    return obs


def observation_from_assumed_fixture(path: Path | None = None) -> Observation:
    return candidate_event_to_observation(load_assumed_fixture(path))
