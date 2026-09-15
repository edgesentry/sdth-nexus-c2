"""Latency-bounded HITL gate with fail-closed fallback."""

from __future__ import annotations

import asyncio

from core.coa import ActionTier, CourseOfAction, GateVerdict
from core.interlock import DeterministicInterlock
from core.schema import DecisionToken


class LatencyBoundedGate:
    def __init__(
        self,
        *,
        timeout_sec: float = 5.0,
        interlock: DeterministicInterlock | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        self.interlock = interlock or DeterministicInterlock()

    def verify_deterministic_interlocks(self, coa: CourseOfAction) -> tuple[bool, str | None]:
        return self.interlock.verify(coa)

    async def evaluate(
        self,
        coa: CourseOfAction,
        operator_input_queue: asyncio.Queue[str] | None = None,
    ) -> tuple[GateVerdict, DecisionToken]:
        valid, reason = self.verify_deterministic_interlocks(coa)
        if not valid:
            token = DecisionToken(
                coa_id=coa.coa_id,
                verdict=GateVerdict.REJECTED_FAST.value,
                reason=reason,
            )
            token.seal()
            return GateVerdict.REJECTED_FAST, token

        if coa.tier == ActionTier.TIER_0_AUTONOMOUS:
            token = DecisionToken(
                coa_id=coa.coa_id,
                verdict=GateVerdict.APPROVED.value,
                operator_id="autonomous",
                reason="tier0_auto",
            )
            token.seal()
            return GateVerdict.APPROVED, token

        if coa.tier == ActionTier.TIER_2_DUAL_KEY:
            # Phase 1: dual-key not implemented — require HITL path with explicit deny if no queue
            pass

        timeout = coa.timeout_seconds if coa.timeout_seconds > 0 else self.timeout_sec
        if operator_input_queue is None:
            token = DecisionToken(
                coa_id=coa.coa_id,
                verdict=GateVerdict.TIMED_OUT_FALLBACK.value,
                reason="no_operator_channel",
            )
            token.seal()
            return GateVerdict.TIMED_OUT_FALLBACK, token

        try:
            decision = await asyncio.wait_for(operator_input_queue.get(), timeout=timeout)
            decision_norm = str(decision).strip().lower()
            if decision_norm in {"y", "yes", "approve", "approved"}:
                token = DecisionToken(
                    coa_id=coa.coa_id,
                    verdict=GateVerdict.APPROVED.value,
                    operator_id="operator",
                    reason="operator_approve",
                )
                token.seal()
                return GateVerdict.APPROVED, token
            token = DecisionToken(
                coa_id=coa.coa_id,
                verdict=GateVerdict.REJECTED_OPERATOR.value,
                operator_id="operator",
                reason="operator_deny",
            )
            token.seal()
            return GateVerdict.REJECTED_OPERATOR, token
        except TimeoutError:
            token = DecisionToken(
                coa_id=coa.coa_id,
                verdict=GateVerdict.TIMED_OUT_FALLBACK.value,
                reason="latency_timeout",
            )
            token.seal()
            return GateVerdict.TIMED_OUT_FALLBACK, token
