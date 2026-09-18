"""Pitch-2: probabilistic interpreter proposes; deterministic gate disposes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app import c2_server
from app.adapters.southbound_sensor import normalize_sensor_event
from app.c2_server import app
from app.llm_interpreter import (
    heuristic_interpret,
    interpret,
    llm_configured,
    llm_interpret,
)
from app.scenarios.base import Finding, get_scenario
from core.coa import ActionTier, CourseOfAction
from core.ontology import SpatialEntityGraph
from fastapi.testclient import TestClient


def _s2_graph_and_finding() -> tuple[SpatialEntityGraph, Finding]:
    scenario = get_scenario("S2")
    graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    graph.ingest_many([normalize_sensor_event(e) for e in scenario.build_events()])
    finding = scenario.detect(graph)
    assert finding is not None
    return graph, finding


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    audit = tmp_path / "gate.jsonl"
    c2_server._runtime = c2_server.C2Runtime(audit_path=audit)
    with TestClient(app) as c:
        yield c


def test_llm_configured_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert llm_configured() is False
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9999/v1")
    assert llm_configured() is True


def test_heuristic_interpret_s2_hypotheses() -> None:
    graph, finding = _s2_graph_and_finding()
    result = heuristic_interpret(graph, finding, timeout_seconds=5.0)
    assert result.source == "heuristic"
    assert result.confidence == finding.confidence
    assert len(result.hypotheses) >= 2
    labels = {h.label for h in result.hypotheses}
    assert "sensor_contradiction" in labels
    assert result.candidate_coa.intent == "CUE_AND_IDENTIFY"
    assert result.candidate_coa.tier == ActionTier.TIER_1_HITL
    assert result.candidate_coa.metadata.get("interpreter") == "heuristic"


def test_interpret_falls_back_without_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    graph, finding = _s2_graph_and_finding()
    result = interpret(graph, finding)
    assert result.source == "heuristic"
    assert result.error is None


def test_interpret_falls_back_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("LLM_TIMEOUT_S", "0.05")
    graph, finding = _s2_graph_and_finding()
    result = interpret(graph, finding)
    assert result.source == "heuristic"
    assert result.error is not None
    assert result.error.startswith("llm_failed:")
    assert result.candidate_coa.intent == "CUE_AND_IDENTIFY"


def test_llm_interpret_parses_structured_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    payload = {
        "hypotheses": [
            {
                "label": "count_mismatch",
                "claim": "Social claims 3; radar sees 1",
                "confidence": 0.82,
                "supports_threat": True,
                "modality_hints": ["social", "radar"],
            }
        ],
        "confidence": 0.8,
        "intent": "CUE_AND_IDENTIFY",
        "picture_summary": "LLM picture",
        "adversarial_hypothesis": "If social is false, swarm collapses",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://llm.test/v1/chat/completions"
        assert request.headers.get("authorization") == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    transport = httpx.MockTransport(handler)
    graph, finding = _s2_graph_and_finding()
    with pytest.MonkeyPatch.context() as mp:
        # Ensure Client uses our transport by patching the class constructor default
        real_client = httpx.Client

        def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        mp.setattr("app.llm_interpreter.httpx.Client", client_factory)
        result = llm_interpret(graph, finding, timeout_seconds=5.0)

    assert result.source == "llm"
    assert result.model == "test-model"
    assert result.hypotheses[0].label == "count_mismatch"
    assert result.candidate_coa.intent == "CUE_AND_IDENTIFY"
    assert result.picture_summary == "LLM picture"


def test_llm_interpret_sends_gemini_38_flash_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live smoke/tests pin Gemini 3.8 Flash via LLM_MODEL (LiteLLM alias)."""
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-litellm-local")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.8-flash")

    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "hypotheses": [
                                        {
                                            "label": "count_mismatch",
                                            "claim": "3 vs 1",
                                            "confidence": 0.8,
                                            "supports_threat": True,
                                            "modality_hints": ["social"],
                                        }
                                    ],
                                    "confidence": 0.8,
                                    "intent": "CUE_AND_IDENTIFY",
                                    "picture_summary": "gemini",
                                    "adversarial_hypothesis": "if social is false",
                                }
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    graph, finding = _s2_graph_and_finding()
    real_client = httpx.Client

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.llm_interpreter.httpx.Client", client_factory)
        result = llm_interpret(graph, finding, timeout_seconds=5.0)

    assert seen["body"]["model"] == "gemini-3.8-flash"
    assert result.source == "llm"
    assert result.model == "gemini-3.8-flash"


def test_api_interpret_heuristic(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    resp = client.post(
        "/api/interpret",
        json={"scenario_id": "S2", "force_heuristic": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "INTERPRETED"
    assert body["source"] == "heuristic"
    assert body["hypotheses"]
    assert body["candidate_coa"]["intent"] == "CUE_AND_IDENTIFY"
    assert body["finding"]["amber_alert"] == "COUNT_AND_BEARING_MISMATCH"
    # Interpreter must not seal a DecisionToken
    assert "token" not in body


def test_interpreter_coa_still_gate_denied(client: TestClient) -> None:
    """LLM/heuristic propose → gate can still REJECTED_FAST (geofence)."""
    interpreted = client.post(
        "/api/interpret",
        json={"scenario_id": "S2", "force_heuristic": True},
    )
    assert interpreted.status_code == 200
    coa = interpreted.json()["candidate_coa"]
    # Poison coordinates into the demo no-go zone
    coa["target_coordinates"] = [1.2310, 103.8510]
    coa["speed_kt"] = 5.0

    denied = client.post(
        "/api/gate/proposals",
        json={"coa": coa, "unit_id": "CUE-NODE-01"},
    )
    assert denied.status_code == 200
    body = denied.json()
    assert body["status"] == "REJECTED_FAST"
    assert "Geofence" in (body.get("reason") or "")
    assert body["token"]["verdict"] == "REJECTED_FAST"
    assert body["token"]["digest"]


def test_proposals_with_interpret_flag(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    resp = client.post(
        "/api/gate/proposals",
        json={
            "scenario_id": "S2",
            "unit_id": "CUE-NODE-01",
            "interpret": True,
            "force_heuristic": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "QUEUED"
    assert body["interpreter_source"] == "heuristic"
    assert body["hypotheses"]
    assert body["coa"]["intent"] == "CUE_AND_IDENTIFY"


def test_llm_interpret_http_error_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    graph, finding = _s2_graph_and_finding()
    real_client = httpx.Client

    def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.llm_interpreter.httpx.Client", client_factory)
        with pytest.raises(httpx.HTTPStatusError):
            llm_interpret(
                graph,
                finding,
                base_url="http://x/v1",
                api_key="",
                model="m",
                http_timeout_s=1.0,
            )


def test_raw_coa_from_interpreter_is_course_of_action() -> None:
    graph, finding = _s2_graph_and_finding()
    result = heuristic_interpret(graph, finding)
    assert isinstance(result.candidate_coa, CourseOfAction)
