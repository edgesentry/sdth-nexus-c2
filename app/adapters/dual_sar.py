"""Dual-SAR Multi-Fidelity Corroborator (issue #56).

Jointly corroborate GLINT macro anomalies with SIA micro OBB metrology into
composite CandidateEvents. When GLINT is unreachable, fail safe to SIA /
Singapore Strait golden fixture without interrupting ingress.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.glint_client import resolve_glint_events
from app.adapters.sar_candidate_event import (
    CandidateEvent,
    CandidateEventBoundingBox,
)
from app.adapters.sentinel_imagery import resolve_sentinel_events
from core.ontology import haversine_m

DEFAULT_ALIGN_M = 3_000.0
CONFIDENCE_BOOST = 0.1
CONFIDENCE_CAP = 0.98

STATUS_CORROBORATED = "corroborated"
STATUS_SIA_ONLY = "sia_only"

SOURCE_DUAL_SAR = "dual_sar"
SOURCE_SIA_ONLY = "sia_only"

COMPOSITE_SOURCE_ID = "DUAL_SAR"


def point_in_bbox(
    latitude: float,
    longitude: float,
    bbox: CandidateEventBoundingBox,
) -> bool:
    return (
        bbox.min_lat <= latitude <= bbox.max_lat
        and bbox.min_lon <= longitude <= bbox.max_lon
    )


def sector_aligns(
    macro: CandidateEvent,
    micro: CandidateEvent,
    *,
    max_align_m: float = DEFAULT_ALIGN_M,
) -> bool:
    """True when micro lies in macro sector (bbox) or within ``max_align_m``."""
    if macro.bounding_box is not None and point_in_bbox(
        micro.location.latitude,
        micro.location.longitude,
        macro.bounding_box,
    ):
        return True

    distance_m = haversine_m(
        macro.location.latitude,
        macro.location.longitude,
        micro.location.latitude,
        micro.location.longitude,
    )
    if distance_m <= max_align_m:
        return True

    if (
        macro.area_id
        and micro.area_id
        and macro.area_id == micro.area_id
        and distance_m <= max_align_m * 2.0
    ):
        return True

    return False


def _nearest_macro(
    macros: list[CandidateEvent],
    micro: CandidateEvent,
    *,
    max_align_m: float,
) -> CandidateEvent | None:
    aligned = [m for m in macros if sector_aligns(m, micro, max_align_m=max_align_m)]
    if not aligned:
        return None
    return min(
        aligned,
        key=lambda m: haversine_m(
            m.location.latitude,
            m.location.longitude,
            micro.location.latitude,
            micro.location.longitude,
        ),
    )


def fuse_pair(macro: CandidateEvent, micro: CandidateEvent) -> CandidateEvent:
    """SIA micro geometry + GLINT macro context, with elevated confidence."""
    boosted = min(
        CONFIDENCE_CAP,
        max(macro.confidence, micro.confidence) + CONFIDENCE_BOOST,
    )
    vessel_est = int(
        macro.attributes.get("vessel_count_est")
        or micro.attributes.get("vessel_count_est")
        or 0
    )
    attrs: dict[str, Any] = {
        **micro.attributes,
        "ingress": "dual_sar",
        "dual_sar_status": STATUS_CORROBORATED,
        "macro_event_id": macro.event_id,
        "macro_source_id": macro.source_id,
        "macro_event_type": macro.event_type,
        "micro_event_id": micro.event_id,
        "micro_source_id": micro.source_id,
        "schema_version": "1.3.0",
    }
    if vessel_est:
        attrs["vessel_count_est"] = vessel_est
    if macro.area_id and not attrs.get("area_id"):
        attrs["area_id"] = macro.area_id

    return micro.model_copy(
        update={
            "source_id": COMPOSITE_SOURCE_ID,
            "area_id": micro.area_id or macro.area_id,
            "confidence": boosted,
            "attributes": attrs,
        }
    )


def _annotate_sia_only(micro: CandidateEvent) -> CandidateEvent:
    attrs: dict[str, Any] = {
        **micro.attributes,
        "ingress": micro.attributes.get("ingress") or "sentinel_imagery",
        "dual_sar_status": STATUS_SIA_ONLY,
    }
    return micro.model_copy(update={"attributes": attrs})


def corroborate(
    macros: list[CandidateEvent],
    micros: list[CandidateEvent],
    *,
    max_align_m: float = DEFAULT_ALIGN_M,
) -> list[CandidateEvent]:
    """Fuse each micro with nearest aligned macro; else mark sia_only."""
    if not macros:
        return [_annotate_sia_only(m) for m in micros]

    out: list[CandidateEvent] = []
    for micro in micros:
        macro = _nearest_macro(macros, micro, max_align_m=max_align_m)
        if macro is None:
            out.append(_annotate_sia_only(micro))
        else:
            out.append(fuse_pair(macro, micro))
    return out


def resolve_dual_sar_events(
    *,
    pull: bool = False,
    use_fixture: bool = False,
    max_align_m: float = DEFAULT_ALIGN_M,
    glint_base_url: str | None = None,
    glint_timeout_s: float | None = None,
    glint_fixture_path: Path | None = None,
    sia_base_url: str | None = None,
    sia_scan: str | None = None,
    sia_timeout_s: float | None = None,
    sia_fixture_path: Path | None = None,
    run_cv: dict[str, Any] | None = None,
) -> tuple[list[CandidateEvent], str]:
    """Resolve GLINT × SIA and corroborate.

    Returns ``(events, source)`` where source is ``dual_sar`` when at least one
    pair corroborates, else the SIA resolve source (fail-safe) or ``sia_only``.
    """
    if not pull and not use_fixture and run_cv is None:
        raise ValueError("Provide pull_dual_sar=true, dual_sar=true, or run_cv={...}")

    micros, sia_source = resolve_sentinel_events(
        pull_upstream=pull,
        run_cv=run_cv,
        use_fixture=use_fixture or pull,
        base_url=sia_base_url,
        scan=sia_scan,
        timeout_s=sia_timeout_s,
        fixture_path=sia_fixture_path,
    )
    if not micros:
        return [], sia_source

    # Prefer live GLINT when pulling; otherwise (or on failure) use assumed fixture.
    glint_fixture = use_fixture or pull or run_cv is not None
    macros: list[CandidateEvent] = []
    try:
        macros, _glint_source = resolve_glint_events(
            pull_upstream=pull,
            use_fixture=glint_fixture,
            base_url=glint_base_url,
            timeout_s=glint_timeout_s,
            fixture_path=glint_fixture_path,
        )
    except ValueError:
        macros = []

    fused = corroborate(macros, micros, max_align_m=max_align_m)
    if any(e.attributes.get("dual_sar_status") == STATUS_CORROBORATED for e in fused):
        return fused, SOURCE_DUAL_SAR
    if not macros:
        return fused, SOURCE_SIA_ONLY if sia_source == "fixture" else sia_source
    return fused, SOURCE_SIA_ONLY
