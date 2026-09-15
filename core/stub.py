"""In-memory stub effector for tests and CI."""

from __future__ import annotations

from core.coa import CourseOfAction
from core.proxy import EffectorProxy
from core.schema import ExecutionReceipt


class StubEffector(EffectorProxy):
    def __init__(self) -> None:
        self.dispatched: list[CourseOfAction] = []
        self.station_keeps: int = 0

    async def dispatch(self, coa: CourseOfAction) -> ExecutionReceipt:
        self.dispatched.append(coa)
        receipt = ExecutionReceipt(
            coa_id=coa.coa_id,
            status="ACCEPTED",
            message="stub_dispatch",
            telemetry={"target": coa.target_coordinates},
        )
        receipt.seal()
        return receipt

    async def emergency_station_keep(self) -> ExecutionReceipt:
        self.station_keeps += 1
        receipt = ExecutionReceipt(
            coa_id="",
            status="STATION_KEEP",
            message="stub_station_keep",
        )
        receipt.seal()
        return receipt
