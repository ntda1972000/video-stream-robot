# Quickstart: Video Stream Robot

**Phase 1 output for**: `specs/001-video-stream-robot-state/plan.md`
**Date**: 2026-05-19

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Raspberry Pi | 3B+, 4, or 5 running Raspberry Pi OS Bookworm (64-bit recommended) |
| Pi CSI Camera | OV5647 or compatible (or use IP/USB camera via `config.py`) |
| Python | 3.11+ (system Python on Bookworm) |
| System packages | `ffmpeg`, `openssl`, `curl`, `python3-venv`, `python3-picamera2`, `alsa-utils`, `v4l-utils` |
| MediaMTX binary | v1.9.0 at `~/rc-car/mediamtx` (installed by `setup_robot.sh`) |

---

## 1. Initial Setup (first time only)

```bash
git clone -b develop https://github.com/ntda1972000/video-stream-robot.git
cd video-stream-robot
chmod +x setup_robot.sh
./setup_robot.sh
```

The setup script installs system packages, creates `.venv`, downloads MediaMTX, and optionally installs Tailscale and systemd autostart.

**Additional packages required by the HAL refactoring** (run after `setup_robot.sh`):

```bash
.venv/bin/pip install pyserial pynmea2 pytest pytest-mock

# If using IP camera or USB camera:
.venv/bin/pip install opencv-python-headless
```

---

## 2. Configure Hardware Profile (`config.py`)

Create `config.py` in the repo root (not committed — add to `.gitignore`):

```python
# config.py — Hardware selection

# ── Camera ──────────────────────────────────────────────────
CAMERA_TYPE = "PI_CAMERA"        # "PI_CAMERA" | "IP_CAMERA" | "USB_CAMERA"

CAMERA_SETTINGS = {
    "PI_CAMERA":  {"RESOLUTION": (640, 480)},
    "IP_CAMERA":  {"RTSP_URL": "rtsp://192.168.1.100:8554/stream"},
    "USB_CAMERA": {"DEVICE_INDEX": 0},
}

# ── Controller ───────────────────────────────────────────────
CONTROLLER_TYPE = "GPIO_CONTROLLER"   # "GPIO_CONTROLLER" | "SERIAL_CONTROLLER"

CONTROLLER_SETTINGS = {
    "GPIO_CONTROLLER": {
        "PIN_L_PWM": 17, "PIN_L_DIR": 27,
        "PIN_R_PWM": 22, "PIN_R_DIR": 23,
        "PWM_HZ": 100,
    },
    "SERIAL_CONTROLLER": {"PORT": "/dev/ttyUSB0", "BAUDRATE": 9600},
}

# ── GPS ──────────────────────────────────────────────────────
GPS_TYPE = "NONE"                # "SERIAL_GPS" | "NONE"

GPS_SETTINGS = {
    "SERIAL_GPS": {"PORT": "/dev/ttyS0", "BAUDRATE": 9600},
}
```

---

## 3. Start the Server

```bash
nohup .venv/bin/python app.py > server.log 2>&1 &
```

Then open in a browser **(accept the self-signed certificate warning)**:

```
https://<pi-ip>:5000
```

---

## 4. Verify the Stream

1. Open `https://<pi-ip>:5000` → dashboard loads.
2. Video stream connects automatically (WebRTC/WHEP).
3. Check `server.log` for `MediaMTX started` and `Publisher started`.

---

## 5. Development Setup (non-Pi machine)

```bash
# Clone repo
git clone -b develop https://github.com/ntda1972000/video-stream-robot.git
cd video-stream-robot

# Create venv (Python 3.11+)
python3 -m venv .venv
.venv/bin/pip install flask gunicorn pyserial pynmea2 opencv-python-headless pytest pytest-mock

# picamera2 is not installable on non-Pi — mocked in tests/conftest.py
# RPi.GPIO is not installable on non-Pi — mocked in tests/conftest.py

# Set a dev-compatible config.py
cat > config.py << 'EOF'
CAMERA_TYPE = "USB_CAMERA"
CAMERA_SETTINGS = {"USB_CAMERA": {"DEVICE_INDEX": 0}}
CONTROLLER_TYPE = "SERIAL_CONTROLLER"
CONTROLLER_SETTINGS = {"SERIAL_CONTROLLER": {"PORT": "/dev/ttyUSB0", "BAUDRATE": 9600}}
GPS_TYPE = "NONE"
GPS_SETTINGS = {}
EOF

# Run tests
.venv/bin/pytest tests/ -v
```

---

## 6. Add a New Camera Implementation

1. Create `implementations/my_camera.py`:
   ```python
   from interfaces.camera_interface import BaseCamera

   class MyCamera(BaseCamera):
       def __init__(self, settings: dict):
           ...
       def get_frame(self) -> bytes:
           ...
   ```
2. Add `"MY_CAMERA"` to `CAMERA_SETTINGS` in `config.py`.
3. Add the factory branch in `app.py` (analogous to existing branches).

---

## 7. Remote Access via Tailscale

```bash
sudo tailscale up                   # authenticate
tailscale ip -4                     # get Tailscale IP
# Open: https://<tailscale-ip>:5000
```

---

## 8. Autostart via systemd

```bash
sudo cp robot-stream.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable robot-stream
sudo systemctl start robot-stream
journalctl -u robot-stream -f       # follow logs
```

---

## Common Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Black video in browser | MediaMTX or publisher not running | Check `server.log`, `mediamtx.log`, `publisher.log` |
| `openssl not found` at startup | openssl not installed | `sudo apt install openssl` |
| Motor not moving | GPIO not available or wrong profile | Check `config.py` `CONTROLLER_TYPE`; confirm RPi.GPIO import in log |
| GPS returns `null` | No serial GPS connected, or wrong port | Set `GPS_TYPE = "NONE"` or correct `GPS_SETTINGS["SERIAL_GPS"]["PORT"]` |
| Certificate warning in browser | Self-signed cert | Click "Advanced → Proceed" once per browser/IP |
| `ImportError: No module named 'picamera2'` on dev machine | picamera2 is Pi-only | Use `CAMERA_TYPE = "USB_CAMERA"` or `"IP_CAMERA"` on non-Pi; tests mock it |
