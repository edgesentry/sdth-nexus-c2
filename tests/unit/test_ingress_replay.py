"""Ingress replay jsonl (issue #54) — not gate authority."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from app import c2_server
from app.c2_server import app
from core.ingress_replay import IngressReplayLog
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    ingress = tmp_path / "ingress.jsonl"
    c2_server._runtime = c2_server.C2Runtime(
        audit_path=audit,
        ingress_replay_path=ingress,
    )
    with TestClient(app) as c:
        yield c


def test_append_writes_received_at_source_payload(tmp_path: Path) -> None:
    log = IngressReplayLog(tmp_path / "ingress.jsonl")
    rec = log.append(
        source="fixture",
        endpoint="/api/ingress/candidate-event",
        payload={"use_fixture": True},
    )
    assert rec is not None
    assert "received_at" in rec
    assert rec["source"] == "fixture"
    assert rec["endpoint"] == "/api/ingress/candidate-event"
    assert rec["payload"] == {"use_fixture": True}
    assert log.records() == [rec]


def test_append_write_failure_returns_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Path is a directory → open("a") raises IsADirectoryError / OSError.
    blocked = tmp_path / "blocked_as_dir"
    blocked.mkdir()
    log = IngressReplayLog(blocked)
    with caplog.at_level(logging.WARNING, logger="core.ingress_replay"):
        rec = log.append(
            source="fixture",
            endpoint="/api/ingress/candidate-event",
            payload={"use_fixture": True},
        )
    assert rec is None
    assert "ingress replay log write failed" in caplog.text


def test_candidate_event_ingress_appends_replay_log(client: TestClient) -> None:
    resp = client.post("/api/ingress/candidate-event", json={"use_fixture": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "INGESTED"

    records = c2_server.get_runtime().ingress_replay.records()
    assert len(records) == 1
    assert records[0]["endpoint"] == "/api/ingress/candidate-event"
    assert records[0]["source"] == "fixture"
    assert records[0]["payload"]["use_fixture"] is True


def test_open_feed_ingress_appends_replay_log(client: TestClient) -> None:
    resp = client.post(
        "/api/ingress/open-feed",
        json={"feed": "ais", "use_fixture": True},
    )
    assert resp.status_code == 200
    records = c2_server.get_runtime().ingress_replay.records()
    assert len(records) == 1
    assert records[0]["endpoint"] == "/api/ingress/open-feed"
    assert records[0]["source"].startswith("open_feed:")
    assert records[0]["payload"]["feed"] == "ais"


def test_ingress_succeeds_when_replay_write_fails(client: TestClient, tmp_path: Path) -> None:
    blocked = tmp_path / "not_a_file"
    blocked.mkdir()
    c2_server.get_runtime().ingress_replay = IngressReplayLog(blocked)
    resp = client.post("/api/ingress/candidate-event", json={"use_fixture": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "INGESTED"


def test_replay_after_admin_reset_restores_observations(client: TestClient) -> None:
    """Mirrors scripts/replay_ingress.py: reset memory, re-POST stored payloads."""
    first = client.post("/api/ingress/candidate-event", json={"use_fixture": True})
    assert first.status_code == 200
    records = c2_server.get_runtime().ingress_replay.records()
    assert len(records) == 1

    reset = client.post("/api/admin/reset")
    assert reset.status_code == 200
    assert client.get("/api/ontology/state").json()["observations"] == []

    # jsonl is not wiped by reset (same contract as gate.jsonl).
    assert len(c2_server.get_runtime().ingress_replay.records()) == 1

    for rec in records:
        endpoint = str(rec["endpoint"])
        payload = rec["payload"]
        assert isinstance(payload, dict)
        resp = client.post(endpoint, json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "INGESTED"

    state = client.get("/api/ontology/state").json()
    assert len(state["observations"]) >= 1
    # Gate authority remains separate — ingest-only recovery seals no Ack.
    gate_names = {r.get("activity_name") for r in c2_server.get_runtime().audit.records()}
    assert "recipient_ack" not in gate_names


def test_join_url_tolerates_slash_variants() -> None:
    from scripts.replay_ingress import _join_url

    assert _join_url("http://127.0.0.1:8080", "/api/ingress/candidate-event") == (
        "http://127.0.0.1:8080/api/ingress/candidate-event"
    )
    assert _join_url("http://127.0.0.1:8080/", "api/ingress/candidate-event") == (
        "http://127.0.0.1:8080/api/ingress/candidate-event"
    )
    assert _join_url("http://127.0.0.1:8080/", "/api/admin/reset") == (
        "http://127.0.0.1:8080/api/admin/reset"
    )


def test_clear_truncates_ingress_log(tmp_path: Path) -> None:
    from scripts.replay_ingress import clear_log, main

    log = tmp_path / "ingress.jsonl"
    log.write_text('{"source":"fixture"}\n', encoding="utf-8")
    assert main(["--log", str(log), "--clear"]) == 0
    assert log.read_text(encoding="utf-8") == ""
    # Idempotent on missing/empty path.
    clear_log(tmp_path / "missing.jsonl")
    assert (tmp_path / "missing.jsonl").read_text(encoding="utf-8") == ""
