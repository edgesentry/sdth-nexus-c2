"""Core gate / interlock / stub tests."""

from __future__ import annotations

import asyncio

import pytest

from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.gate import LatencyBoundedGate
from core.interlock import DeterministicInterlock, point_in_polygon
from core.stub import StubEffector


def test_null_coordinates_rejected() -> None:
    gate = LatencyBoundedGate()
    coa = CourseOfAction(target_coordinates=(0.0, 0.0), tier=ActionTier.TIER_0_AUTONOMOUS)
    ok, reason = gate.verify_deterministic_interlocks(coa)
    assert ok is False
    assert reason is not None


def test_geofence_reject() -> None:
    interlock = DeterministicInterlock(
        forbidden_zones=[
            {
                "name": "box",
                "polygon": [
                    [1.0, 100.0],
                    [1.0, 101.0],
                    [2.0, 101.0],
                    [2.0, 100.0],
                    [1.0, 100.0],
                ],
            }
        ]
    )
    assert point_in_polygon(1.5, 100.5, [tuple(p) for p in interlock.forbidden_zones[0]["polygon"]])
    coa = CourseOfAction(target_coordinates=(1.5, 100.5), tier=ActionTier.TIER_1_HITL)
    ok, reason = interlock.verify(coa)
    assert ok is False
    assert "Geofence" in (reason or "")


@pytest.mark.asyncio
async def test_tier0_auto_approve() -> None:
    gate = LatencyBoundedGate()
    coa = CourseOfAction(
        target_coordinates=(1.2, 103.8),
        tier=ActionTier.TIER_0_AUTONOMOUS,
    )
    verdict, token = await gate.evaluate(coa, None)
    assert verdict == GateVerdict.APPROVED
    assert token.verdict == GateVerdict.APPROVED.value


@pytest.mark.asyncio
async def test_hitl_approve() -> None:
    gate = LatencyBoundedGate(timeout_sec=2.0)
    coa = CourseOfAction(target_coordinates=(1.2, 103.8), tier=ActionTier.TIER_1_HITL)
    q: asyncio.Queue[str] = asyncio.Queue()
    await q.put("y")
    verdict, _ = await gate.evaluate(coa, q)
    assert verdict == GateVerdict.APPROVED


@pytest.mark.asyncio
async def test_hitl_deny() -> None:
    gate = LatencyBoundedGate(timeout_sec=2.0)
    coa = CourseOfAction(target_coordinates=(1.2, 103.8), tier=ActionTier.TIER_1_HITL)
    q: asyncio.Queue[str] = asyncio.Queue()
    await q.put("n")
    verdict, _ = await gate.evaluate(coa, q)
    assert verdict == GateVerdict.REJECTED_OPERATOR


@pytest.mark.asyncio
async def test_timeout_station_keep_verdict() -> None:
    gate = LatencyBoundedGate(timeout_sec=0.2)
    coa = CourseOfAction(
        target_coordinates=(1.2, 103.8),
        tier=ActionTier.TIER_1_HITL,
        timeout_seconds=0.2,
    )
    q: asyncio.Queue[str] = asyncio.Queue()
    verdict, token = await gate.evaluate(coa, q)
    assert verdict == GateVerdict.TIMED_OUT_FALLBACK
    assert token.reason == "latency_timeout"


@pytest.mark.asyncio
async def test_stub_dispatch() -> None:
    stub = StubEffector()
    coa = CourseOfAction(target_coordinates=(1.1, 103.9), intent="INSPECT_TARGET")
    receipt = await stub.dispatch(coa)
    assert receipt.status == "ACCEPTED"
    assert len(stub.dispatched) == 1
    keep = await stub.emergency_station_keep()
    assert keep.status == "STATION_KEEP"
    assert stub.station_keeps == 1
