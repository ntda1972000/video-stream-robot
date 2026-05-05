import logging
from importlib import import_module
from typing import Dict


class GPIOBackend:
    """Hardware abstraction to allow GPIO simulation off-device."""

    def setup_output(self, pin: int) -> None:
        raise NotImplementedError

    def setup_pwm(self, pin: int, frequency_hz: int) -> None:
        raise NotImplementedError

    def write_output(self, pin: int, high: bool) -> None:
        raise NotImplementedError

    def set_pwm_duty(self, pin: int, duty_percent: float) -> None:
        raise NotImplementedError


class MockGPIOBackend(GPIOBackend):
    def __init__(self):
        self.outputs: Dict[int, bool] = {}
        self.pwm: Dict[int, float] = {}

    def setup_output(self, pin: int) -> None:
        self.outputs.setdefault(pin, False)

    def setup_pwm(self, pin: int, frequency_hz: int) -> None:
        self.pwm.setdefault(pin, 0.0)

    def write_output(self, pin: int, high: bool) -> None:
        self.outputs[pin] = bool(high)

    def set_pwm_duty(self, pin: int, duty_percent: float) -> None:
        self.pwm[pin] = max(0.0, min(100.0, float(duty_percent)))


class RPiGPIOBackend(GPIOBackend):
    def __init__(self):
        self._gpio = import_module("RPi.GPIO")
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setwarnings(False)
        self._pwm_channels: Dict[int, object] = {}

    def setup_output(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.OUT)
        self._gpio.output(pin, self._gpio.LOW)

    def setup_pwm(self, pin: int, frequency_hz: int) -> None:
        self.setup_output(pin)
        pwm = self._gpio.PWM(pin, frequency_hz)
        pwm.start(0)
        self._pwm_channels[pin] = pwm

    def write_output(self, pin: int, high: bool) -> None:
        self._gpio.output(pin, self._gpio.HIGH if high else self._gpio.LOW)

    def set_pwm_duty(self, pin: int, duty_percent: float) -> None:
        pwm = self._pwm_channels.get(pin)
        if pwm is None:
            raise RuntimeError(f"PWM pin {pin} is not initialized")
        pwm.ChangeDutyCycle(max(0.0, min(100.0, float(duty_percent))))


def create_gpio_backend() -> GPIOBackend:
    try:
        backend = RPiGPIOBackend()
        logging.info("Using RPi.GPIO backend")
        return backend
    except Exception as exc:
        logging.warning("Falling back to mock GPIO backend: %s", exc)
        return MockGPIOBackend()
