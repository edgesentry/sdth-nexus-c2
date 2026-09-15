"""Domain-agnostic schemas for observations, decisions, and execution receipts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_hex(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


class Observation(BaseModel):
    """Spatio-temporal observation from any sensor modality."""

    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    entity_hint: str = ""
    latitude: float
    longitude: float
    altitude_m: float | None = None
    speed_mps: float = 0.0
    heading_deg: float | None = None
    confidence: float = 0.5
    observed_at: datetime = Field(default_factory=utc_now)
    modality: str = "generic"
    attributes: dict[str, Any] = Field(default_factory=dict)
    raw_digest: str = ""

    def ensure_digest(self) -> str:
        if self.raw_digest:
            return self.raw_digest
        body = canonical_json(self.model_dump(mode="json", exclude={"raw_digest"}))
        self.raw_digest = sha256_hex(body)
        return self.raw_digest


class DecisionToken(BaseModel):
    token_id: str = Field(default_factory=lambda: str(uuid4()))
    coa_id: str
    verdict: str
    issued_at: datetime = Field(default_factory=utc_now)
    operator_id: str | None = None
    reason: str | None = None
    digest: str = ""

    def seal(self) -> str:
        body = canonical_json(self.model_dump(mode="json", exclude={"digest"}))
        self.digest = sha256_hex(body)
        return self.digest


class ExecutionReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    coa_id: str
    status: str
    message: str = ""
    telemetry: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=utc_now)
    digest: str = ""

    def seal(self) -> str:
        body = canonical_json(self.model_dump(mode="json", exclude={"digest"}))
        self.digest = sha256_hex(body)
        return self.digest
