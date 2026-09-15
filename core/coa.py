"""Course-of-action (COA) transaction types."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ActionTier(int, Enum):
    TIER_0_AUTONOMOUS = 0
    TIER_1_HITL = 1
    TIER_2_DUAL_KEY = 2


class GateVerdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED_FAST = "REJECTED_FAST"
    REJECTED_OPERATOR = "REJECTED_OPERATOR"
    TIMED_OUT_FALLBACK = "TIMED_OUT_FALLBACK"


class CourseOfAction(BaseModel):
    """Executable tasking proposal with pre/post/invariant slots."""

    coa_id: str = Field(default_factory=lambda: str(uuid4()))
    tier: ActionTier = ActionTier.TIER_1_HITL
    target_entity_id: str = ""
    target_coordinates: tuple[float, float] = (0.0, 0.0)
    intent: str = "INSPECT_TARGET"
    timeout_seconds: float = 5.0
    pre_conditions: dict[str, Any] = Field(default_factory=dict)
    post_conditions: dict[str, Any] = Field(default_factory=dict)
    invariants: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    corroborating_sources: list[str] = Field(default_factory=list)
    raw_input_digest: str = ""
    speed_kt: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
