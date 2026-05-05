from dataclasses import dataclass


@dataclass(frozen=True)
class MotorPinSet:
    in1: int
    in2: int
    en: int


# GPIO pin plan (BCM numbering) for 4 motors on L298N-compatible wiring.
DEFAULT_MOTOR_PIN_CONFIG = [
    MotorPinSet(in1=5, in2=6, en=12),
    MotorPinSet(in1=13, in2=19, en=26),
    MotorPinSet(in1=16, in2=20, en=21),
    MotorPinSet(in1=23, in2=24, en=25),
]

# 4 web-controlled digital output pins.
DEFAULT_IO_PINS = [17, 27, 22, 4]
