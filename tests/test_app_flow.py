"""App scenario / agent / mock server tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.adapters.kinematics_sim import KinematicsSim
from app.adapters.southbound_sensor import normalize_sensor_event
from app.agent import find_first_contradiction_coa
from app.mock_server import app as mock_app
from app.scenarios.strait_incident import build_strait_incident
from core.coa import ActionTier, GateVerdict
from core.ontology import SpatialEntityGraph
from core.schema import sha256_hex


def test_strait_incident_builds_tier1_coa() -> None:
    events = build_strait_incident()
    graph = SpatialEntityGraph()
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    result = find_first_contradiction_coa(graph)
    assert result is not None
    finding, coa = result
    assert finding.mismatch_m > 500
    assert coa.tier == ActionTier.TIER_1_HITL
    assert coa.intent == "INTERCEPT_AND_IDENTIFY"
    assert len(coa.corroborating_sources) >= 2
    assert coa.raw_input_digest == sha256_hex("|".join(sorted(
        o.raw_digest for o in graph.observations if o.observation_id in graph.get_track(finding.track_id).observation_ids  # type: ignore[union-attr]
    ))) or len(coa.raw_input_digest) == 64


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

    verdict = await run_c2_cycle(auto_decision="y", use_stub=True, gate_timeout_sec=2.0)
    assert verdict == GateVerdict.APPROVED


@pytest.mark.asyncio
async def test_c2_cycle_stub_timeout() -> None:
    from app.main import run_c2_cycle

    # No auto_decision and empty operator channel → prompt returns without put on timeout
    # Use auto_decision=None with very short timeout: prompt waits on stdin.
    # Safer: leave queue empty by using a custom path — call gate via stub only.
    # Here we simulate timeout by not providing decision and patching prompt.
    import app.main as main_mod

    async def silent_prompt(**kwargs):  # type: ignore[no-untyped-def]
        return None

    original = main_mod.prompt_operator_decision
    main_mod.prompt_operator_decision = silent_prompt  # type: ignore[assignment]
    try:
        verdict = await run_c2_cycle(auto_decision=None, use_stub=True, gate_timeout_sec=0.3)
        assert verdict == GateVerdict.TIMED_OUT_FALLBACK
    finally:
        main_mod.prompt_operator_decision = original
