#!/usr/bin/env python3
"""Slide 11 operational benchmarks for NexusGate C2.

Metrics (fail = non-zero exit):
  Gate latency (p95)         < 50 ms   (100 synthetic COA evals)
  Interlock fast-reject      <  5 ms   (subset of the above)
  Unauthorized taskings        = 0     (geofence / speed / duplicate / timeout)
  Picture-to-Ack roundtrip   <  3.0 s  (approve → inbox → ack)
  Audit trace integrity      = 100%    (hash-chain walk)

Usage:
  uv run python scripts/benchmark.py
  uv run python scripts/benchmark.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.audit import AuditLogger
from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.gate import LatencyBoundedGate
from core.interlock import DeterministicInterlock
from core.schema import canonical_json, sha256_hex
from fastapi.testclient import TestClient

from app import c2_server

# ---------------------------------------------------------------------------
# Targets (Slide 11)
# ---------------------------------------------------------------------------

GATE_P95_MS = 50.0
FAST_REJECT_MS = 5.0
UNAUTHORIZED_MAX = 0
ROUNDTRIP_S = 3.0
GATE_SAMPLES = 100

SAFE_COORDS = (1.2500, 103.8200)
GEOFENCE_COORDS = (1.2310, 103.8510)  # inside demo_no_go in maritime_defense_policy.yaml

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
class MetricResult:
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


# ---------------------------------------------------------------------------
# 1) Gate latency
# ---------------------------------------------------------------------------


async def _run_gate_samples(
    gate: LatencyBoundedGate, n: int
) -> tuple[list[float], list[float]]:
    all_ms: list[float] = []
    reject_ms: list[float] = []

    for i in range(n):
        if i % 2 == 0:
            coa = CourseOfAction(
                target_coordinates=SAFE_COORDS,
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="BENCHMARK_OK",
                confidence=0.99,
            )
            expect = GateVerdict.APPROVED
        else:
            coa = CourseOfAction(
                target_coordinates=GEOFENCE_COORDS,
                tier=ActionTier.TIER_0_AUTONOMOUS,
                intent="BENCHMARK_GEOFENCE",
                speed_kt=5.0,
            )
            expect = GateVerdict.REJECTED_FAST

        t0 = time.perf_counter()
        verdict, _token = await gate.evaluate(coa, None)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        all_ms.append(elapsed_ms)

        if verdict != expect:
            raise RuntimeError(f"unexpected verdict {verdict} (expected {expect})")
        if expect == GateVerdict.REJECTED_FAST:
            reject_ms.append(elapsed_ms)

    return all_ms, reject_ms


def bench_gate_latency(n: int = GATE_SAMPLES) -> list[MetricResult]:
    """100 COA evaluations: mix of approve + fast-reject paths."""
    interlock = DeterministicInterlock(
        forbidden_zones=FORBIDDEN_ZONES,
        max_speed_kt=40.0,
    )
    gate = LatencyBoundedGate(timeout_sec=5.0, interlock=interlock)
    all_ms, reject_ms = asyncio.run(_run_gate_samples(gate, n))

    all_sorted = sorted(all_ms)
    reject_sorted = sorted(reject_ms)
    p95 = _percentile(all_sorted, 95)
    reject_p95 = _percentile(reject_sorted, 95) if reject_sorted else 0.0
    mean = statistics.fmean(all_ms)

    return [
        MetricResult(
            name="Gate latency (p95)",
            value=round(p95, 3),
            unit="ms",
            target=f"< {GATE_P95_MS:g} ms",
            passed=p95 < GATE_P95_MS,
            detail=f"n={n} mean={mean:.3f} ms  min={min(all_ms):.3f}  max={max(all_ms):.3f}",
        ),
        MetricResult(
            name="Interlock fast-reject (p95)",
            value=round(reject_p95, 3),
            unit="ms",
            target=f"< {FAST_REJECT_MS:g} ms",
            passed=reject_p95 < FAST_REJECT_MS,
            detail=f"n={len(reject_ms)} rejects",
        ),
    ]


# ---------------------------------------------------------------------------
# 2) Unauthorized taskings must be 0
# ---------------------------------------------------------------------------


async def _unauthorized_cases(gate: LatencyBoundedGate) -> tuple[int, list[str]]:
    interlock = gate.interlock
    leaks = 0
    cases: list[str] = []

    # Geofence
    coa_geo = CourseOfAction(
        target_coordinates=GEOFENCE_COORDS,
        tier=ActionTier.TIER_1_HITL,
        intent="GEO_PROBE",
    )
    v, _ = await gate.evaluate(coa_geo, None)
    if v == GateVerdict.APPROVED:
        leaks += 1
        cases.append("geofence→APPROVED")
    else:
        cases.append(f"geofence→{v.value}")

    # Speed breach
    coa_spd = CourseOfAction(
        target_coordinates=SAFE_COORDS,
        tier=ActionTier.TIER_0_AUTONOMOUS,
        intent="SPEED_PROBE",
        speed_kt=99.0,
    )
    v, _ = await gate.evaluate(coa_spd, None)
    if v == GateVerdict.APPROVED:
        leaks += 1
        cases.append("speed→APPROVED")
    else:
        cases.append(f"speed→{v.value}")

    # Duplicate active task
    coa_ok = CourseOfAction(
        target_coordinates=SAFE_COORDS,
        tier=ActionTier.TIER_0_AUTONOMOUS,
        intent="DUP_BASE",
        target_entity_id="ENT-DUP",
    )
    v_ok, _ = await gate.evaluate(coa_ok, None)
    if v_ok != GateVerdict.APPROVED:
        raise RuntimeError(f"baseline approve failed: {v_ok}")
    interlock.register_active(coa_ok)
    coa_dup = CourseOfAction(
        coa_id=coa_ok.coa_id,
        target_coordinates=SAFE_COORDS,
        tier=ActionTier.TIER_0_AUTONOMOUS,
        intent="DUP_BASE",
        target_entity_id="ENT-DUP",
    )
    v, _ = await gate.evaluate(coa_dup, None)
    if v == GateVerdict.APPROVED:
        leaks += 1
        cases.append("duplicate→APPROVED")
    else:
        cases.append(f"duplicate→{v.value}")

    # Timeout / empty operator channel → fail closed (not APPROVED)
    coa_to = CourseOfAction(
        target_coordinates=SAFE_COORDS,
        tier=ActionTier.TIER_1_HITL,
        intent="TIMEOUT_PROBE",
        timeout_seconds=0.1,
    )
    empty: asyncio.Queue[str] = asyncio.Queue()
    v, token = await gate.evaluate(coa_to, empty)
    if v == GateVerdict.APPROVED:
        leaks += 1
        cases.append("timeout→APPROVED")
    else:
        cases.append(f"timeout→{v.value}({token.reason})")

    return leaks, cases


def bench_unauthorized() -> MetricResult:
    """Geofence, speed, duplicate, and timeout must all fail closed (no APPROVED)."""
    interlock = DeterministicInterlock(
        forbidden_zones=FORBIDDEN_ZONES,
        max_speed_kt=40.0,
    )
    gate = LatencyBoundedGate(timeout_sec=0.15, interlock=interlock)
    leaks, cases = asyncio.run(_unauthorized_cases(gate))

    return MetricResult(
        name="Unauthorized taskings",
        value=leaks,
        unit="",
        target=f"= {UNAUTHORIZED_MAX}",
        passed=leaks <= UNAUTHORIZED_MAX,
        detail="; ".join(cases),
    )


# ---------------------------------------------------------------------------
# 3) Picture-to-Ack roundtrip via C2 REST
# ---------------------------------------------------------------------------


def bench_picture_to_ack() -> MetricResult:
    """End-to-end: propose S2 → approve → inbox → ack; wall time from approve."""
    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / "bench_gate.jsonl"
        c2_server._runtime = c2_server.C2Runtime(audit_path=audit_path)
        with TestClient(c2_server.app) as client:
            proposed = client.post(
                "/api/gate/proposals",
                json={"scenario_id": "S2", "unit_id": "BENCH-NODE-01"},
            )
            proposed.raise_for_status()
            body = proposed.json()
            if body.get("status") != "QUEUED":
                return MetricResult(
                    name="Picture-to-Ack roundtrip",
                    value=-1,
                    unit="s",
                    target=f"< {ROUNDTRIP_S:g} s",
                    passed=False,
                    detail=f"unexpected propose status: {body.get('status')}",
                )
            coa_id = body["coa"]["coa_id"]

            t0 = time.perf_counter()
            approved = client.post(
                "/api/gate/approve",
                json={"coa_id": coa_id, "decision": "y", "operator_id": "bench"},
            )
            approved.raise_for_status()
            inbox = client.get(
                "/api/recipient/inbox",
                params={"unit_id": "BENCH-NODE-01"},
            )
            inbox.raise_for_status()
            if inbox.json()["count"] < 1:
                return MetricResult(
                    name="Picture-to-Ack roundtrip",
                    value=-1,
                    unit="s",
                    target=f"< {ROUNDTRIP_S:g} s",
                    passed=False,
                    detail="inbox empty after approve",
                )
            ack = client.post(
                "/api/recipient/ack",
                json={
                    "coa_id": coa_id,
                    "unit_id": "BENCH-NODE-01",
                    "message": "bench ack",
                },
            )
            ack.raise_for_status()
            if ack.json()["status"] != "ACKED":
                return MetricResult(
                    name="Picture-to-Ack roundtrip",
                    value=-1,
                    unit="s",
                    target=f"< {ROUNDTRIP_S:g} s",
                    passed=False,
                    detail=f"ack status={ack.json().get('status')}",
                )
            elapsed = time.perf_counter() - t0

    return MetricResult(
        name="Picture-to-Ack roundtrip",
        value=round(elapsed, 4),
        unit="s",
        target=f"< {ROUNDTRIP_S:g} s",
        passed=elapsed < ROUNDTRIP_S,
        detail="approve → inbox poll → signed ack (S2)",
    )


# ---------------------------------------------------------------------------
# 4) Audit hash-chain integrity
# ---------------------------------------------------------------------------


def _verify_audit_chain(path: Path) -> tuple[int, int, list[str]]:
    """Return (ok_links, total_records, errors). Recomputes hashes."""
    if not path.exists():
        return 0, 0, ["audit file missing"]

    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    errors: list[str] = []
    prev = "0" * 64
    ok = 0
    for i, rec in enumerate(records):
        if rec.get("prev_hash") != prev:
            errors.append(f"record[{i}] broken prev_hash link")
        else:
            ok += 1
        stored = rec.get("hash")
        body = {k: v for k, v in rec.items() if k != "hash"}
        expected = sha256_hex(canonical_json(body))
        if stored != expected:
            errors.append(f"record[{i}] hash mismatch")
        prev = stored if isinstance(stored, str) else prev
    return ok, len(records), errors


def bench_audit_integrity() -> MetricResult:
    """Write a short chain via AuditLogger then walk + recompute hashes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "integrity.jsonl"
        logger = AuditLogger(path)
        for i in range(12):
            logger.append("bench_event", "Low", {"i": i, "payload": f"row-{i}"})

        # Also exercise C2 path so trail includes gate-shaped events
        c2_server._runtime = c2_server.C2Runtime(audit_path=path)
        with TestClient(c2_server.app) as client:
            prop = client.post(
                "/api/gate/proposals",
                json={"scenario_id": "S2", "unit_id": "AUDIT-NODE"},
            )
            prop.raise_for_status()
            coa_id = prop.json()["coa"]["coa_id"]
            client.post(
                "/api/gate/approve",
                json={"coa_id": coa_id, "decision": "y"},
            ).raise_for_status()
            client.post(
                "/api/recipient/ack",
                json={"coa_id": coa_id, "unit_id": "AUDIT-NODE"},
            ).raise_for_status()

        ok, total, errors = _verify_audit_chain(path)
        if total and not errors and ok == total:
            integrity_pct = 100.0
        else:
            integrity_pct = 0.0

        return MetricResult(
            name="Audit trace integrity",
            value=round(integrity_pct, 1),
            unit="%",
            target="= 100%",
            passed=integrity_pct == 100.0 and total > 0 and not errors,
            detail=f"records={total} ok_links={ok}"
            + (f" errors={errors[:3]}" if errors else ""),
        )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_report(results: list[MetricResult]) -> int:
    width = 72
    print("=" * width)
    print("  NexusGate C2 — Slide 11 Operational Benchmarks")
    print("=" * width)

    failures = 0
    for m in results:
        status = "PASS" if m.passed else "FAIL"
        if not m.passed:
            failures += 1
        if isinstance(m.value, float):
            shown = f"{m.value:g} {m.unit}".strip()
        else:
            shown = f"{m.value} {m.unit}".strip()
        print(f"  [{status}] {m.name}")
        print(f"         measured: {shown}")
        print(f"         target:   {m.target}")
        if m.detail:
            print(f"         detail:   {m.detail}")
        print()

    print("-" * width)
    if failures:
        print(f"  RESULT: {failures} metric(s) FAILED — demo proof incomplete")
        print("=" * width)
        return 1
    print("  RESULT: ALL METRICS PASSED — ready for Slide 11 proof")
    print("=" * width)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Slide 11 NexusGate C2 operational benchmarks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Targets:\n"
            f"  Gate latency (p95)       < {GATE_P95_MS:g} ms\n"
            f"  Fast-reject (p95)        < {FAST_REJECT_MS:g} ms\n"
            f"  Unauthorized taskings    = {UNAUTHORIZED_MAX}\n"
            f"  Picture-to-Ack           < {ROUNDTRIP_S:g} s\n"
            "  Audit integrity          = 100%\n"
        ),
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=GATE_SAMPLES,
        help=f"COA evaluations for gate latency (default {GATE_SAMPLES})",
    )
    args = parser.parse_args(argv)

    results: list[MetricResult] = []
    results.extend(bench_gate_latency(n=max(2, args.samples)))
    results.append(bench_unauthorized())
    results.append(bench_picture_to_ack())
    results.append(bench_audit_integrity())
    return _print_report(results)


if __name__ == "__main__":
    sys.exit(main())
