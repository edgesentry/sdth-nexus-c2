"""Integration: /verify WebUI Phase 4 cards & badges (issue #77)."""

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
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "verify77_gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


def _coa_id_from_html(body: str) -> str:
    marker = 'name="coa_id" value="'
    assert marker in body
    return body.split(marker, 1)[1].split('"', 1)[0]


def test_verify_ui_ocsf_health_pill_path_f(c2_client: TestClient) -> None:
    """OCSF hash-chain pill stays 100% Verified across Propose → Approve → Ack."""
    c2_client.post("/api/admin/reset")

    hub = c2_client.get("/verify")
    assert hub.status_code == 200
    assert b"OCSF Hash Chain" in hub.content
    assert b"100% Verified" in hub.content
    assert b"records sealed" in hub.content

    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"OCSF Hash Chain: 100% Verified" in proposed.content
    assert b"records sealed" in proposed.content
    coa_id = _coa_id_from_html(proposed.text)

    approved = c2_client.post(
        "/verify/command/approve",
        data={
            "coa_id": coa_id,
            "decision": "y",
            "unit_id": "CUE-NODE-01",
            "scenario_id": "S2",
        },
    )
    assert approved.status_code == 200
    assert b"APPROVED" in approved.content
    assert b"OCSF Hash Chain: 100% Verified" in approved.content

    inbox = c2_client.get("/verify/recipient", params={"unit_id": "CUE-NODE-01"})
    assert inbox.status_code == 200
    assert b"OCSF Hash Chain: 100% Verified" in inbox.content
    assert coa_id.encode() in inbox.content

    acked = c2_client.post(
        "/verify/recipient/ack",
        data={"coa_id": coa_id, "unit_id": "CUE-NODE-01"},
    )
    assert acked.status_code == 200
    assert b"Ack" in acked.content
    assert b"OCSF Hash Chain: 100% Verified" in acked.content


def test_verify_ui_osint_claim_badges_s2(c2_client: TestClient) -> None:
    """S2 Warning Picture renders OSINT vs Radar comparison tags with amber."""
    c2_client.post("/api/admin/reset")
    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"COUNT_AND_BEARING_MISMATCH" in proposed.content
    assert b"OSINT: 3 UAVs (Telegram)" in proposed.content
    assert b"Radar: 1 Contact" in proposed.content
    assert b"claim-tags" in proposed.content
    assert b'class="panel amber"' in proposed.content or b"panel amber" in proposed.content


def test_verify_ui_lead_poi_card_s3(c2_client: TestClient) -> None:
    """S3 propose elevates Lead POI card (lat/lon/bearing/speed/ETA)."""
    c2_client.post("/api/admin/reset")
    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S3", "unit_id": "USV-02"},
    )
    assert proposed.status_code == 200
    assert b"Lead POI" in proposed.content
    assert b"poi-card" in proposed.content
    assert b"Bearing" in proposed.content
    assert b"Speed" in proposed.content
    assert b"ETA" in proposed.content
    assert b"m/s" in proposed.content
    # Formatted lat/lon appear as four-decimal degrees
    body = proposed.text
    assert "Lat" in body and "Lon" in body
    assert any(token for token in body.split() if token.replace(".", "", 1).isdigit() and "." in token)


def test_verify_ui_lead_poi_card_also_on_s2(c2_client: TestClient) -> None:
    """S2 CUE_AND_IDENTIFY also surfaces Lead POI when metadata.poi is present."""
    c2_client.post("/api/admin/reset")
    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"Lead POI" in proposed.content
    assert b"poi-card" in proposed.content
    assert b"OCSF Hash Chain: 100% Verified" in proposed.content
    assert b"OSINT: 3 UAVs (Telegram)" in proposed.content
