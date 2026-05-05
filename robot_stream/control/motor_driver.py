from typing import Iterable

from robot_stream.control.gpio_adapter import GPIOBackend
from robot_stream.control.pin_layout import MotorPinSet


class L298NFourMotorController:
    """Controls 4 DC motors using L298N-compatible direction + PWM pins."""

    def __init__(self, backend: GPIOBackend, motor_pins: Iterable[MotorPinSet], pwm_frequency_hz: int = 1000):
        self._backend = backend
        self._motor_pins = list(motor_pins)
        self._pwm_frequency_hz = pwm_frequency_hz
        self._setup()

    def _setup(self) -> None:
        for pins in self._motor_pins:
            self._backend.setup_output(pins.in1)
            self._backend.setup_output(pins.in2)
            self._backend.setup_pwm(pins.en, self._pwm_frequency_hz)
            self._backend.write_output(pins.in1, False)
            self._backend.write_output(pins.in2, False)
            self._backend.set_pwm_duty(pins.en, 0)

    def _set_motor_speed(self, motor_index: int, speed: float) -> None:
        pins = self._motor_pins[motor_index]
        clamped = max(-1.0, min(1.0, float(speed)))
        duty = abs(clamped) * 100.0

        if clamped > 0:
            self._backend.write_output(pins.in1, True)
            self._backend.write_output(pins.in2, False)
        elif clamped < 0:
            self._backend.write_output(pins.in1, False)
            self._backend.write_output(pins.in2, True)
        else:
            self._backend.write_output(pins.in1, False)
            self._backend.write_output(pins.in2, False)

        self._backend.set_pwm_duty(pins.en, duty)

    def drive(self, x: float, y: float) -> None:
        """Map joystick x/y input to differential left/right motor speeds."""
        turn = max(-1.0, min(1.0, float(x)))
        throttle = max(-1.0, min(1.0, float(y)))

        left_speed = max(-1.0, min(1.0, throttle + turn))
        right_speed = max(-1.0, min(1.0, throttle - turn))

        # Motors 0 and 2 are left side, 1 and 3 are right side.
        self._set_motor_speed(0, left_speed)
        self._set_motor_speed(2, left_speed)
        self._set_motor_speed(1, right_speed)
        self._set_motor_speed(3, right_speed)

    def stop_all(self) -> None:
        for index in range(len(self._motor_pins)):
            self._set_motor_speed(index, 0.0)
