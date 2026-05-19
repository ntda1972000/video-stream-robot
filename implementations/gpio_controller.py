import logging

from interfaces.controller_interface import BaseController

_DUTY = 80  # percent duty cycle for movement


class GPIOController(BaseController):
    def __init__(self, settings: dict):
        import RPi.GPIO as GPIO
        self._GPIO = GPIO
        self._pin_l_pwm = settings["PIN_L_PWM"]
        self._pin_l_dir = settings["PIN_L_DIR"]
        self._pin_r_pwm = settings["PIN_R_PWM"]
        self._pin_r_dir = settings["PIN_R_DIR"]
        self._pwm_hz    = settings.get("PWM_HZ", 100)
        self._pwm_l = self._pwm_r = None
        self._ready = False
        self._setup()

    def _setup(self):
        try:
            GPIO = self._GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for pin in (self._pin_l_pwm, self._pin_l_dir,
                        self._pin_r_pwm, self._pin_r_dir):
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            self._pwm_l = GPIO.PWM(self._pin_l_pwm, self._pwm_hz)
            self._pwm_r = GPIO.PWM(self._pin_r_pwm, self._pwm_hz)
            self._pwm_l.start(0)
            self._pwm_r.start(0)
            self._ready = True
            logging.info(
                "GPIOController ready — BCM L(PWM=%d DIR=%d) R(PWM=%d DIR=%d)",
                self._pin_l_pwm, self._pin_l_dir,
                self._pin_r_pwm, self._pin_r_dir,
            )
        except Exception as exc:
            logging.warning("GPIOController setup failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal drive helper
    # ------------------------------------------------------------------
    def _drive(self, left: float, right: float) -> None:
        """Drive motors. Speed in [-1.0, +1.0]; positive = forward."""
        if not self._ready:
            return
        GPIO = self._GPIO

        def _apply(dir_pin, pwm, spd):
            duty_hi = round(min(abs(spd), 1.0) * 100)
            if spd > 0.02:
                GPIO.output(dir_pin, GPIO.LOW)
                pwm.ChangeDutyCycle(duty_hi)
            elif spd < -0.02:
                GPIO.output(dir_pin, GPIO.HIGH)
                pwm.ChangeDutyCycle(100 - duty_hi)
            else:
                GPIO.output(dir_pin, GPIO.LOW)
                pwm.ChangeDutyCycle(0)

        _apply(self._pin_l_dir, self._pwm_l, left)
        _apply(self._pin_r_dir, self._pwm_r, right)

    # ------------------------------------------------------------------
    # BaseController interface
    # ------------------------------------------------------------------
    def forward(self) -> None:
        self._drive(_DUTY / 100, _DUTY / 100)

    def backward(self) -> None:
        self._drive(-_DUTY / 100, -_DUTY / 100)

    def left(self) -> None:
        self._drive(-_DUTY / 100, _DUTY / 100)

    def right(self) -> None:
        self._drive(_DUTY / 100, -_DUTY / 100)

    def stop(self) -> None:
        self._drive(0.0, 0.0)

    def cleanup(self) -> None:
        self.stop()
        try:
            if self._pwm_l:
                self._pwm_l.stop()
            if self._pwm_r:
                self._pwm_r.stop()
            self._GPIO.cleanup()
        except Exception:
            pass
        self._ready = False
