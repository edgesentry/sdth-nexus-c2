"""Integration tests: OSINT text parser → S2 Warning Picture → gate (#59)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app import c2_server
from app.adapters.osint_text import parse_osint_text
from app.adapters.southbound_sensor import normalize_sensor_event
from app.c2_server import app as c2_app
from app.scenarios.base import get_scenario
from app.scenarios.s2_air_corridor_attritable import _INTEL_TEXT
from core.ontology import SpatialEntityGraph
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture()
def c2_client(tmp_path: Path) -> Iterator[TestClient]:
    c2_server._runtime = c2_server.C2Runtime(audit_path=tmp_path / "osint_gate.jsonl")
    with TestClient(c2_app) as client:
        yield client


def test_osint_parser_feeds_s2_gate_proposal(c2_client: TestClient) -> None:
    """S2 propose uses OSINT-parsed claimed_count=3 from intel_text."""
    parsed = parse_osint_text(_INTEL_TEXT)
    assert parsed.claimed_count == 3
    assert "filtered_estimate" in parsed.notes

    proposed = c2_client.post(
        "/api/gate/proposals",
        json={"scenario_id": "S2_osint_swarm", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    body = proposed.json()
    finding = body["finding"]
    social = finding["source_breakdown"]["social"]

    assert finding["amber_alert"] == "COUNT_AND_BEARING_MISMATCH"
    assert social["claimed_count"] == 3
    assert "intel_text" in social
    assert "filtered OSINT estimate" in social["intel_text"] or "3" in social["intel_text"]
    assert body["coa"]["intent"] == "CUE_AND_IDENTIFY"

    coa_id = body["coa"]["coa_id"]
    approved = c2_client.post(
        "/api/gate/approve",
        json={"coa_id": coa_id, "decision": "y", "operator_id": "osint-ci"},
    )
    assert approved.json()["status"] == "APPROVED"

    inbox = c2_client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"}).json()
    assert inbox["count"] == 1

    ack = c2_client.post(
        "/api/recipient/ack",
        json={"coa_id": coa_id, "unit_id": "CUE-NODE-01", "message": "osint e2e"},
    )
    assert ack.json()["status"] == "ACKED"


def test_osint_fallback_when_intel_unparseable() -> None:
    """Detector still gets claimed_count via fallback when text has no number."""
    scenario = get_scenario("S2_osint_swarm")
    events = scenario.build_events()
    social = next(e for e in events if e.get("modality") == "social")
    # Strip structured count; leave unparseable rumor text.
    social = dict(social)
    social.pop("claimed_count", None)
    social["intel_text"] = "Telegram chatter: many drones over the coast - unverified."
    social.pop("osint_parse_notes", None)
    events = [social if e.get("modality") == "social" else e for e in events]

    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in events])
    finding = scenario.detect(graph)
    assert finding is not None
    assert finding.amber_alert == "COUNT_AND_BEARING_MISMATCH"
    assert finding.source_breakdown["social"]["claimed_count"] == 3


def test_osint_s2_verify_ui_propose_approve_ack(c2_client: TestClient) -> None:
    """Screen 1/2 harness: Propose S2 → Approve → Ack with OSINT-backed amber (#59/#77)."""
    proposed = c2_client.post(
        "/verify/command/propose",
        data={"scenario_id": "S2_osint_swarm", "unit_id": "CUE-NODE-01"},
    )
    assert proposed.status_code == 200
    assert b"COUNT_AND_BEARING_MISMATCH" in proposed.content
    assert b"Queued" in proposed.content
    assert b"OSINT: 3 UAVs (Telegram)" in proposed.content
    assert b"Radar: 1 Contact" in proposed.content
    assert b"OCSF Hash Chain: broken links" in proposed.content

    body = proposed.text
    marker = 'name="coa_id" value="'
    assert marker in body
    coa_id = body.split(marker, 1)[1].split('"', 1)[0]

    approved = c2_client.post(
        "/verify/command/approve",
        data={
            "coa_id": coa_id,
            "decision": "y",
            "unit_id": "CUE-NODE-01",
            "scenario_id": "S2_osint_swarm",
        },
    )
    assert approved.status_code == 200
    assert b"APPROVED" in approved.content
    assert b"OCSF Hash Chain: broken links" in approved.content

    inbox = c2_client.get("/verify/recipient", params={"unit_id": "CUE-NODE-01"})
    assert inbox.status_code == 200
    assert coa_id.encode() in inbox.content
    assert b"CUE_AND_IDENTIFY" in inbox.content or b"PENDING_ACK" in inbox.content
    assert b"OCSF Hash Chain: broken links" in inbox.content

    acked = c2_client.post(
        "/verify/recipient/ack",
        data={"coa_id": coa_id, "unit_id": "CUE-NODE-01"},
    )
    assert acked.status_code == 200
    assert b"Ack" in acked.content
