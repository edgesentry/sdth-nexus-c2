"""19-step temporal streamer timeline."""

from __future__ import annotations

from datetime import UTC, datetime

from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import get_scenario
from app.scenarios.temporal import build_stream_timeline
from core.ontology import SpatialEntityGraph


def test_s2_timeline_has_19_steps() -> None:
    t0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
    steps = build_stream_timeline("S2", t0=t0)
    assert len(steps) == 19
    assert steps[0].t_minus_s == 60
    assert steps[-1].t_minus_s == 0
    assert steps[0].band == "early_recon"
    assert steps[10].band == "amber_contradiction"
    assert steps[-1].band == "warning_tasking"


def test_s2_amber_only_after_band_11() -> None:
    t0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
    steps = build_stream_timeline("S2", t0=t0)
    scenario = get_scenario("S2")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)

    first_amber: int | None = None
    for step in steps:
        if step.events:
            graph.ingest_many([normalize_sensor_event(e) for e in step.events])
        finding = scenario.detect(graph)
        if finding is not None and first_amber is None:
            first_amber = step.step
            assert finding.amber_alert == "COUNT_AND_BEARING_MISMATCH"
            assert finding.source_breakdown["social"]["claimed_count"] == 3
            assert finding.source_breakdown["radar"]["contact_count"] == 1

    assert first_amber is not None
    assert first_amber >= 11
    assert first_amber <= 15


def test_s1_timeline_spreads_events() -> None:
    steps = build_stream_timeline("S1")
    assert len(steps) == 19
    total_events = sum(len(s.events) for s in steps)
    assert total_events == len(get_scenario("S1").build_events())
