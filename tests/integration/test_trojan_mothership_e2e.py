"""End-to-end Trojan mothership path: JSONL → detect → Verify UI (issue #116)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import C2Runtime, app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    c2_server._runtime = C2Runtime(
        audit_path=tmp_path / "gate.jsonl",
        runtime_db_path=tmp_path / "runtime.sqlite",
    )
    with TestClient(app) as c:
        yield c


def test_trojan_propose_shows_amber_and_claim_tags(client: TestClient) -> None:
    resp = client.post(
        "/verify/command/propose",
        data={"scenario_id": "s1_trojan", "unit_id": "GBAD-RSAF-01", "service_view": "nexus"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "VELOCITY_MISMATCH" in body
    assert "claim-tags" in body or "claim-tag" in body
    assert "AIS:" in body
    assert "Radar:" in body
    assert "HAPPY TUG" in body.upper() or "Happy Tug" in body or "6.1" in body


def test_navy_silo_shows_happy_tug_ais(client: TestClient) -> None:
    proposed = client.post(
        "/verify/command/propose",
        data={"scenario_id": "s1_trojan", "unit_id": "GBAD-RSAF-01", "service_view": "navy"},
    )
    assert proposed.status_code == 200
    # After propose, ontology is populated; request navy silo view
    navy = client.get(
        "/verify/command",
        params={"scenario_id": "s1_trojan", "unit_id": "GBAD-RSAF-01", "service_view": "navy"},
    )
    assert navy.status_code == 200
    text = navy.text
    assert "service=NAVY" in text or "NAVY" in text
    assert "HAPPY TUG" in text.upper() or "MPA_OCEANS" in text or "563098710" in text


def test_guardrail_panel_veto_and_option_b(client: TestClient) -> None:
    resp = client.post(
        "/verify/command/guardrail",
        data={
            "scenario_id": "s1_trojan",
            "unit_id": "GBAD-RSAF-01",
            "navy_unit_id": "PCG-PT-44",
            "service_view": "nexus",
        },
    )
    assert resp.status_code == 200
    text = resp.text
    assert "SAFETY_LOCKOUT_CNI_FALLOUT_HAZARD" in text
    assert "OFFSHORE_INTERCEPT_RF_SOFTKILL" in text or "Option B" in text
    assert "AUTHORIZE Option B" in text


def test_scenario_select_includes_s1_trojan(client: TestClient) -> None:
    cmd = client.get("/verify/command", params={"scenario_id": "s1_trojan"})
    assert cmd.status_code == 200
    assert b"s1_trojan" in cmd.content
    assert b"Service silo" in cmd.content or b"service_view" in cmd.content


def test_arun_reload_ingress(client: TestClient) -> None:
    resp = client.post(
        "/verify/command/ingress",
        data={
            "mode": "arun_reload",
            "unit_id": "GBAD-RSAF-01",
            "scenario_id": "s1_trojan",
            "service_view": "navy",
        },
    )
    assert resp.status_code == 200
    assert b"Arun canonical reload" in resp.content
    assert b"ingested" in resp.content
