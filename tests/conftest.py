"""
tests/conftest.py — Hardware module mocking for non-Pi dev machines.

Patches sys.modules BEFORE any test module imports app.py or implementations,
so that RPi.GPIO, picamera2, cv2, and serial never cause ImportError on
non-Pi hosts.
"""
import sys
from unittest.mock import MagicMock

# ── RPi.GPIO ──────────────────────────────────────────────────────────────
_rpi_mock = MagicMock()
_gpio_mock = MagicMock()
_rpi_mock.GPIO = _gpio_mock
sys.modules.setdefault("RPi", _rpi_mock)
sys.modules.setdefault("RPi.GPIO", _gpio_mock)

# ── picamera2 ─────────────────────────────────────────────────────────────
sys.modules.setdefault("picamera2", MagicMock())

# ── cv2 (OpenCV) ──────────────────────────────────────────────────────────
sys.modules.setdefault("cv2", MagicMock())

# ── serial (pyserial) ─────────────────────────────────────────────────────
sys.modules.setdefault("serial", MagicMock())

# ── pynmea2 ───────────────────────────────────────────────────────────────
sys.modules.setdefault("pynmea2", MagicMock())
