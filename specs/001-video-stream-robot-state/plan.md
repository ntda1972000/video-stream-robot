# Implementation Plan: Video Stream Robot — HAL Refactoring & New Features

**Branch**: `develop` | **Date**: 2026-05-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-video-stream-robot-state/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Refactor the existing monolithic `app.py` robot firmware into a modular, hardware-abstracted architecture. Introduce abstract base interfaces for Camera, Controller, and GPS components; provide concrete implementations (PiCamera, IPCamera, USBCamera, GPIOController, SerialController, SerialGPS); add a `config.py` hardware selection layer; and add GPS coordinates + minimap UI to the dashboard.

## Technical Context

**Language/Version**: Python 3.11+ (system Python on Raspberry Pi OS Bookworm; `.venv` managed)

**Primary Dependencies**:
- Flask 3.x + Gunicorn (HTTPS server)
- RPi.GPIO / rpi-lgpio (GPIO motor control — Pi only)
- picamera2 via apt (`python3-picamera2`) — Pi CSI camera on Bookworm/libcamera
- OpenCV `opencv-python-headless` — IP camera (RTSP) and USB camera (`cv2.VideoCapture`)
- pyserial — SerialController (Arduino commands) and SerialGPS (NMEA serial read)
- pynmea2 — NMEA 0183 sentence parsing for SerialGPS
- Leaflet.js 1.9.4 via CDN — browser minimap with OpenStreetMap tiles
- MediaMTX v1.9.0 binary (RTSP→WebRTC gateway, spawned as subprocess)
- FFmpeg (video encoding in publisher.py)

**Storage**: `settings.json` flat file (resolution, fps, rotation, motor_trim, io_devices)

**Testing**: pytest + `unittest.mock` / `pytest-mock`; `RPi.GPIO`, `picamera2`, and `serial.Serial` mocked via `sys.modules` patching in `tests/conftest.py` to enable tests on non-Pi dev machines

**Target Platform**: Raspberry Pi 3B+/4/5 (arm64/armv7, Raspberry Pi OS Bookworm) + Linux x86_64 dev machines

**Project Type**: Embedded IoT web-service (single-process Flask+Gunicorn HTTPS server)

**Performance Goals**: Live WebRTC video at 20–30 fps; motor command round-trip < 100 ms; GPS poll interval ≤ 1 s

**Constraints**: Single-operator device; no auth; self-signed TLS; GPIO unavailable on non-Pi hosts (graceful no-op required); hardware encoder disabled due to VCHIQ deadlock; max 500 kbps video bitrate

**Scale/Scope**: 1 operator, 1 robot, ~10 source files after refactor; all logic runs on a single Pi process

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution is a placeholder template with no project-specific principles ratified. No constitution gates apply. All design decisions follow the spec requirements and Python/Flask best practices.

**Post-Phase-1 Re-check**: No violations found. The HAL interfaces use standard Python `abc.ABC` / `abstractmethod` patterns — no over-engineering. Factory logic in `app.py` is a simple conditional block matching the scale of a single-operator IoT device.

## Project Structure

### Documentation (this feature)

```text
specs/001-video-stream-robot-state/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# Repository root (single-project embedded web service)
app.py                      # Flask app + Gunicorn entry; factory instantiation only
publisher.py                # Camera-to-RTSP subprocess (rpicam-vid | FFmpeg)
config.py                   # Hardware selection: CAMERA_TYPE, CONTROLLER_TYPE, GPS_TYPE + _SETTINGS
settings.json               # Runtime-persisted settings (resolution, fps, rotation, etc.)

interfaces/
├── camera_interface.py     # BaseCamera ABC (get_frame)
├── controller_interface.py # BaseController ABC (forward/backward/left/right/stop)
└── gps_interface.py        # BaseGPS ABC (get_coordinates)

implementations/
├── pi_camera.py            # PiCamera — picamera2 (CSI, libcamera)
├── ip_camera.py            # IPCamera — OpenCV RTSP
├── usb_camera.py           # USBCamera — OpenCV V4L2 device index
├── gpio_controller.py      # GPIOController — L298N H-bridge via RPi.GPIO
├── serial_controller.py    # SerialController — Arduino serial commands
└── serial_gps.py           # SerialGPS — NMEA via pyserial + pynmea2

templates/
├── dashboard.html          # Main control UI (joystick, video, I/O, minimap)
└── index.html              # Legacy bidirectional stream page (not routed)

tests/
├── unit/
│   ├── test_config.py
│   ├── test_gpio_controller.py   # mocked RPi.GPIO
│   ├── test_serial_controller.py # mocked serial port
│   └── test_serial_gps.py        # mocked serial + NMEA fixtures
└── integration/
    └── test_api.py               # Flask test client, mocked hardware

mediamtx/                   # MediaMTX binary + reference config
setup_robot.sh              # One-shot setup script
robot-stream.service        # systemd unit
```

**Structure Decision**: Single-project layout. HAL lives in `interfaces/` (ABCs) and `implementations/` (concrete classes) at the repo root alongside `app.py`. No separate package or build step needed — the Pi runs directly from the repo directory with `.venv`. Tests under `tests/` use pytest with `unittest.mock` to isolate hardware dependencies.

## Complexity Tracking

> No constitution violations. No complexity justification required.
