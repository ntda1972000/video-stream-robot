from dataclasses import dataclass


@dataclass(frozen=True)
class MotorPinSet:
    in1: int
    in2: int
    en: int


# Pin plan (BCM numbering): 4 motors + 4 enable PWM channels for L298N-based setup.
# Left side motors: index 0 and 2
# Right side motors: index 1 and 3
DEFAULT_MOTOR_PIN_CONFIG = [
    MotorPinSet(in1=5, in2=6, en=12),
    MotorPinSet(in1=13, in2=19, en=26),
    MotorPinSet(in1=16, in2=20, en=21),
    MotorPinSet(in1=23, in2=24, en=25),
]

# 4 web-controlled digital outputs (BCM numbering).
DEFAULT_IO_PINS = [17, 27, 22, 4]
