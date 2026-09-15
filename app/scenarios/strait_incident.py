"""Backward-compatible alias: former strait_incident → S1 sea-approach spoof."""

from __future__ import annotations

from typing import Any

from app.scenarios.s1_sea_approach_spoof import SPEC, _build_events


def build_strait_incident(**kwargs: Any) -> list[dict[str, Any]]:
    """Deprecated name; returns S1 defense events."""
    return SPEC.build_events()


build_sea_approach_spoof = _build_events
