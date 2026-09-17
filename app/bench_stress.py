"""Pitch-3 deterministic gate stress: 100+ synthetic tracks (Phase 2 thin).

Demo fidelity only — Phase 5 owns 1,000+ swarm / air-gap / dual-key.
"""

from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.gate import LatencyBoundedGate
from core.interlock import DeterministicInterlock
from core.ontology import SpatialEntityGraph
from core.schema import Observation
from fastapi.testclient import TestClient

from app import c2_server

GATE_P95_MS = 50.0
UNAUTHORIZED_MAX = 0
STRESS_TRACKS = 120
STRESS_PROPOSALS = 120

SAFE_COORDS = (1.2500, 103.8200)
GEOFENCE_COORDS = (1.2310, 103.8510)
FLOOD_ORIGIN = (1.1000, 103.6000)
FLOOD_STEP_DEG = 0.05  # ~5.5 km — beyond associate_radius (2 km)

FORBIDDEN_ZONES: list[dict[str, Any]] = [
    {
        "name": "demo_no_go",
        "polygon": [
            [1.2300, 103.8500],
            [1.2300, 103.8520],
            [1.2320, 103.8520],
            [1.2320, 103.8500],
            [1.2300, 103.8500],
        ],
    }
]


@dataclass
class StressMetric:
    name: str
    value: float | int | str
    unit: str
    target: str
    passed: bool
    detail: str = ""


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def synthetic_flood_observations(n: int) -> list[Observation]:
    """Build n geographically spaced observations → n distinct tracks."""
    modalities = ("radar", "ais", "eo", "rf", "adsb", "social")
    origin_lat, origin_lon = FLOOD_ORIGIN
    cols = max(1, int(n**0.5) + 1)
    obs: list[Observation] = []
    for i in range(n):
        row, col = divmod(i, cols)
        lat = origin_lat + row * FLOOD_STEP_DEG
        lon = origin_lon + col * FLOOD_STEP_DEG
        obs.append(
            Observation(
                source_id=f"FLOOD-SRC-{i:04d}",
                entity_hint=f"FLOOD-ENT-{i:04d}",
                latitude=lat,
                longitude=lon,
                speed_mps=5.0 + (i % 10),
                confidence=0.4 + (i % 6) * 0.1,
                observed_at=datetime.now(UTC),
                modality=modalities[i % len(modalities)],
                attributes={"flood_index": i, "demo": "pitch3_stress"},
            )
        )
    return obs


def build_flood_graph(n_tracks: int) -> SpatialEntityGraph:
    """Ingest n spaced observations into a fresh SpatialEntityGraph."""
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many(synthetic_flood_observations(n_tracks))
    return graph


async def run_flood_gate_evals(
    gate: LatencyBoundedGate,
    *,
    n_proposals: int,
) -> tuple[list[float], int, int]:
    """Evaluate n proposals: ~25% safe, ~75% unauthorized probes.

    Returns (latencies_ms, unauthorized_leaks, reject_count).
    """
    latencies: list[float] = []
    leaks = 0
    rejects = 0

    for i in range(n_proposals):
        kind = i % 4
        if kind == 0:
            coa = CourseOfAction(
                target_coordinates=SAFE_COORDS,
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="FLOOD_OK",
                confidence=0.95,
                target_entity_id=f"FLOOD-OK-{i}",
            )
            expect_reject = False
        elif kind == 1:
            coa = CourseOfAction(
                target_coordinates=GEOFENCE_COORDS,
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="FLOOD_GEO",
                speed_kt=5.0,
            )
            expect_reject = True
        elif kind == 2:
            coa = CourseOfAction(
                target_coordinates=SAFE_COORDS,
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="FLOOD_SPEED",
                speed_kt=99.0,
            )
            expect_reject = True
        else:
            coa = CourseOfAction(
                target_coordinates=(0.0, 0.0),
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="FLOOD_NULL",
            )
            expect_reject = True

        t0 = time.perf_counter()
        verdict, _token = await gate.evaluate(coa, None)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        if expect_reject:
            rejects += 1
            if verdict == GateVerdict.APPROVED:
                leaks += 1
        elif verdict != GateVerdict.APPROVED:
            raise RuntimeError(f"flood safe COA not approved: {verdict}")

    return latencies, leaks, rejects


def run_rest_flood(
    graph: SpatialEntityGraph,
    *,
    n_proposals: int,
) -> tuple[list[float], int, int]:
    """Propose mixed COAs against a C2 runtime with flooded ontology.

    Returns (latencies_ms, unauthorized_leaks, api_track_count).
    """
    rest_ms: list[float] = []
    rest_leaks = 0
    api_tracks = 0

    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / "stress_gate.jsonl"
        runtime = c2_server.C2Runtime(audit_path=audit_path)
        runtime.graph = graph
        runtime.scenario_id = "STRESS-FLOOD"
        c2_server._runtime = runtime
        with TestClient(c2_server.app) as client:
            state = client.get("/api/ontology/state")
            state.raise_for_status()
            api_tracks = len(state.json().get("tracks", []))
            if api_tracks < 100:
                raise RuntimeError(f"ontology/state under-reported tracks: {api_tracks}")

            for i in range(min(40, n_proposals)):
                if i % 2 == 0:
                    payload: dict[str, Any] = {
                        "coa": {
                            "target_coordinates": list(SAFE_COORDS),
                            "tier": 0,
                            "intent": f"REST_FLOOD_OK_{i}",
                            "confidence": 0.9,
                        },
                        "unit_id": f"STRESS-NODE-{i % 5}",
                    }
                    expect_status = "APPROVED"
                else:
                    payload = {
                        "coa": {
                            "target_coordinates": list(GEOFENCE_COORDS),
                            "tier": 0,
                            "intent": f"REST_FLOOD_GEO_{i}",
                            "speed_kt": 5.0,
                        },
                        "unit_id": f"STRESS-NODE-{i % 5}",
                    }
                    expect_status = "REJECTED_FAST"

                t0 = time.perf_counter()
                resp = client.post("/api/gate/proposals", json=payload)
                rest_ms.append((time.perf_counter() - t0) * 1000.0)
                resp.raise_for_status()
                body = resp.json()
                status = body.get("status")
                if status != expect_status:
                    if expect_status == "REJECTED_FAST" and status in {
                        "QUEUED",
                        "APPROVED",
                    }:
                        rest_leaks += 1
                    elif expect_status == "APPROVED":
                        raise RuntimeError(
                            f"REST flood unexpected status for safe COA: {body}"
                        )

    return rest_ms, rest_leaks, api_tracks


def bench_track_flood_stress(
    n_tracks: int = STRESS_TRACKS,
    n_proposals: int = STRESS_PROPOSALS,
) -> list[StressMetric]:
    """Pitch-3 thin stress: 100+ tracks + mixed COA flood; p95 / unauthorized=0."""
    if n_tracks < 100:
        raise ValueError(f"stress requires ≥100 tracks (got {n_tracks})")

    graph = build_flood_graph(n_tracks)
    track_count = len(graph.all_tracks())
    if track_count < 100:
        raise RuntimeError(f"expected ≥100 tracks after flood ingest, got {track_count}")

    interlock = DeterministicInterlock(
        forbidden_zones=FORBIDDEN_ZONES,
        max_speed_kt=40.0,
    )
    gate = LatencyBoundedGate(timeout_sec=5.0, interlock=interlock)
    latencies, leaks, rejects = asyncio.run(
        run_flood_gate_evals(gate, n_proposals=n_proposals)
    )
    rest_ms, rest_leaks, api_tracks = run_rest_flood(graph, n_proposals=n_proposals)

    p95 = _percentile(sorted(latencies), 95)
    mean = statistics.fmean(latencies)
    rest_p95 = _percentile(sorted(rest_ms), 95) if rest_ms else 0.0
    total_leaks = leaks + rest_leaks

    return [
        StressMetric(
            name="Track-flood stress (gate p95)",
            value=round(p95, 3),
            unit="ms",
            target=f"< {GATE_P95_MS:g} ms",
            passed=p95 < GATE_P95_MS and track_count >= 100,
            detail=(
                f"tracks={track_count} proposals={n_proposals} "
                f"mean={mean:.3f} ms rejects={rejects} "
                f"rest_propose_p95={rest_p95:.3f} ms api_tracks={api_tracks}"
            ),
        ),
        StressMetric(
            name="Track-flood unauthorized",
            value=total_leaks,
            unit="",
            target=f"= {UNAUTHORIZED_MAX}",
            passed=total_leaks <= UNAUTHORIZED_MAX,
            detail=(
                f"gate_leaks={leaks} rest_leaks={rest_leaks} under tracks={track_count}"
            ),
        ),
    ]
