"""Tiered autonomy policy loaded from YAML (generic thresholds only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.coa import ActionTier, CourseOfAction
from core.interlock import DeterministicInterlock


class TieredPolicy:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        gate = raw.get("gate", {})
        tiers = raw.get("tiers", {})
        interlock = raw.get("interlock", {})
        self.default_timeout_seconds = float(gate.get("default_timeout_seconds", 5.0))
        self.confidence_auto_approve_min = float(tiers.get("confidence_auto_approve_min", 0.95))
        self.min_corroborating_sources_tier1 = int(tiers.get("min_corroborating_sources_tier1", 2))
        self.inspect_default_tier = int(tiers.get("inspect_default_tier", 1))
        self.interlock = DeterministicInterlock(
            forbidden_zones=list(interlock.get("forbidden_zones", [])),
            max_speed_kt=float(interlock.get("max_speed_kt", 40.0)),
            reject_null_coordinates=bool(interlock.get("reject_null_coordinates", True)),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> TieredPolicy:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(data)

    def resolve_tier(self, coa: CourseOfAction) -> ActionTier:
        if coa.tier == ActionTier.TIER_2_DUAL_KEY:
            return ActionTier.TIER_2_DUAL_KEY
        if (
            coa.confidence >= self.confidence_auto_approve_min
            and len(coa.corroborating_sources) >= self.min_corroborating_sources_tier1
            and coa.intent in {"OBSERVE_ONLY", "STATION_KEEP"}
        ):
            return ActionTier.TIER_0_AUTONOMOUS
        if coa.tier == ActionTier.TIER_0_AUTONOMOUS:
            return ActionTier.TIER_0_AUTONOMOUS
        return ActionTier.TIER_1_HITL

    def apply_defaults(self, coa: CourseOfAction) -> CourseOfAction:
        if coa.timeout_seconds <= 0:
            coa.timeout_seconds = self.default_timeout_seconds
        coa.tier = self.resolve_tier(coa)
        if "fail_safe" not in coa.invariants:
            coa.invariants["fail_safe"] = "STATION_KEEP"
        return coa
