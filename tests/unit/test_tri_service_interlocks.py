"""Tri-service CNI debris interlock + Option B failsafe (issue #116)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.adapters.arun_canonical import load_pois
from app.c2_server import C2Runtime, _build_option_b_fallback, _load_scenario, app
from core.coa import ActionTier, CourseOfAction
from core.gate import LatencyBoundedGate
from core.interlock import CNI_FALLOUT_CODE, DeterministicInterlock, debris_footprint_radius_m
from fastapi.testclient import TestClient


@pytest.fixture()
def runtime(tmp_path: Path) -> C2Runtime:
    return C2Runtime(
        audit_path=tmp_path / "gate.jsonl",
        runtime_db_path=tmp_path / "runtime.sqlite",
    )


def test_cni_debris_vetoes_terminal_over_jurong(runtime: C2Runtime) -> None:
    pois = load_pois()
    runtime.policy.interlock.set_cni_pois(pois)
    poi01 = next(p for p in pois if p["poi_id"] == "POI-01")
    coa = CourseOfAction(
        intent="TERMINAL_SAM_INTERCEPT",
        tier=ActionTier.TIER_1_HITL,
        target_entity_id="UAS-001",
        target_coordinates=(float(poi01["center_lat"]), float(poi01["center_lon"])),
        metadata={"dangerous_proposal_draft": True, "altitude_m": 71.0},
    )
    ok, reason = LatencyBoundedGate(interlock=runtime.policy.interlock).verify_deterministic_interlocks(
        coa
    )
    assert ok is False
    assert reason is not None
    assert CNI_FALLOUT_CODE in reason
    assert "Jurong" in reason


def test_offshore_option_b_clears_cni_gate(runtime: C2Runtime) -> None:
    pois = load_pois()
    runtime.policy.interlock.set_cni_pois(pois)
    dangerous = _load_scenario(runtime, "s1_trojan", 5.0)
    fallback = _build_option_b_fallback(dangerous, runtime.finding)
    ok, reason = LatencyBoundedGate(interlock=runtime.policy.interlock).verify_deterministic_interlocks(
        fallback
    )
    assert ok is True
    assert reason is None
    assert fallback.intent == "OFFSHORE_INTERCEPT_RF_SOFTKILL"
    assert fallback.metadata.get("option_id") == "B"


def test_military_poi_does_not_hard_veto_alone() -> None:
    """Debris lockout is civilian CNI; military POIs are ETA-only."""
    interlock = DeterministicInterlock(
        cni_pois=[
            {
                "poi_id": "POI-03",
                "name": "Changi Naval Base",
                "kind": "military",
                "center_lat": 1.33,
                "center_lon": 104.02,
                "buffer_m": 1500.0,
            }
        ]
    )
    coa = CourseOfAction(
        intent="TERMINAL_SAM_INTERCEPT",
        tier=ActionTier.TIER_1_HITL,
        target_entity_id="UAS-001",
        target_coordinates=(1.33, 104.02),
        metadata={"dangerous_proposal_draft": True},
    )
    ok, reason = interlock.verify(coa)
    assert ok is True
    assert reason is None


def test_poi_eta_flags_cover_civilian_and_military(runtime: C2Runtime) -> None:
    _load_scenario(runtime, "s1_trojan", 5.0)
    assert runtime.finding is not None
    eta = runtime.finding.source_breakdown.get("poi_eta_sec") or {}
    assert "POI-01" in eta
    assert "POI-03" in eta or "POI-04" in eta
    assert all(isinstance(v, (int, float)) and v > 0 for v in eta.values())


def test_demo_evaluate_with_guardrail_api(tmp_path: Path) -> None:
    from app import c2_server

    c2_server._runtime = C2Runtime(
        audit_path=tmp_path / "gate.jsonl",
        runtime_db_path=tmp_path / "runtime.sqlite",
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/gate/demo-evaluate-with-guardrail",
            json={
                "scenario_id": "s1_trojan",
                "unit_id": "GBAD-RSAF-01",
                "navy_unit_id": "PCG-PT-44",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "GUARDRAIL_VETO_OPTION_B_QUEUED"
    assert body["veto_code"] == CNI_FALLOUT_CODE
    assert CNI_FALLOUT_CODE in body["veto_reason"]
    assert body["fallback_coa"]["intent"] == "OFFSHORE_INTERCEPT_RF_SOFTKILL"
    assert body["finding"]["amber_alert"]
    assert "VELOCITY_MISMATCH" in body["finding"]["amber_alert"]


def test_debris_footprint_scales_with_altitude() -> None:
    assert debris_footprint_radius_m(altitude_m=71.0) >= 500.0
    assert debris_footprint_radius_m(altitude_m=200.0) > debris_footprint_radius_m(altitude_m=50.0)
