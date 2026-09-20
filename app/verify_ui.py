"""NexusGate verification harness (Phase 2 #65) — FastAPI + Jinja2/HTMX.

Served from the same Core as frozen REST. UI never seals DecisionTokens.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.schema import utc_now
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.adapters.dual_sar import resolve_dual_sar_events
from app.adapters.glint_client import resolve_glint_events
from app.adapters.sar_candidate_event import candidate_event_to_observation
from app.adapters.sentinel_imagery import resolve_sentinel_events

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(tags=["verify-ui"])

DEFAULT_UNIT = "CUE-NODE-01"
DEFAULT_SCENARIO = "S2"
DEFAULT_TIMEOUT = 30.0


def _c2() -> Any:
    """Late import to avoid circular import with ``app.c2_server``."""
    from app import c2_server

    return c2_server


def _exc_message(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _evidence_urls(runtime: Any) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def _add(uri: object) -> None:
        if not isinstance(uri, str) or not uri:
            return
        name = uri.rsplit("/", 1)[-1]
        path = f"/static/fixtures/{name}"
        if path not in seen:
            seen.add(path)
            urls.append(path)

    for obs in runtime.graph.observations:
        _add(obs.attributes.get("evidence_image_uri"))
    for track in runtime.graph.all_tracks():
        _add(track.attributes.get("evidence_image_uri"))
    return urls


def _ctx(
    request: Request,
    *,
    flash: str = "",
    error: str = "",
    unit_id: str = DEFAULT_UNIT,
    scenario_id: str = DEFAULT_SCENARIO,
) -> dict[str, Any]:
    runtime = _c2().get_runtime()
    pending = list(runtime.proposals.keys())
    taskings = [
        t
        for cid, t in runtime.inbox.items()
        if cid not in runtime.acked and t.get("unit_id") == unit_id
    ]
    queued_coa = runtime.proposals[pending[0]]["coa"] if pending else None
    return {
        "request": request,
        "flash": flash,
        "error": error,
        "unit_id": unit_id,
        "scenario_id": scenario_id,
        "finding": runtime.finding,
        "scenario_runtime": runtime.scenario_id,
        "pending_ids": pending,
        "queued_coa": queued_coa,
        "taskings": taskings,
        "tracks": list(runtime.graph.all_tracks())[:12],
        "observations": list(runtime.graph.observations)[:12],
        "obs_count": len(runtime.graph.observations),
        "inbox_depth": len([k for k in runtime.inbox if k not in runtime.acked]),
        "evidence": _evidence_urls(runtime),
        "audit_rows": list(reversed(runtime.audit.records()[-12:])),
    }


def _page(
    request: Request,
    template: str,
    **kwargs: Any,
) -> HTMLResponse:
    return templates.TemplateResponse(request, template, _ctx(request, **kwargs))


@router.get("/verify", response_class=HTMLResponse)
async def verify_hub(request: Request) -> HTMLResponse:
    return _page(request, "verify/hub.html")


@router.get("/verify/command", response_class=HTMLResponse)
async def verify_command(
    request: Request,
    unit_id: str = DEFAULT_UNIT,
    scenario_id: str = DEFAULT_SCENARIO,
) -> HTMLResponse:
    return _page(
        request,
        "verify/command.html",
        unit_id=unit_id,
        scenario_id=scenario_id,
    )


@router.get("/verify/recipient", response_class=HTMLResponse)
async def verify_recipient(
    request: Request,
    unit_id: str = DEFAULT_UNIT,
) -> HTMLResponse:
    return _page(request, "verify/recipient.html", unit_id=unit_id)


@router.get("/verify/recipient/poll", response_class=HTMLResponse)
async def verify_poll(
    request: Request,
    unit_id: str = DEFAULT_UNIT,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "verify/partials/recipient_body.html",
        _ctx(request, unit_id=unit_id),
    )


@router.post("/verify/command/propose", response_class=HTMLResponse)
async def verify_propose(
    request: Request,
    scenario_id: str = Form(DEFAULT_SCENARIO),
    unit_id: str = Form(DEFAULT_UNIT),
) -> HTMLResponse:
    runtime = _c2().get_runtime()
    flash = ""
    error = ""
    try:
        coa = _c2()._load_scenario(runtime, scenario_id, DEFAULT_TIMEOUT)
        coa = coa.model_copy(update={"unit_id": unit_id})
        runtime.proposals[coa.coa_id] = {
            "coa": coa,
            "unit_id": unit_id,
            "created_at": utc_now().isoformat(),
        }
        runtime.audit.append(
            "coa_proposed",
            "Info",
            {"coa_id": coa.coa_id, "scenario_id": scenario_id, "unit_id": unit_id},
        )
        flash = f"Queued {coa.coa_id[:8]}… ({scenario_id})"
    except (HTTPException, KeyError, ValueError) as exc:
        error = _exc_message(exc)
    return _page(
        request,
        "verify/command.html",
        flash=flash,
        error=error,
        unit_id=unit_id,
        scenario_id=scenario_id,
    )


@router.post("/verify/command/approve", response_class=HTMLResponse)
async def verify_approve(
    request: Request,
    coa_id: str = Form(...),
    decision: str = Form(...),
    unit_id: str = Form(DEFAULT_UNIT),
    scenario_id: str = Form(DEFAULT_SCENARIO),
) -> HTMLResponse:
    flash = ""
    error = ""
    try:
        c2 = _c2()
        result = await c2.gate_approve(
            c2.ApproveRequest(
                coa_id=coa_id,
                decision=decision,
                operator_id="nexusgate-verify-screen1",
            )
        )
        flash = f"{result.get('status')} · coa {coa_id[:8]}…"
    except HTTPException as exc:
        error = _exc_message(exc)
    return _page(
        request,
        "verify/command.html",
        flash=flash,
        error=error,
        unit_id=unit_id,
        scenario_id=scenario_id,
    )


@router.post("/verify/command/ingress", response_class=HTMLResponse)
async def verify_ingress(
    request: Request,
    mode: str = Form("sentinel"),
    unit_id: str = Form(DEFAULT_UNIT),
    scenario_id: str = Form(DEFAULT_SCENARIO),
) -> HTMLResponse:
    """Ingest SAR evidence for side-by-side compare: SIA / GLINT / Dual-SAR."""
    runtime = _c2().get_runtime()
    flash = ""
    error = ""
    try:
        label = mode
        if mode == "dual_sar":
            events, source = resolve_dual_sar_events(use_fixture=True)
            label = "Dual-SAR (GLINT x SIA)"
        elif mode in {"glint", "glint_fixture"}:
            events, source = resolve_glint_events(use_fixture=True)
            label = "GLINT only (fixture)"
        elif mode == "glint_pull":
            events, source = resolve_glint_events(pull_upstream=True, use_fixture=True)
            label = "GLINT only (pull→fixture fail-safe)"
        elif mode in {"sentinel", "sia"}:
            events, source = resolve_sentinel_events(use_fixture=True)
            label = "SIA only (Sentinel fixture)"
        else:
            raise ValueError(f"Unknown ingress mode: {mode}")
        if not events:
            raise ValueError("No detections to ingest")
        for payload in events:
            obs = candidate_event_to_observation(payload)
            runtime.graph.ingest(obs)
        flash = f"{label}: ingested {len(events)} · source={source}"
    except (ValueError, OSError, TypeError) as exc:
        error = str(exc)
    return _page(
        request,
        "verify/command.html",
        flash=flash,
        error=error,
        unit_id=unit_id,
        scenario_id=scenario_id,
    )


@router.post("/verify/command/reset", response_class=HTMLResponse)
async def verify_reset(
    request: Request,
    unit_id: str = Form(DEFAULT_UNIT),
    scenario_id: str = Form(DEFAULT_SCENARIO),
) -> HTMLResponse:
    _c2().get_runtime().reset()
    return _page(
        request,
        "verify/command.html",
        flash="Runtime reset",
        unit_id=unit_id,
        scenario_id=scenario_id,
    )


@router.post("/verify/recipient/ack", response_class=HTMLResponse)
async def verify_ack(
    request: Request,
    coa_id: str = Form(...),
    unit_id: str = Form(DEFAULT_UNIT),
) -> HTMLResponse:
    flash = ""
    error = ""
    try:
        c2 = _c2()
        result = await c2.recipient_ack(
            c2.AckRequest(
                coa_id=coa_id,
                unit_id=unit_id,
                message="nexusgate-verify-screen2",
            )
        )
        flash = f"Ack {result.get('status')} · {coa_id[:8]}…"
    except HTTPException as exc:
        error = _exc_message(exc)
    return _page(request, "verify/recipient.html", flash=flash, error=error, unit_id=unit_id)


@router.get("/")
async def root_to_verify() -> RedirectResponse:
    return RedirectResponse(url="/verify", status_code=302)
