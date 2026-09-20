"""Unified C2 REST server — Screen 1 (command) + Screen 2 (recipient)."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from core.audit import AuditLogger
from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.gate import LatencyBoundedGate
from core.ingress_replay import IngressReplayLog
from core.ontology import SpatialEntityGraph
from core.policy import TieredPolicy
from core.schema import DecisionToken, canonical_json, sha256_hex, utc_now
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.adapters.sar_candidate_event import candidate_event_to_observation
from app.adapters.southbound_sensor import normalize_sensor_event
from app.llm_interpreter import InterpretationResult, interpret
from app.scenarios.base import Finding, get_scenario

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
DEFAULT_POLICY = APP_DIR / "config" / "maritime_defense_policy.yaml"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
VERIFY_STATIC = APP_DIR / "static" / "verify"


def _default_audit_path() -> Path:
    override = os.environ.get("AUDIT_PATH")
    if override:
        return Path(override)
    return ROOT / ".audit" / "gate.jsonl"


def _default_ingress_replay_path() -> Path:
    override = os.environ.get("INGRESS_REPLAY_PATH")
    if override:
        return Path(override)
    return ROOT / ".audit" / "ingress.jsonl"


DEFAULT_AUDIT = _default_audit_path()
DEFAULT_INGRESS_REPLAY = _default_ingress_replay_path()

app = FastAPI(title="NexusGate C2 Server", version="0.1.0")

# Browser NexusGate verify UI (Phase 2 #65) — local Core. Cloudflare Worker adds CORS separately.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "C2_CORS_ORIGINS",
        "http://127.0.0.1:3000,http://localhost:3000",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Demo evidence chips (e.g. Sentinel SAR) — operational, not frozen Screen 1/2 handshake.
if FIXTURES_DIR.is_dir():
    app.mount(
        "/static/fixtures",
        StaticFiles(directory=str(FIXTURES_DIR)),
        name="fixtures",
    )

# NexusGate Verify harness assets (Phase 2 #65) — CSS for Jinja2/HTMX UI.
if VERIFY_STATIC.is_dir():
    app.mount(
        "/static/verify",
        StaticFiles(directory=str(VERIFY_STATIC)),
        name="verify_static",
    )


class ProposalRequest(BaseModel):
    """Submit a raw COA and/or build one from a defense scenario."""

    scenario_id: str | None = None
    coa: CourseOfAction | None = None
    unit_id: str = "ISR-NODE-01"
    timeout_seconds: float | None = None
    # When true with scenario_id: run probabilistic interpreter → candidate COA → gate.
    interpret: bool = False
    force_heuristic: bool = False


class InterpretRequest(BaseModel):
    """Probabilistic propose only — never seals DecisionTokens."""

    scenario_id: str
    timeout_seconds: float | None = None
    force_heuristic: bool = False


class CandidateEventIngressRequest(BaseModel):
    """Upstream macro intelligence push (assumed CandidateEvent v1.3.0).

    Sentinel-Imagery-Analysis (issue #47): ``use_sentinel_fixture``, ``pull_upstream``,
    or raw ``run_cv`` body. GLINT Assumed-mock (issue #55): ``pull_glint`` /
    ``use_glint_fixture``. Dual-SAR (issue #56): ``dual_sar`` / ``pull_dual_sar``.
    Assumed fixture / ``event`` remain for Pitch-1 (#25).
    """

    event: dict[str, Any] | None = None
    use_fixture: bool = False
    use_sentinel_fixture: bool = False
    pull_upstream: bool = False
    run_cv: dict[str, Any] | None = None
    pull_glint: bool = False
    use_glint_fixture: bool = False
    dual_sar: bool = False
    pull_dual_sar: bool = False


class OpenFeedIngressRequest(BaseModel):
    """Optional demo-grade open AIS / open air ingress (issue #16)."""

    feed: str = Field(description="ais | air | all (or comma list)")
    payload: dict[str, Any] | None = None
    use_fixture: bool = False


class ApproveRequest(BaseModel):
    coa_id: str
    decision: str = Field(description="y/yes/approve or n/no/deny")
    operator_id: str = "operator"


class AckRequest(BaseModel):
    coa_id: str
    unit_id: str
    signature: str | None = None
    status: str = "ACKED"
    message: str = ""
    telemetry: dict[str, Any] = Field(default_factory=dict)


class AuditSnapshotRequest(BaseModel):
    """Replace on-disk OCSF jsonl (Cloudflare container hydrate; not a frozen client path)."""

    records: list[dict[str, Any]]


class C2Runtime:
    def __init__(
        self,
        *,
        policy_path: Path = DEFAULT_POLICY,
        audit_path: Path = DEFAULT_AUDIT,
        ingress_replay_path: Path = DEFAULT_INGRESS_REPLAY,
    ) -> None:
        self.policy = TieredPolicy.from_yaml(policy_path)
        self.audit = AuditLogger(audit_path)
        self.ingress_replay = IngressReplayLog(ingress_replay_path)
        self.graph = SpatialEntityGraph(associate_radius_m=2_000.0)
        self.finding: Finding | None = None
        self.scenario_id: str | None = None
        self.proposals: dict[str, dict[str, Any]] = {}
        self.inbox: dict[str, dict[str, Any]] = {}  # coa_id -> tasking
        self.acked: set[str] = set()

    def reset(self) -> None:
        self.graph = SpatialEntityGraph(associate_radius_m=2_000.0)
        self.finding = None
        self.scenario_id = None
        self.proposals.clear()
        self.inbox.clear()
        self.acked.clear()
        # Drop soft-duplicate keys so the same scenario can be re-proposed after reset.
        self.policy.interlock.active_coa_ids.clear()


_runtime = C2Runtime()


def get_runtime() -> C2Runtime:
    return _runtime


def _finding_dict(finding: Finding | None) -> dict[str, Any] | None:
    if finding is None:
        return None
    return asdict(finding)


def _ingest_scenario(runtime: C2Runtime, scenario_id: str) -> Finding:
    scenario = get_scenario(scenario_id)
    runtime.graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    events = scenario.build_events()
    runtime.graph.ingest_many([normalize_sensor_event(e) for e in events])
    runtime.scenario_id = scenario.id
    finding = scenario.detect(runtime.graph)
    runtime.finding = finding
    if finding is None:
        raise HTTPException(status_code=404, detail=f"No finding for scenario {scenario_id}")
    return finding


def _load_scenario(runtime: C2Runtime, scenario_id: str, timeout: float) -> CourseOfAction:
    finding = _ingest_scenario(runtime, scenario_id)
    scenario = get_scenario(scenario_id)
    coa = scenario.build_coa(runtime.graph, finding, timeout_seconds=timeout)
    return runtime.policy.apply_defaults(coa)


def _interpret_scenario(
    runtime: C2Runtime,
    scenario_id: str,
    timeout: float,
    *,
    force_heuristic: bool = False,
) -> InterpretationResult:
    _ingest_scenario(runtime, scenario_id)
    assert runtime.finding is not None
    result = interpret(
        runtime.graph,
        runtime.finding,
        timeout_seconds=timeout,
        force_heuristic=force_heuristic,
    )
    result.candidate_coa = runtime.policy.apply_defaults(result.candidate_coa)
    return result


def _interpretation_response(result: InterpretationResult) -> dict[str, Any]:
    return {
        "status": "INTERPRETED",
        "source": result.source,
        "model": result.model,
        "error": result.error,
        "hypotheses": [h.model_dump() for h in result.hypotheses],
        "confidence": result.confidence,
        "picture_summary": result.picture_summary,
        "adversarial_hypothesis": result.adversarial_hypothesis,
        "candidate_coa": result.candidate_coa.model_dump(mode="json"),
        "finding": _finding_dict(get_runtime().finding),
    }


@app.get("/api/ontology/state")
async def ontology_state() -> dict[str, Any]:
    runtime = get_runtime()
    tracks = [
        {
            "track_id": t.track_id,
            "latitude": t.latitude,
            "longitude": t.longitude,
            "speed_mps": t.speed_mps,
            "confidence": t.confidence,
            "source_ids": t.source_ids,
            "modalities": t.modalities,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "attributes": t.attributes,
        }
        for t in runtime.graph.all_tracks()
    ]
    observations = [o.model_dump(mode="json") for o in runtime.graph.observations]
    amber: dict[str, Any] | None = None
    if runtime.finding is not None:
        amber = {
            "alert": runtime.finding.amber_alert,
            "threat_class": runtime.finding.threat_class,
            "mismatch_m": runtime.finding.mismatch_m,
            "picture_summary": runtime.finding.picture_summary,
            "source_breakdown": runtime.finding.source_breakdown,
            "scenario_id": runtime.finding.scenario_id,
        }
    return {
        "scenario_id": runtime.scenario_id,
        "tracks": tracks,
        "observations": observations,
        "amber_alert": amber,
        "pending_proposals": list(runtime.proposals.keys()),
        "inbox_depth": len([k for k in runtime.inbox if k not in runtime.acked]),
    }


@app.post("/api/ingress/candidate-event")
async def ingress_candidate_event(req: CandidateEventIngressRequest) -> dict[str, Any]:
    """Ingest CandidateEvent / Sentinel / GLINT / Dual-SAR → Observation (space_sar).

    Never seals tokens. Sentinel paths (issue #47) fall back to the Singapore Strait
    fixture when ``pull_upstream`` cannot reach the sibling upstream. GLINT paths
    (issue #55) fall back to the assumed CandidateEvent fixture when mock/live is down.
    Dual-SAR (issue #56) corroborates GLINT x SIA and fails safe to SIA/fixture.
    """
    from app.adapters.dual_sar import resolve_dual_sar_events
    from app.adapters.glint_client import resolve_glint_events
    from app.adapters.sar_candidate_event import load_assumed_fixture
    from app.adapters.sentinel_imagery import resolve_sentinel_events

    runtime = get_runtime()
    resolved_source: str | None = None
    events: list[Any]

    if req.dual_sar or req.pull_dual_sar:
        try:
            mapped, resolved_source = resolve_dual_sar_events(
                pull=req.pull_dual_sar,
                use_fixture=req.dual_sar or req.pull_dual_sar,
                run_cv=req.run_cv,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not mapped:
            raise HTTPException(
                status_code=400,
                detail="No Dual-SAR / dark-vessel detections to ingest",
            )
        events = mapped
    elif req.run_cv is not None or req.pull_upstream or req.use_sentinel_fixture:
        try:
            mapped, resolved_source = resolve_sentinel_events(
                run_cv=req.run_cv,
                pull_upstream=req.pull_upstream,
                use_fixture=req.use_sentinel_fixture or req.pull_upstream,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not mapped:
            raise HTTPException(
                status_code=400,
                detail="No uncorrelated (dark vessel) detections to ingest",
            )
        events = mapped
    elif req.pull_glint or req.use_glint_fixture:
        try:
            mapped, resolved_source = resolve_glint_events(
                pull_upstream=req.pull_glint,
                use_fixture=req.use_glint_fixture or req.pull_glint,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        events = mapped
    elif req.use_fixture:
        events = [load_assumed_fixture()]
    elif req.event is not None:
        events = [req.event]
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide event, use_fixture=true, use_sentinel_fixture=true, "
                "pull_upstream=true, run_cv={...}, pull_glint=true, "
                "use_glint_fixture=true, dual_sar=true, or pull_dual_sar=true"
            ),
        )

    observations: list[dict[str, Any]] = []
    track_ids: list[str] = []
    try:
        for payload in events:
            obs = candidate_event_to_observation(payload)
            track = runtime.graph.ingest(obs)
            runtime.audit.append(
                "candidate_event_ingested",
                "Info",
                {
                    "observation_id": obs.observation_id,
                    "source_id": obs.source_id,
                    "modality": obs.modality,
                    "track_id": track.track_id,
                    "event_type": obs.entity_hint,
                    "ingress_source": resolved_source or "candidate_event",
                },
            )
            observations.append(obs.model_dump(mode="json"))
            track_ids.append(track.track_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ingress_source = resolved_source or ("fixture" if req.use_fixture else "event")
    # Replay log is best-effort — never fail a successful ingest (issue #54).
    runtime.ingress_replay.append(
        source=ingress_source,
        endpoint="/api/ingress/candidate-event",
        payload=req.model_dump(mode="json"),
    )

    first = observations[0]
    return {
        "status": "INGESTED",
        "observation": first,
        "observations": observations,
        "track_id": track_ids[0],
        "track_ids": track_ids,
        "count": len(observations),
        "source": ingress_source,
    }


@app.post("/api/ingress/open-feed")
async def ingress_open_feed(req: OpenFeedIngressRequest) -> dict[str, Any]:
    """Ingest optional open AIS / open air snapshots. Never seals tokens; S1-S3 stay primary."""
    from app.adapters.open_feed import (
        open_feed_to_observations,
        parse_open_feed_selection,
    )

    runtime = get_runtime()
    try:
        feeds = parse_open_feed_selection(req.feed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not feeds:
        raise HTTPException(status_code=400, detail="feed must be ais, air, or all")

    if req.payload is not None and len(feeds) != 1:
        raise HTTPException(
            status_code=400,
            detail="payload requires a single feed (ais or air); use use_fixture for all",
        )
    if not req.use_fixture and req.payload is None:
        raise HTTPException(status_code=400, detail="Provide payload or use_fixture=true")

    ingested: list[dict[str, Any]] = []
    for feed in feeds:
        try:
            observations = open_feed_to_observations(
                feed,
                req.payload,
                use_fixture=req.use_fixture,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        for obs in observations:
            track = runtime.graph.ingest(obs)
            runtime.audit.append(
                "open_feed_ingested",
                "Info",
                {
                    "feed": feed,
                    "observation_id": obs.observation_id,
                    "source_id": obs.source_id,
                    "modality": obs.modality,
                    "track_id": track.track_id,
                },
            )
            ingested.append(
                {
                    "feed": feed,
                    "observation": obs.model_dump(mode="json"),
                    "track_id": track.track_id,
                }
            )

    # Optional open-feed replay (issue #54) — best-effort, never fails ingress.
    runtime.ingress_replay.append(
        source=f"open_feed:{','.join(feeds)}",
        endpoint="/api/ingress/open-feed",
        payload=req.model_dump(mode="json"),
    )

    return {
        "status": "INGESTED",
        "feeds": list(feeds),
        "count": len(ingested),
        "items": ingested,
    }


@app.post("/api/interpret")
async def interpret_picture(req: InterpretRequest) -> dict[str, Any]:
    """App-layer LLM/heuristic propose: hypotheses + candidate COA (no token seal)."""
    runtime = get_runtime()
    timeout = req.timeout_seconds or runtime.policy.default_timeout_seconds
    try:
        result = _interpret_scenario(
            runtime,
            req.scenario_id,
            timeout,
            force_heuristic=req.force_heuristic,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    runtime.audit.append(
        "picture_interpreted",
        "Low",
        {
            "scenario_id": req.scenario_id,
            "source": result.source,
            "model": result.model,
            "error": result.error,
            "hypothesis_count": len(result.hypotheses),
            "coa_id": result.candidate_coa.coa_id,
            "intent": result.candidate_coa.intent,
        },
    )
    return _interpretation_response(result)


@app.post("/api/gate/proposals")
async def gate_proposals(req: ProposalRequest) -> dict[str, Any]:
    runtime = get_runtime()
    timeout = req.timeout_seconds or runtime.policy.default_timeout_seconds
    interpretation: InterpretationResult | None = None

    if req.scenario_id and req.interpret:
        try:
            interpretation = _interpret_scenario(
                runtime,
                req.scenario_id,
                timeout,
                force_heuristic=req.force_heuristic,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        coa = interpretation.candidate_coa
    elif req.scenario_id:
        coa = _load_scenario(runtime, req.scenario_id, timeout)
    elif req.coa is not None:
        coa = runtime.policy.apply_defaults(req.coa)
    else:
        raise HTTPException(status_code=400, detail="Provide scenario_id or coa")

    # Fast interlock check before queueing for HITL
    gate = LatencyBoundedGate(
        timeout_sec=timeout,
        interlock=runtime.policy.interlock,
    )
    ok, reason = gate.verify_deterministic_interlocks(coa)
    if not ok:
        token = DecisionToken(
            coa_id=coa.coa_id,
            verdict=GateVerdict.REJECTED_FAST.value,
            reason=reason,
        )
        token.seal()
        runtime.audit.append(
            "coa_rejected_fast",
            "High",
            {"coa": coa.model_dump(mode="json"), "token": token.model_dump(mode="json")},
        )
        return {
            "status": "REJECTED_FAST",
            "reason": reason,
            "coa": coa.model_dump(mode="json"),
            "token": token.model_dump(mode="json"),
        }

    if coa.tier == ActionTier.TIER_0_AUTONOMOUS:
        token = DecisionToken(
            coa_id=coa.coa_id,
            verdict=GateVerdict.APPROVED.value,
            operator_id="autonomous",
            reason="tier0_auto",
        )
        token.seal()
        tasking = {
            "coa": coa.model_dump(mode="json"),
            "token": token.model_dump(mode="json"),
            "unit_id": req.unit_id,
            "issued_at": utc_now().isoformat(),
            "status": "PENDING_ACK",
        }
        runtime.inbox[coa.coa_id] = tasking
        runtime.policy.interlock.register_active(coa)
        runtime.audit.append(
            "coa_auto_approved",
            "High",
            {"coa_id": coa.coa_id, "token": token.model_dump(mode="json")},
        )
        return {
            "status": "APPROVED",
            "coa": coa.model_dump(mode="json"),
            "token": token.model_dump(mode="json"),
            "finding": _finding_dict(runtime.finding),
        }

    runtime.proposals[coa.coa_id] = {
        "coa": coa,
        "unit_id": req.unit_id,
        "queued_at": utc_now().isoformat(),
    }
    runtime.audit.append(
        "coa_proposed",
        "Medium",
        {
            "coa_id": coa.coa_id,
            "scenario_id": runtime.scenario_id,
            "intent": coa.intent,
            "unit_id": req.unit_id,
            "finding": _finding_dict(runtime.finding),
            "interpreter_source": interpretation.source if interpretation else None,
        },
    )
    queued: dict[str, Any] = {
        "status": "QUEUED",
        "coa": coa.model_dump(mode="json"),
        "finding": _finding_dict(runtime.finding),
    }
    if interpretation is not None:
        queued["hypotheses"] = [h.model_dump() for h in interpretation.hypotheses]
        queued["interpreter_source"] = interpretation.source
        queued["interpreter_error"] = interpretation.error
    return queued


@app.post("/api/gate/approve")
async def gate_approve(req: ApproveRequest) -> dict[str, Any]:
    runtime = get_runtime()
    pending = runtime.proposals.get(req.coa_id)
    if pending is None:
        raise HTTPException(status_code=404, detail=f"No pending proposal {req.coa_id}")

    coa: CourseOfAction = pending["coa"]
    decision = req.decision.strip().lower()
    if decision in {"y", "yes", "approve", "approved"}:
        verdict = GateVerdict.APPROVED
        reason = "operator_approve"
    elif decision in {"n", "no", "deny", "denied", "reject", "rejected"}:
        verdict = GateVerdict.REJECTED_OPERATOR
        reason = "operator_deny"
    else:
        raise HTTPException(status_code=400, detail="decision must be approve or deny")

    token = DecisionToken(
        coa_id=coa.coa_id,
        verdict=verdict.value,
        operator_id=req.operator_id,
        reason=reason,
    )
    token.seal()
    del runtime.proposals[req.coa_id]

    runtime.audit.append(
        "gate_decision",
        "High",
        {
            "coa_id": coa.coa_id,
            "verdict": verdict.value,
            "token": token.model_dump(mode="json"),
            "operator_id": req.operator_id,
        },
    )

    if verdict == GateVerdict.APPROVED:
        tasking = {
            "coa": coa.model_dump(mode="json"),
            "token": token.model_dump(mode="json"),
            "unit_id": pending["unit_id"],
            "issued_at": utc_now().isoformat(),
            "status": "PENDING_ACK",
        }
        runtime.inbox[coa.coa_id] = tasking
        runtime.policy.interlock.register_active(coa)
        runtime.audit.append(
            "tasking_issued",
            "High",
            {"coa_id": coa.coa_id, "unit_id": pending["unit_id"]},
        )

    return {
        "status": verdict.value,
        "coa": coa.model_dump(mode="json"),
        "token": token.model_dump(mode="json"),
    }


@app.get("/api/recipient/inbox")
async def recipient_inbox(
    unit_id: str = Query(..., description="Recipient unit identifier"),
) -> dict[str, Any]:
    runtime = get_runtime()
    items = [
        item
        for item in runtime.inbox.values()
        if item["unit_id"] == unit_id and item["coa"]["coa_id"] not in runtime.acked
    ]
    return {"unit_id": unit_id, "taskings": items, "count": len(items)}


@app.post("/api/recipient/ack")
async def recipient_ack(req: AckRequest) -> dict[str, Any]:
    runtime = get_runtime()
    tasking = runtime.inbox.get(req.coa_id)
    if tasking is None:
        raise HTTPException(status_code=404, detail=f"No inbox item for {req.coa_id}")
    if tasking["unit_id"] != req.unit_id:
        raise HTTPException(status_code=403, detail="unit_id does not match tasking")

    signature = req.signature or sha256_hex(
        canonical_json(
            {
                "coa_id": req.coa_id,
                "unit_id": req.unit_id,
                "status": req.status,
                "time": utc_now().isoformat(),
            }
        )
    )
    ack_record = {
        "ack_id": str(uuid4()),
        "coa_id": req.coa_id,
        "unit_id": req.unit_id,
        "status": req.status,
        "message": req.message,
        "telemetry": req.telemetry,
        "signature": signature,
        "token_digest": tasking["token"].get("digest"),
        "acked_at": utc_now().isoformat(),
    }
    runtime.acked.add(req.coa_id)
    tasking["status"] = "ACKED"
    tasking["ack"] = ack_record
    sealed = runtime.audit.append("recipient_ack", "High", ack_record)
    return {"status": "ACKED", "ack": ack_record, "audit_hash": sealed["hash"]}


@app.get("/health")
async def health() -> dict[str, str]:
    """Readiness probe. Not part of the frozen C2 contract."""
    return {"status": "ok"}


@app.get("/api/audit/trail")
async def audit_trail() -> dict[str, Any]:
    runtime = get_runtime()
    records = runtime.audit.records()
    return {"count": len(records), "path": str(runtime.audit.path), "records": records}


@app.put("/api/admin/audit/snapshot")
async def admin_audit_snapshot(req: AuditSnapshotRequest) -> dict[str, Any]:
    """Hydrate jsonl after ephemeral container disk reset. Does not mint tokens."""
    runtime = get_runtime()
    runtime.audit.replace_records(req.records)
    return {"status": "restored", "count": len(req.records)}


@app.post("/api/admin/reset")
async def admin_reset() -> dict[str, str]:
    """Test helper: clear in-memory C2 state (does not wipe audit file)."""
    get_runtime().reset()
    return {"status": "reset"}


from app.verify_ui import router as verify_router  # noqa: E402

app.include_router(verify_router)


def cli_main() -> None:
    host = os.environ.get("C2_HOST", "127.0.0.1")
    port = int(os.environ.get("C2_PORT", "8080"))
    uvicorn.run("app.c2_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli_main()
