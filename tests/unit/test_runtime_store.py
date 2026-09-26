"""SQLite runtime picture survives process restart; reset clears it."""

from __future__ import annotations

from pathlib import Path

from app import c2_server
from app.c2_server import C2Runtime, app
from fastapi.testclient import TestClient


def _runtime(tmp_path: Path) -> C2Runtime:
    return C2Runtime(
        audit_path=tmp_path / "gate.jsonl",
        ingress_replay_path=tmp_path / "ingress.jsonl",
        runtime_db_path=tmp_path / "runtime.sqlite",
    )


def test_runtime_picture_survives_restart(tmp_path: Path) -> None:
    first = _runtime(tmp_path)
    c2_server._runtime = first
    with TestClient(app) as client:
        proposed = client.post(
            "/api/gate/proposals",
            json={"scenario_id": "S3_sar_ais", "unit_id": "CUE-NODE-01"},
        )
        assert proposed.status_code == 200
        body = proposed.json()
        assert body["status"] == "QUEUED"
        coa_id = body["coa"]["coa_id"]
        assert body["finding"]["amber_alert"] == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"

        state = client.get("/api/ontology/state").json()
        assert len(state["tracks"]) >= 1
        assert coa_id in state["pending_proposals"]
        track_count = len(state["tracks"])
        obs_count = len(state["observations"])

        approved = client.post(
            "/api/gate/approve",
            json={"coa_id": coa_id, "decision": "y", "operator_id": "sqlite-test"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"

    # New process-equivalent: fresh C2Runtime on the same SQLite file.
    second = _runtime(tmp_path)
    c2_server._runtime = second
    with TestClient(app) as client:
        state = client.get("/api/ontology/state").json()
        assert len(state["tracks"]) == track_count
        assert len(state["observations"]) == obs_count
        assert state["amber_alert"]["alert"] == "SAR_DARK_CLUSTER_VS_AIS_SILENCE"
        assert coa_id not in state["pending_proposals"]

        inbox = client.get("/api/recipient/inbox", params={"unit_id": "CUE-NODE-01"}).json()
        assert inbox["count"] == 1
        assert inbox["taskings"][0]["coa"]["coa_id"] == coa_id


def test_admin_reset_clears_sqlite_picture(tmp_path: Path) -> None:
    first = _runtime(tmp_path)
    c2_server._runtime = first
    with TestClient(app) as client:
        proposed = client.post(
            "/api/gate/proposals",
            json={"scenario_id": "S2_osint_swarm", "unit_id": "CUE-NODE-01"},
        )
        assert proposed.status_code == 200
        assert client.post("/api/admin/reset").status_code == 200
        empty = client.get("/api/ontology/state").json()
        assert empty["tracks"] == []
        assert empty["pending_proposals"] == []
        assert empty["amber_alert"] is None

    second = _runtime(tmp_path)
    c2_server._runtime = second
    with TestClient(app) as client:
        state = client.get("/api/ontology/state").json()
        assert state["tracks"] == []
        assert state["observations"] == []
        assert state["pending_proposals"] == []
        assert state["amber_alert"] is None
