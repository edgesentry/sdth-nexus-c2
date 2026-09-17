"""Pitch-3: deterministic gate under 100+ track flood."""

from __future__ import annotations

from app.bench_stress import (
    GATE_P95_MS,
    bench_track_flood_stress,
    build_flood_graph,
)


def test_flood_graph_yields_100_plus_tracks() -> None:
    graph = build_flood_graph(120)
    assert len(graph.all_tracks()) >= 100
    assert len(graph.observations) == 120


def test_track_flood_stress_metrics_pass() -> None:
    results = bench_track_flood_stress(n_tracks=120, n_proposals=80)
    assert len(results) == 2
    by_name = {m.name: m for m in results}

    p95 = by_name["Track-flood stress (gate p95)"]
    assert p95.passed, p95.detail
    assert isinstance(p95.value, float)
    assert p95.value < GATE_P95_MS
    assert "tracks=120" in p95.detail

    unauth = by_name["Track-flood unauthorized"]
    assert unauth.passed, unauth.detail
    assert unauth.value == 0
