"""NexusGate verification harness (Phase 2 #65) — FastAPI + Jinja2/HTMX.

Served from the same Core as frozen REST. UI never seals DecisionTokens.
"""

from __future__ import annotations

from math import atan2, cos, degrees, radians, sin
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
DEFAULT_SCENARIO = "S3"
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


def _ocsf_health(runtime: Any) -> dict[str, Any]:
    """Hash-chain integrity summary for the verify UI pill (#88)."""
    from core.audit import verify_audit_chain

    records = runtime.audit.records()
    result = verify_audit_chain(records)
    broken = 0 if result.ok else (len(result.errors) if result.errors else 1)
    detail = ""
    if not result.ok and result.break_index is not None and result.reason:
        detail = f" · {result.reason} @ record[{result.break_index}]"

    path = "sha256"
    eds_ok: bool | None = None
    eds_label: str | None = None
    last_eds = getattr(runtime, "last_eds_verify", None)
    if isinstance(last_eds, dict):
        eds_ok = bool(last_eds.get("ok"))
        eds_label = str(last_eds.get("label") or last_eds.get("summary") or "")
        path = "eds"
    elif runtime.audit.eds is not None:
        # Sidecar present but not yet re-verified out-of-process.
        eds_label = "eds sidecar (re-verify for CHAIN_VALID)"

    return {
        "verified": result.ok,
        "broken": broken,
        "count": result.total,
        "label": f"{broken} of {result.total}",
        "reason": result.reason,
        "break_index": result.break_index,
        "detail": detail,
        "path": path,
        "eds_ok": eds_ok,
        "eds_label": eds_label,
    }


def _initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from (lat1, lon1) to (lat2, lon2), degrees [0, 360)."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    x = sin(dlon) * cos(phi2)
    y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlon)
    return (degrees(atan2(x, y)) + 360.0) % 360.0


def _poi_card(queued_coa: Any) -> dict[str, Any] | None:
    """Display-ready Lead POI fields when ``coa.metadata.poi`` is present."""
    if queued_coa is None:
        return None
    meta = getattr(queued_coa, "metadata", None) or {}
    poi = meta.get("poi") if isinstance(meta, dict) else None
    if not isinstance(poi, dict):
        return None
    try:
        lat = float(poi["latitude"])
        lon = float(poi["longitude"])
        eta_sec = float(poi.get("eta_sec", meta.get("eta_sec", 0.0)))
    except (KeyError, TypeError, ValueError):
        return None
    raw_own = poi.get("own_platform")
    own: dict[str, Any] = raw_own if isinstance(raw_own, dict) else {}
    try:
        own_lat = float(own.get("latitude", lat))
        own_lon = float(own.get("longitude", lon))
        speed_mps = float(own.get("speed_mps", 0.0))
    except (TypeError, ValueError):
        own_lat, own_lon, speed_mps = lat, lon, 0.0
    bearing = _initial_bearing_deg(own_lat, own_lon, lat, lon)
    return {
        "latitude": lat,
        "longitude": lon,
        "bearing_deg": bearing,
        "speed_mps": speed_mps,
        "eta_sec": eta_sec,
        "method": str(poi.get("method") or ""),
    }


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
    observations = list(runtime.graph.observations)
    # Newest first so Dual-SAR / Indago just ingested stay visible after large AIS loads.
    recent_obs = list(reversed(observations))[:12]
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
        "poi_card": _poi_card(queued_coa),
        "taskings": taskings,
        "tracks": list(runtime.graph.all_tracks())[:12],
        "observations": recent_obs,
        "obs_count": len(observations),
        "inbox_depth": len([k for k in runtime.inbox if k not in runtime.acked]),
        "evidence": _evidence_urls(runtime),
        "audit_rows": list(reversed(runtime.audit.records()[-12:])),
        "ocsf_health": _ocsf_health(runtime),
        "demo_tamper": _c2().demo_tamper_enabled(),
        "has_tamper_snapshot": runtime.audit_pre_tamper is not None,
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
    """Ingest SAR / open-AIS evidence: SIA / GLINT / Dual-SAR / Indago."""
    from app.adapters.open_feed import open_feed_to_observations

    runtime = _c2().get_runtime()
    flash = ""
    error = ""
    try:
        if mode in {"indago", "open_ais", "indago_ais"}:
            # Prefer Indago DuckDB; ladder falls back to live → fixture (venue-safe).
            observations, source = open_feed_to_observations(
                "ais",
                source="auto",
                limit=40,
            )
            if not observations:
                raise ValueError("No AIS vessels to ingest")
            for obs in observations:
                runtime.graph.ingest(obs)
            flash = f"Indago AIS (open-feed): ingested {len(observations)} · source={source}"
        else:
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
    except (ValueError, OSError, TypeError, FileNotFoundError) as exc:
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


def _audit_demo_page(request: Request, *, flash: str = "", error: str = "") -> HTMLResponse:
    """Land audit demo actions on the hub (header forms are shared across screens)."""
    return _page(request, "verify/hub.html", flash=flash, error=error)


@router.post("/verify/audit/tamper", response_class=HTMLResponse)
async def verify_audit_tamper(request: Request) -> HTMLResponse:
    c2 = _c2()
    try:
        c2._require_demo_tamper()
        result = c2.get_runtime().inject_audit_tamper(index=1)
        ocsf = result.get("ocsf") or {}
        flash = (
            f"Injected 1-char tamper · {ocsf.get('summary', 'broken')} "
            f"(path={ocsf.get('reason', 'hash mismatch')})"
        )
        return _audit_demo_page(request, flash=flash)
    except HTTPException as exc:
        return _audit_demo_page(request, error=_exc_message(exc))


@router.post("/verify/audit/restore", response_class=HTMLResponse)
async def verify_audit_restore(request: Request) -> HTMLResponse:
    c2 = _c2()
    try:
        c2._require_demo_tamper()
        result = c2.get_runtime().restore_audit_tamper()
        ocsf = result.get("ocsf") or {}
        flash = f"Restored pre-tamper snapshot · {ocsf.get('summary', 'ok')}"
        return _audit_demo_page(request, flash=flash)
    except HTTPException as exc:
        return _audit_demo_page(request, error=_exc_message(exc))


@router.post("/verify/audit/reverify", response_class=HTMLResponse)
async def verify_audit_reverify(request: Request) -> HTMLResponse:
    c2 = _c2()
    try:
        c2._require_demo_tamper()
        result = c2.get_runtime().reverify_audit()
        ocsf = result.get("ocsf") or {}
        eds = result.get("eds")
        parts = [f"OCSF {ocsf.get('summary', '?')} via {result.get('path', 'sha256')}"]
        if isinstance(eds, dict):
            parts.append(f"EDS {eds.get('label', '?')}")
        flash = " · ".join(parts)
        return _audit_demo_page(request, flash=flash)
    except HTTPException as exc:
        return _audit_demo_page(request, error=_exc_message(exc))


@router.get("/")
async def root_to_verify() -> RedirectResponse:
    return RedirectResponse(url="/verify", status_code=302)
