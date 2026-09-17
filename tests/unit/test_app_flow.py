"""App mock server / kinematics / C2 cycle smoke tests."""

from __future__ import annotations

import pytest
from app.adapters.kinematics_sim import KinematicsSim
from app.mock_server import app as mock_app
from core.coa import GateVerdict
from fastapi.testclient import TestClient


def test_mock_navigate_accepts_waypoint() -> None:
    client = TestClient(mock_app)
    resp = client.post(
        "/api/v1/navigate",
        json={"latitude": 1.24, "longitude": 103.86, "speed_kt": 4.0, "mission_id": "t1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    tel = client.get("/api/v1/telemetry")
    assert tel.status_code == 200
    assert tel.json()["mode"] == "navigating"
    stop = client.post("/api/v1/emergency_stop")
    assert stop.json()["status"] == "station_keep"


def test_kinematics_moves_toward_waypoint() -> None:
    sim = KinematicsSim(latitude=1.23, longitude=103.85, speed_mps=50.0)
    sim.set_waypoint(1.231, 103.851)
    path = sim.run_until_arrival(max_steps=200, dt_sec=1.0)
    assert len(path) > 1
    assert abs(sim.latitude - 1.231) < 1e-4
    assert abs(sim.longitude - 103.851) < 1e-4


@pytest.mark.asyncio
async def test_usv_rest_dispatch_and_station_keep(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from app.adapters import usv_rest
    from app.adapters.usv_rest import UsvRestAdapter
    from core.coa import ActionTier, CourseOfAction

    transport = httpx.ASGITransport(app=mock_app)

    class _AsgiClient(httpx.AsyncClient):
        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs["transport"] = transport
            kwargs.setdefault("base_url", "http://testserver")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(usv_rest.httpx, "AsyncClient", _AsgiClient)

    adapter = UsvRestAdapter(endpoint="http://testserver")
    coa = CourseOfAction(
        coa_id="coa-test-1",
        intent="ISR_IDENTIFY_CONTACT",
        tier=ActionTier.TIER_1_HITL,
        target_coordinates=(1.24, 103.86),
        timeout_seconds=5.0,
    )
    receipt = await adapter.dispatch(coa)
    assert receipt.status == "DISPATCHED"
    assert receipt.message == "navigate_accepted"
    tel = await adapter.telemetry()
    assert tel["mode"] == "navigating"
    keep = await adapter.emergency_station_keep()
    assert keep.status == "STATION_KEEP"


def test_resolve_effector_base_url_prefers_effector_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adapters.usv_rest import resolve_effector_base_url

    monkeypatch.delenv("EFFECTOR_BASE_URL", raising=False)
    monkeypatch.delenv("CLEARBOT_BASE_URL", raising=False)
    assert resolve_effector_base_url() == "http://127.0.0.1:8000"

    monkeypatch.setenv("CLEARBOT_BASE_URL", "http://legacy:9000")
    assert resolve_effector_base_url() == "http://legacy:9000"

    monkeypatch.setenv("EFFECTOR_BASE_URL", "http://effector:8000")
    assert resolve_effector_base_url() == "http://effector:8000"
    assert resolve_effector_base_url("http://explicit:1") == "http://explicit:1"


def test_clearbot_adapter_is_usv_alias() -> None:
    from app.adapters.clearbot_rest import ClearbotRestAdapter
    from app.adapters.usv_rest import UsvRestAdapter

    assert ClearbotRestAdapter is UsvRestAdapter


@pytest.mark.asyncio
async def test_c2_cycle_stub_approve() -> None:
    from app.main import run_c2_cycle

    verdict = await run_c2_cycle(
        scenario_id="S1",
        auto_decision="y",
        use_stub=True,
        gate_timeout_sec=2.0,
    )
    assert verdict == GateVerdict.APPROVED


@pytest.mark.asyncio
async def test_c2_cycle_stub_timeout() -> None:
    import app.main as main_mod
    from app.main import run_c2_cycle

    async def silent_prompt(**kwargs):  # type: ignore[no-untyped-def]
        return None

    original = main_mod.prompt_operator_decision
    main_mod.prompt_operator_decision = silent_prompt  # type: ignore[assignment]
    try:
        verdict = await run_c2_cycle(
            scenario_id="S1",
            auto_decision=None,
            use_stub=True,
            gate_timeout_sec=0.3,
        )
        assert verdict == GateVerdict.TIMED_OUT_FALLBACK
    finally:
        main_mod.prompt_operator_decision = original
