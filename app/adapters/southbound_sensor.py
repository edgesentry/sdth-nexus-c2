"""Southbound: normalize venue sensor payloads into core Observations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schema import Observation


def kt_to_mps(knots: float) -> float:
    return knots * 0.514444


def normalize_sensor_event(event: dict[str, Any]) -> Observation:
    """Convert a dict sensor event into a domain Observation."""
    observed_at = event.get("observed_at")
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    elif observed_at is None:
        observed_at = datetime.now(UTC)

    speed_kt = float(event.get("speed_kt", 0.0))
    obs_kwargs: dict[str, Any] = {
        "source_id": str(event["source_id"]),
        "entity_hint": str(event.get("entity_id", event["source_id"])),
        "latitude": float(event["latitude"]),
        "longitude": float(event["longitude"]),
        "speed_mps": kt_to_mps(speed_kt),
        "heading_deg": event.get("heading_deg"),
        "confidence": float(event.get("confidence", 0.5)),
        "observed_at": observed_at,
        "modality": str(event.get("modality", "generic")),
        "attributes": {
            "speed_kt": speed_kt,
            **{
                k: v
                for k, v in event.items()
                if k
                not in {
                    "source_id",
                    "entity_id",
                    "observation_id",
                    "latitude",
                    "longitude",
                    "speed_kt",
                    "heading_deg",
                    "confidence",
                    "observed_at",
                    "modality",
                }
            },
        },
    }
    if event.get("observation_id"):
        obs_kwargs["observation_id"] = str(event["observation_id"])
    obs = Observation(**obs_kwargs)
    obs.ensure_digest()
    return obs
