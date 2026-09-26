"""Integration: lead-pursuit POI appears on gated S2/S3 proposals (issue #58)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import app as c2_app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture()
def c2_client(tmp_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "poi_gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


@pytest.mark.parametrize(
    ("scenario_id", "unit_id", "intent"),
    [
        ("S2_osint_swarm", "CUE-NODE-01", "CUE_AND_IDENTIFY"),
        ("S3_sar_ais", "USV-02", "APPROACH_PATROL"),
    ],
)
def test_proposal_includes_lead_pursuit_poi(
    c2_client: TestClient,
    scenario_id: str,
    unit_id: str,
    intent: str,
) -> None:
    """Propose → COA carries POI waypoint + ETA; approve → inbox keeps them."""
    c2_client.post("/api/admin/reset")
    propose = c2_client.post(
        "/api/gate/proposals",
        json={"scenario_id": scenario_id, "unit_id": unit_id},
    )
    assert propose.status_code == 200, propose.text
    body = propose.json()
    coa = body["coa"]
    assert coa["intent"] == intent
    assert "poi" in coa["metadata"]
    poi = coa["metadata"]["poi"]
    assert poi["method"] in {"collision_course", "lead_along_track", "static_contact"}
    assert poi["eta_sec"] > 0.0
    assert coa["metadata"]["eta_sec"] == poi["eta_sec"]
    assert coa["target_coordinates"][0] == pytest.approx(poi["latitude"])
    assert coa["target_coordinates"][1] == pytest.approx(poi["longitude"])
    assert "contact_coordinates" in coa["metadata"]

    approve = c2_client.post(
        "/api/gate/approve",
        json={
            "coa_id": coa["coa_id"],
            "decision": "y",
            "operator_id": "e2e-poi",
        },
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    inbox = c2_client.get("/api/recipient/inbox", params={"unit_id": unit_id})
    assert inbox.status_code == 200
    taskings = inbox.json()["taskings"]
    assert len(taskings) >= 1
    task_coa = taskings[0]["coa"]
    assert task_coa["metadata"]["poi"]["eta_sec"] == poi["eta_sec"]
    assert task_coa["target_coordinates"] == coa["target_coordinates"]


def test_s1_proposal_has_no_poi(c2_client: TestClient) -> None:
    c2_client.post("/api/admin/reset")
    propose = c2_client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S1_ais_spoof", "unit_id": "ISR-NODE-01"},
    )
    assert propose.status_code == 200
    meta = propose.json()["coa"]["metadata"]
    assert "poi" not in meta
    assert "eta_sec" not in meta


def test_verify_ui_s3_renders_lead_poi_card(c2_client: TestClient) -> None:
    """REST POI metadata surfaces as Lead POI card on /verify Screen 1 (#58/#77)."""
    c2_client.post("/api/admin/reset")
    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S3_sar_ais", "unit_id": "USV-02"},
    )
    assert proposed.status_code == 200
    assert b"Lead POI" in proposed.content
    assert b"Bearing" in proposed.content
    assert b"Speed" in proposed.content
    assert b"ETA" in proposed.content
    assert b"poi-card" in proposed.content
