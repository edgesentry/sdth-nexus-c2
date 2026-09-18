"""Level 3: Raspberry Pi GPIO effector (graceful no-op without hardware)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from core.coa import CourseOfAction
from core.proxy import EffectorProxy
from core.schema import ExecutionReceipt

# Truthy values for RASPI_ACK_BLINK / RASPI_GPIO (issue #20).
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def raspi_ack_blink_enabled(env: dict[str, str] | None = None) -> bool:
    """Opt-in secondary proof: blink GPIO on recipient ack when set."""
    source = env if env is not None else os.environ
    for key in ("RASPI_ACK_BLINK", "RASPI_GPIO"):
        raw = (source.get(key) or "").strip().lower()
        if raw in _TRUTHY:
            return True
    return False


def resolve_led_pin(explicit: int | None = None, env: dict[str, str] | None = None) -> int:
    if explicit is not None:
        return explicit
    source = env if env is not None else os.environ
    raw = (source.get("RASPI_LED_PIN") or "").strip()
    if raw:
        return int(raw)
    return 17


class RaspiHardwareAdapter(EffectorProxy):
    """Drive LED on approve / ack when GPIO is available; otherwise log-only."""

    def __init__(
        self,
        *,
        led_pin: int | None = None,
        servo_pin: int = 18,
        gpio: Any | None = None,
        auto_init: bool = True,
    ) -> None:
        self.led_pin = resolve_led_pin(led_pin)
        self.servo_pin = servo_pin
        self._gpio: Any | None = None
        if gpio is not None:
            self._gpio = gpio
            self._setup_pins()
        elif auto_init:
            self._try_import_gpio()

    def _try_import_gpio(self) -> None:
        try:
            import RPi.GPIO as GPIO  # type: ignore[import-untyped]

            self._gpio = GPIO
            self._setup_pins()
        except Exception:
            self._gpio = None

    def _setup_pins(self) -> None:
        if self._gpio is None:
            return
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setup(self.led_pin, self._gpio.OUT)
        self._gpio.setup(self.servo_pin, self._gpio.OUT)

    @property
    def hardware_available(self) -> bool:
        return self._gpio is not None

    async def blink(
        self,
        *,
        pulses: int = 2,
        on_s: float = 0.12,
        off_s: float = 0.12,
    ) -> dict[str, Any]:
        """Pulse LED for Ack / dispatch proof. No-op when GPIO is missing."""
        if self._gpio is None:
            return {
                "hardware": "unavailable",
                "blinked": False,
                "led_pin": self.led_pin,
                "pulses": 0,
            }
        for _ in range(max(pulses, 0)):
            self._gpio.output(self.led_pin, True)
            await asyncio.sleep(on_s)
            self._gpio.output(self.led_pin, False)
            await asyncio.sleep(off_s)
        return {
            "hardware": f"led:{self.led_pin}",
            "blinked": True,
            "led_pin": self.led_pin,
            "pulses": pulses,
        }

    async def dispatch(self, coa: CourseOfAction) -> ExecutionReceipt:
        blink_tel = await self.blink(pulses=1, on_s=0.2, off_s=0.05)
        receipt = ExecutionReceipt(
            coa_id=coa.coa_id,
            status="DISPATCHED",
            message="raspi_dispatch",
            telemetry={
                **blink_tel,
                "target": list(coa.target_coordinates),
            },
        )
        receipt.seal()
        return receipt

    async def emergency_station_keep(self) -> ExecutionReceipt:
        if self._gpio is not None:
            self._gpio.output(self.led_pin, False)
        receipt = ExecutionReceipt(
            coa_id="",
            status="STATION_KEEP",
            message="raspi_station_keep",
            telemetry={"hardware": "led_off" if self._gpio else "unavailable"},
        )
        receipt.seal()
        return receipt


async def maybe_blink_on_ack(
    *,
    enabled: bool | None = None,
    adapter: RaspiHardwareAdapter | None = None,
) -> dict[str, Any] | None:
    """
    Optional GPIO blink for POST /api/recipient/ack (issue #20).

    Returns None when the feature is disabled; otherwise blink telemetry
    (blinked=False when RPi.GPIO / hardware is absent).
    """
    if enabled is None:
        enabled = raspi_ack_blink_enabled()
    if not enabled:
        return None
    hardware = adapter or RaspiHardwareAdapter()
    return await hardware.blink()
