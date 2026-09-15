"""Common defense scenario contract (app-layer only)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from core.coa import CourseOfAction
from core.ontology import SpatialEntityGraph


@dataclass
class Finding:
    """Actionable warning picture derived from disagreeing sensors."""

    scenario_id: str
    track_id: str
    threat_class: str
    warning_minutes_est: float
    mismatch_m: float
    confidence: float
    picture_summary: str
    adversarial_hypothesis: str
    spoof_sources: list[str] = field(default_factory=list)
    approach_sources: list[str] = field(default_factory=list)
    other_sources: list[str] = field(default_factory=list)
    message: str = ""

    def all_sources(self) -> list[str]:
        return list(dict.fromkeys(self.approach_sources + self.spoof_sources + self.other_sources))


class ScenarioSpec(Protocol):
    id: str
    title: str
    threat_class: str
    warning_minutes_est: float
    narrative: str
    asset_label: str

    def build_events(self) -> list[dict[str, Any]]: ...

    def detect(self, graph: SpatialEntityGraph) -> Finding | None: ...

    def build_coa(
        self, graph: SpatialEntityGraph, finding: Finding, *, timeout_seconds: float
    ) -> CourseOfAction: ...


@dataclass
class Scenario:
    id: str
    title: str
    threat_class: str
    warning_minutes_est: float
    narrative: str
    asset_label: str
    _build_events: Callable[[], list[dict[str, Any]]]
    _detect: Callable[[SpatialEntityGraph], Finding | None]
    _build_coa: Callable[[SpatialEntityGraph, Finding, float], CourseOfAction]

    def build_events(self) -> list[dict[str, Any]]:
        return self._build_events()

    def detect(self, graph: SpatialEntityGraph) -> Finding | None:
        return self._detect(graph)

    def build_coa(
        self,
        graph: SpatialEntityGraph,
        finding: Finding,
        *,
        timeout_seconds: float = 5.0,
    ) -> CourseOfAction:
        return self._build_coa(graph, finding, timeout_seconds)


def get_scenario(scenario_id: str) -> Scenario:
    from app.scenarios.registry import SCENARIOS

    key = scenario_id.strip().upper()
    if key not in SCENARIOS:
        known = ", ".join(sorted(SCENARIOS))
        raise KeyError(f"Unknown scenario {scenario_id!r}; choose one of: {known}")
    return SCENARIOS[key]


def list_scenario_ids() -> list[str]:
    from app.scenarios.registry import SCENARIOS

    return sorted(SCENARIOS.keys())
