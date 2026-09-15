"""Effector proxy abstraction (northbound)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.coa import CourseOfAction
from core.schema import ExecutionReceipt


class EffectorProxy(ABC):
    @abstractmethod
    async def dispatch(self, coa: CourseOfAction) -> ExecutionReceipt:
        raise NotImplementedError

    @abstractmethod
    async def emergency_station_keep(self) -> ExecutionReceipt:
        raise NotImplementedError
