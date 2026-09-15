"""Level 3: Raspberry Pi GPIO effector (graceful no-op without hardware)."""

from __future__ import annotations

from core.coa import CourseOfAction
from core.proxy import EffectorProxy
from core.schema import ExecutionReceipt


class RaspiHardwareAdapter(EffectorProxy):
    """Drive LED/servo on approve when GPIO is available; otherwise log-only."""

    def __init__(self, *, led_pin: int = 17, servo_pin: int = 18) -> None:
        self.led_pin = led_pin
        self.servo_pin = servo_pin
        self._gpio = None
        try:
            import RPi.GPIO as GPIO  # type: ignore

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.led_pin, GPIO.OUT)
            GPIO.setup(self.servo_pin, GPIO.OUT)
            self._gpio = GPIO
        except Exception:
            self._gpio = None

    async def dispatch(self, coa: CourseOfAction) -> ExecutionReceipt:
        hardware = "unavailable"
        if self._gpio is not None:
            self._gpio.output(self.led_pin, True)
            hardware = f"led:{self.led_pin}/servo:{self.servo_pin}"
        receipt = ExecutionReceipt(
            coa_id=coa.coa_id,
            status="DISPATCHED",
            message="raspi_dispatch",
            telemetry={"hardware": hardware, "target": coa.target_coordinates},
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
