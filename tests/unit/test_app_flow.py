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
