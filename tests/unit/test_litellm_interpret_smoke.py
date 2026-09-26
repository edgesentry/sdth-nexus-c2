"""LiteLLM interpret smoke client (issue #32) — no live LLM in CI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_smoke() -> ModuleType:
    path = ROOT / "scripts" / "litellm_interpret_smoke.py"
    spec = importlib.util.spec_from_file_location("litellm_interpret_smoke", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_evaluate_accepts_live_llm_payload() -> None:
    smoke = _load_smoke()
    ok, detail = smoke.evaluate_interpret_response(
        {
            "status": "INTERPRETED",
            "source": "llm",
            "model": "gemini-3.8-flash",
            "hypotheses": [{"label": "sensor_contradiction", "claim": "3 vs 1"}],
            "candidate_coa": {"intent": "GNSS_DENIAL_AND_GBAD_CUE"},
        }
    )
    assert ok is True
    assert "source=llm" in detail


def test_evaluate_rejects_heuristic_fallback() -> None:
    smoke = _load_smoke()
    ok, detail = smoke.evaluate_interpret_response(
        {
            "status": "INTERPRETED",
            "source": "heuristic",
            "error": "llm_failed:ConnectError:…",
            "hypotheses": [{"label": "sensor_contradiction"}],
        }
    )
    assert ok is False
    assert "source=llm" in detail


def test_evaluate_rejects_empty_hypotheses_and_token() -> None:
    smoke = _load_smoke()
    ok, _ = smoke.evaluate_interpret_response(
        {"status": "INTERPRETED", "source": "llm", "hypotheses": []}
    )
    assert ok is False
    ok, detail = smoke.evaluate_interpret_response(
        {
            "status": "INTERPRETED",
            "source": "llm",
            "hypotheses": [{"label": "x"}],
            "token": {"digest": "abc"},
        }
    )
    assert ok is False
    assert "DecisionToken" in detail


def test_evaluate_rejects_non_interpreted_status() -> None:
    smoke = _load_smoke()
    ok, detail = smoke.evaluate_interpret_response({"status": "QUEUED", "source": "llm"})
    assert ok is False
    assert "INTERPRETED" in detail


def test_smoke_fails_when_core_down(monkeypatch: pytest.MonkeyPatch) -> None:
    smoke = _load_smoke()
    monkeypatch.setenv("C2_BASE_URL", "http://127.0.0.1:1")
    code = smoke.run_smoke(
        base_url="http://127.0.0.1:1",
        scenario_id="S2_osint_swarm",
        timeout_s=0.05,
    )
    assert code == 2
