"""Unified C2 REST server — Screen 1 (command) + Screen 2 (recipient)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
from core.audit import AuditLogger
from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.gate import LatencyBoundedGate
from core.ontology import SpatialEntityGraph
from core.policy import TieredPolicy
from core.schema import DecisionToken, canonical_json, sha256_hex, utc_now
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.adapters.southbound_sensor import normalize_sensor_event
from app.scenarios.base import Finding, get_scenario

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
DEFAULT_POLICY = APP_DIR / "config" / "maritime_defense_policy.yaml"
DEFAULT_AUDIT = ROOT / ".audit" / "gate.jsonl"

app = FastAPI(title="NexusGate C2 Server", version="0.1.0")


class ProposalRequest(BaseModel):
    """Submit a raw COA and/or build one from a defense scenario."""

    scenario_id: str | None = None
    coa: CourseOfAction | None = None
    unit_id: str = "ISR-NODE-01"
    timeout_seconds: float | None = None


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


class C2Runtime:
    def __init__(
        self,
        *,
        policy_path: Path = DEFAULT_POLICY,
        audit_path: Path = DEFAULT_AUDIT,
    ) -> None:
        self.policy = TieredPolicy.from_yaml(policy_path)
        self.audit = AuditLogger(audit_path)
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


_runtime = C2Runtime()


def get_runtime() -> C2Runtime:
    return _runtime


def _finding_dict(finding: Finding | None) -> dict[str, Any] | None:
    if finding is None:
        return None
    return asdict(finding)


def _load_scenario(runtime: C2Runtime, scenario_id: str, timeout: float) -> CourseOfAction:
    scenario = get_scenario(scenario_id)
    runtime.graph = SpatialEntityGraph(associate_radius_m=2_000.0)
    events = scenario.build_events()
    runtime.graph.ingest_many([normalize_sensor_event(e) for e in events])
    runtime.scenario_id = scenario.id
    finding = scenario.detect(runtime.graph)
    runtime.finding = finding
    if finding is None:
        raise HTTPException(status_code=404, detail=f"No finding for scenario {scenario_id}")
    coa = scenario.build_coa(runtime.graph, finding, timeout_seconds=timeout)
    return runtime.policy.apply_defaults(coa)


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


@app.post("/api/gate/proposals")
async def gate_proposals(req: ProposalRequest) -> dict[str, Any]:
    runtime = get_runtime()
    timeout = req.timeout_seconds or runtime.policy.default_timeout_seconds

    if req.scenario_id:
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
        },
    )
    return {
        "status": "QUEUED",
        "coa": coa.model_dump(mode="json"),
        "finding": _finding_dict(runtime.finding),
    }


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


@app.get("/api/audit/trail")
async def audit_trail() -> dict[str, Any]:
    runtime = get_runtime()
    path = runtime.audit.path
    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return {"count": len(records), "path": str(path), "records": records}


@app.post("/api/admin/reset")
async def admin_reset() -> dict[str, str]:
    """Test helper: clear in-memory C2 state (does not wipe audit file)."""
    get_runtime().reset()
    return {"status": "reset"}


def cli_main() -> None:
    host = os.environ.get("C2_HOST", "127.0.0.1")
    port = int(os.environ.get("C2_PORT", "8080"))
    uvicorn.run("app.c2_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli_main()
