"""Course-of-action (COA) transaction types."""

from __future__ import annotations

from enum import Enum, StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.kinematics import LeadPursuitPOI

# Intents that replace static historical coords with a lead-pursuit POI (#58).
LEAD_PURSUIT_INTENTS = frozenset(
    {"APPROACH_PATROL", "CUE_AND_IDENTIFY", "GNSS_DENIAL_AND_GBAD_CUE"}
)


class ActionTier(int, Enum):
    TIER_0_AUTONOMOUS = 0
    TIER_1_HITL = 1
    TIER_2_DUAL_KEY = 2


class GateVerdict(StrEnum):
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

    def apply_lead_pursuit(self, poi: LeadPursuitPOI) -> None:
        """Set ``target_coordinates`` to the POI and expose ETA in metadata."""
        self.target_coordinates = (poi.latitude, poi.longitude)
        self.metadata["poi"] = poi.as_metadata()
        self.metadata["contact_coordinates"] = [
            poi.contact_latitude,
            poi.contact_longitude,
        ]
        self.metadata["eta_sec"] = round(poi.eta_sec, 3)
