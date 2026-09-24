"""Pitch-3: deterministic gate under 100+ track flood."""

from __future__ import annotations

import pytest
from app import c2_server
from app.bench_stress import (
    GATE_P95_MS,
    REST_PROPOSE_P95_MS,
    bench_track_flood_stress,
    build_flood_graph,
)
from core.ontology import SpatialEntityGraph


def test_flood_graph_yields_100_plus_tracks() -> None:
    graph = build_flood_graph(120)
    assert len(graph.all_tracks()) >= 100
    assert len(graph.observations) == 120


def test_track_flood_stress_requires_100_tracks() -> None:
    with pytest.raises(ValueError, match="stress requires ≥100 tracks"):
        bench_track_flood_stress(n_tracks=50, n_proposals=4)


def test_track_flood_stress_metrics_pass() -> None:
    results = bench_track_flood_stress(n_tracks=120, n_proposals=80)
    assert len(results) == 3
    by_name = {m.name: m for m in results}

    p95 = by_name["Track-flood stress (gate p95)"]
    assert p95.passed, p95.detail
    assert isinstance(p95.value, float)
    assert p95.value < GATE_P95_MS
    assert "tracks=120" in p95.detail

    rest = by_name["Track-flood REST propose (p95)"]
    assert rest.passed, rest.detail
    assert isinstance(rest.value, float)
    assert rest.value < REST_PROPOSE_P95_MS
    assert "warmup=" in rest.detail

    unauth = by_name["Track-flood unauthorized"]
    assert unauth.passed, unauth.detail
    assert unauth.value == 0


def test_track_flood_stress_restores_c2_runtime() -> None:
    prior = c2_server.get_runtime()
    prior_id = id(prior)
    prior_track_count = len(prior.graph.all_tracks())

    bench_track_flood_stress(n_tracks=100, n_proposals=8)

    restored = c2_server.get_runtime()
    assert id(restored) == prior_id
    assert len(restored.graph.all_tracks()) == prior_track_count
    assert isinstance(restored.graph, SpatialEntityGraph)
