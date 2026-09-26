"""Probabilistic app-layer interpreter: noisy inputs → hypotheses + candidate COA.

Core (`LatencyBoundedGate`) remains the only authority that can approve / seal
DecisionTokens. This module **proposes**; it never seals.

Env:
  LLM_BASE_URL   — OpenAI-compatible base. Unset → heuristic.
                   Live path: LiteLLM at http://127.0.0.1:4000/v1 (deploy/litellm/).
  LLM_API_KEY    — Bearer token (LiteLLM master key, or empty for open local endpoints).
  LLM_MODEL      — Model id / LiteLLM alias (default: gpt-4o-mini; live smoke: gemini-3.8-flash).
  LLM_TIMEOUT_S  — HTTP timeout seconds (default: 8).
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

import httpx
from core.coa import ActionTier, CourseOfAction
from core.ontology import SpatialEntityGraph
from pydantic import BaseModel, Field

from app.scenarios.base import Finding

SourceKind = Literal["llm", "heuristic"]

_DEFAULT_INTENTS: dict[str, str] = {
    "S1_trojan": "OFFSHORE_INTERCEPT_RF_SOFTKILL",
    "S3_sar_ais": "APPROACH_PATROL",
    "S1_ais_spoof": "ISR_IDENTIFY_CONTACT",
    "S2_osint_swarm": "GNSS_DENIAL_AND_GBAD_CUE",
}


class Hypothesis(BaseModel):
    """Scored adversarial / operational hypothesis from noisy sensors."""

    label: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    supports_threat: bool = True
    modality_hints: list[str] = Field(default_factory=list)


class InterpretationResult(BaseModel):
    """Structured interpreter output — candidate only; gate decides."""

    hypotheses: list[Hypothesis]
    confidence: float = Field(ge=0.0, le=1.0)
    candidate_coa: CourseOfAction
    picture_summary: str = ""
    adversarial_hypothesis: str = ""
    source: SourceKind = "heuristic"
    model: str | None = None
    error: str | None = None


def llm_configured() -> bool:
    return bool(os.environ.get("LLM_BASE_URL", "").strip())


def _intent_for(finding: Finding) -> str:
    return _DEFAULT_INTENTS.get(finding.scenario_id.upper(), "INSPECT_TARGET")


def _candidate_coa(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    timeout_seconds: float,
    intent_override: str | None = None,
) -> CourseOfAction:
    """Prefer scenario-owned COA construction (correct speed/intent defaults)."""
    from app.scenarios.base import get_scenario

    try:
        scenario = get_scenario(finding.scenario_id)
        coa = scenario.build_coa(graph, finding, timeout_seconds=timeout_seconds)
    except KeyError:
        from app.agent import make_tier1_coa

        coa = make_tier1_coa(
            graph,
            finding,
            intent=intent_override or _intent_for(finding),
            timeout_seconds=timeout_seconds,
            apply_contact_speed=False,
        )
    if intent_override:
        coa.intent = intent_override
    return coa


def heuristic_interpret(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    timeout_seconds: float = 5.0,
) -> InterpretationResult:
    """Rule-composed hypotheses from an existing Finding (demo-safe fallback)."""
    hypotheses: list[Hypothesis] = []
    breakdown = finding.source_breakdown or {}

    if finding.amber_alert:
        hypotheses.append(
            Hypothesis(
                label="sensor_contradiction",
                claim=(
                    f"Amber {finding.amber_alert}: modalities disagree "
                    f"(mismatch ≈ {finding.mismatch_m:.0f} m)."
                ),
                confidence=min(0.95, max(0.4, finding.confidence)),
                supports_threat=True,
                modality_hints=list(breakdown.keys()) if breakdown else [],
            )
        )

    for spoof in finding.spoof_sources:
        hypotheses.append(
            Hypothesis(
                label="spoof_or_manipulated",
                claim=f"Source {spoof} may be spoofed / delayed / exaggerated.",
                confidence=0.55,
                supports_threat=True,
                modality_hints=["ais", "social"],
            )
        )

    for approach in finding.approach_sources:
        hypotheses.append(
            Hypothesis(
                label="corroborated_approach",
                claim=f"Source {approach} supports an inbound / approach picture.",
                confidence=0.7,
                supports_threat=True,
                modality_hints=["radar", "optical", "rf"],
            )
        )

    if finding.adversarial_hypothesis:
        hypotheses.append(
            Hypothesis(
                label="collapse_condition",
                claim=finding.adversarial_hypothesis,
                confidence=0.5,
                supports_threat=False,
                modality_hints=[],
            )
        )

    if not hypotheses:
        hypotheses.append(
            Hypothesis(
                label="insufficient_picture",
                claim=finding.picture_summary or finding.message or "No clear discrepancy.",
                confidence=finding.confidence,
                supports_threat=finding.confidence >= 0.5,
            )
        )

    coa = _candidate_coa(graph, finding, timeout_seconds=timeout_seconds)
    coa.metadata = {
        **coa.metadata,
        "interpreter": "heuristic",
        "hypotheses": [h.model_dump() for h in hypotheses],
    }

    return InterpretationResult(
        hypotheses=hypotheses,
        confidence=finding.confidence,
        candidate_coa=coa,
        picture_summary=finding.picture_summary,
        adversarial_hypothesis=finding.adversarial_hypothesis,
        source="heuristic",
        model=None,
        error=None,
    )


def _observation_brief(graph: SpatialEntityGraph) -> list[dict[str, Any]]:
    brief: list[dict[str, Any]] = []
    for obs in graph.observations:
        brief.append(
            {
                "source_id": obs.source_id,
                "modality": obs.modality,
                "lat": obs.latitude,
                "lon": obs.longitude,
                "speed_mps": obs.speed_mps,
                "confidence": obs.confidence,
                "attributes": {
                    k: obs.attributes[k]
                    for k in (
                        "intel_text",
                        "claimed_count",
                        "contact_count",
                        "blur",
                        "note",
                        "rf_silent",
                        "empty_sector",
                    )
                    if k in obs.attributes
                },
            }
        )
    return brief


def _build_prompt(graph: SpatialEntityGraph, finding: Finding) -> str:
    payload = {
        "finding": {
            "scenario_id": finding.scenario_id,
            "threat_class": finding.threat_class,
            "warning_minutes_est": finding.warning_minutes_est,
            "mismatch_m": finding.mismatch_m,
            "confidence": finding.confidence,
            "picture_summary": finding.picture_summary,
            "adversarial_hypothesis": finding.adversarial_hypothesis,
            "amber_alert": finding.amber_alert,
            "source_breakdown": finding.source_breakdown,
        },
        "observations": _observation_brief(graph),
        "required_json_schema": {
            "hypotheses": [
                {
                    "label": "string",
                    "claim": "string",
                    "confidence": "0..1",
                    "supports_threat": "bool",
                    "modality_hints": ["string"],
                }
            ],
            "confidence": "0..1",
            "intent": (
                "CUE_AND_IDENTIFY | GNSS_DENIAL_AND_GBAD_CUE | "
                "ISR_IDENTIFY_CONTACT | APPROACH_PATROL | INSPECT_TARGET"
            ),
            "picture_summary": "string",
            "adversarial_hypothesis": "string",
        },
    }
    return (
        "You are a probabilistic C2 interpreter. Sensors disagree; produce scored "
        "hypotheses and a non-kinetic investigation intent. Never authorize kinetic "
        "action. Reply with ONLY valid JSON matching required_json_schema.\n\n"
        + json.dumps(payload, default=str)
    )


def _parse_llm_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop fence open/close
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed: Any = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _coa_from_llm_payload(
    graph: SpatialEntityGraph,
    finding: Finding,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    hypotheses: list[Hypothesis],
    model: str,
) -> CourseOfAction:
    intent = str(payload.get("intent") or _intent_for(finding)).strip().upper()
    if intent not in {
        "CUE_AND_IDENTIFY",
        "GNSS_DENIAL_AND_GBAD_CUE",
        "ISR_IDENTIFY_CONTACT",
        "APPROACH_PATROL",
        "INSPECT_TARGET",
    }:
        intent = _intent_for(finding)

    coa = _candidate_coa(
        graph,
        finding,
        timeout_seconds=timeout_seconds,
        intent_override=intent,
    )
    conf = float(payload.get("confidence", finding.confidence))
    coa.confidence = max(0.0, min(1.0, conf))
    coa.tier = ActionTier.TIER_1_HITL
    picture = str(payload.get("picture_summary") or finding.picture_summary)
    adversarial = str(payload.get("adversarial_hypothesis") or finding.adversarial_hypothesis)
    coa.metadata = {
        **coa.metadata,
        "interpreter": "llm",
        "llm_model": model,
        "picture_summary": picture,
        "adversarial_hypothesis": adversarial,
        "hypotheses": [h.model_dump() for h in hypotheses],
    }
    return coa


def llm_interpret(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    timeout_seconds: float = 5.0,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    http_timeout_s: float | None = None,
) -> InterpretationResult:
    """Call an OpenAI-compatible chat completions API; raise on hard failure."""
    base = (base_url if base_url is not None else os.environ.get("LLM_BASE_URL", "")).rstrip("/")
    if not base:
        raise RuntimeError("LLM_BASE_URL is not set")

    key = api_key if api_key is not None else os.environ.get("LLM_API_KEY", "")
    model_id = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
    timeout = http_timeout_s
    if timeout is None:
        timeout = float(os.environ.get("LLM_TIMEOUT_S", "8"))

    url = f"{base}/chat/completions"
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"

    body = {
        "model": model_id,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You output JSON only. Probabilistic proposes; deterministic gate disposes."
                ),
            },
            {"role": "user", "content": _build_prompt(graph, finding)},
        ],
    }

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    payload = _parse_llm_json(content)

    raw_hyps = payload.get("hypotheses") or []
    hypotheses: list[Hypothesis] = []
    for item in raw_hyps:
        if not isinstance(item, dict):
            continue
        hypotheses.append(
            Hypothesis(
                label=str(item.get("label", "hypothesis")),
                claim=str(item.get("claim", "")),
                confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                supports_threat=bool(item.get("supports_threat", True)),
                modality_hints=[str(x) for x in (item.get("modality_hints") or [])],
            )
        )
    if not hypotheses:
        # LLM returned empty — still build COA but mark thin
        hypotheses = [
            Hypothesis(
                label="llm_empty_hypotheses",
                claim=str(payload.get("picture_summary") or finding.picture_summary),
                confidence=float(payload.get("confidence", finding.confidence)),
            )
        ]

    conf = max(0.0, min(1.0, float(payload.get("confidence", finding.confidence))))
    coa = _coa_from_llm_payload(
        graph,
        finding,
        payload,
        timeout_seconds=timeout_seconds,
        hypotheses=hypotheses,
        model=model_id,
    )

    return InterpretationResult(
        hypotheses=hypotheses,
        confidence=conf,
        candidate_coa=coa,
        picture_summary=str(payload.get("picture_summary") or finding.picture_summary),
        adversarial_hypothesis=str(
            payload.get("adversarial_hypothesis") or finding.adversarial_hypothesis
        ),
        source="llm",
        model=model_id,
        error=None,
    )


def interpret(
    graph: SpatialEntityGraph,
    finding: Finding,
    *,
    timeout_seconds: float = 5.0,
    force_heuristic: bool = False,
) -> InterpretationResult:
    """Prefer LLM when configured; always fall back to heuristics on failure."""
    if force_heuristic or not llm_configured():
        return heuristic_interpret(graph, finding, timeout_seconds=timeout_seconds)

    try:
        return llm_interpret(graph, finding, timeout_seconds=timeout_seconds)
    except Exception:
        # Broad catch: demo must not hard-depend on a live LLM endpoint.
        fallback = heuristic_interpret(graph, finding, timeout_seconds=timeout_seconds)
        # Do not expose raw exception details to API callers.
        fallback.error = "llm_failed"
        fallback.candidate_coa.metadata = {
            **fallback.candidate_coa.metadata,
            "llm_error": fallback.error,
        }
        return fallback
