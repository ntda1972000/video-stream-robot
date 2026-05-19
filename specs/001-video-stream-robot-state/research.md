# Research: Video Stream Robot — HAL Dependencies & Design Decisions

**Phase 0 output for**: `specs/001-video-stream-robot-state/plan.md`
**Date**: 2026-05-19

---

## R-01 — Camera Library: picamera2 vs picamera

**Decision**: Use `picamera2`

**Rationale**: `picamera` (v1.x) is a legacy library targeting the V4L2/MMAL stack on Pi 3 and earlier. It is **not compatible** with Raspberry Pi OS Bookworm (Debian 12), which uses the `libcamera` framework exclusively. `picamera2` is the official successor maintained by the Raspberry Pi Foundation and supports all Pi models (3B+, 4, 5) on Bookworm.

**Alternatives considered**:
- `picamera` (legacy): Incompatible with Bookworm/libcamera. Rejected.
- `rpicam-vid` CLI (current approach): Works but does not offer a Python API for per-frame access; keeps camera in a separate subprocess. The HAL `PiCamera.get_frame()` requires Python-level frame access, so `picamera2` is the right choice.

**Installation**: `picamera2` requires system packages on Bookworm. The recommended installation is:
```bash
sudo apt install python3-picamera2
# OR inside venv with system-site-packages:
python3 -m venv --system-site-packages .venv
# OR via pip (may need libcamera system headers):
pip install picamera2
```
The `setup_robot.sh` must be updated to install `python3-picamera2` via apt.

**Key code snippet**:
```python
from picamera2 import Picamera2
import io

class PiCamera(BaseCamera):
    def __init__(self, settings: dict):
        self._cam = Picamera2()
        w, h = settings.get("RESOLUTION", (640, 480))
        config = self._cam.create_still_configuration(
            main={"size": (w, h), "format": "RGB888"}
        )
        self._cam.configure(config)
        self._cam.start()

    def get_frame(self) -> bytes:
        buf = io.BytesIO()
        self._cam.capture_file(buf, format="jpeg")
        return buf.getvalue()
```

---

## R-02 — OpenCV for IPCamera and USBCamera

**Decision**: Use `opencv-python-headless`

**Rationale**: `opencv-python-headless` omits GUI dependencies (Qt, GTK) that are not needed on a headless Pi server. This significantly reduces install size and avoids conflicts with the Pi's display stack. It supports `cv2.VideoCapture` for both RTSP streams and USB V4L2 devices.

**Alternatives considered**:
- `opencv-python` (full): Includes GUI windows; unnecessary for server use. Rejected.
- `opencv-contrib-python-headless`: Adds extra modules not needed here. Rejected.

**Installation**: `pip install opencv-python-headless`

**Key code snippets**:

IPCamera (RTSP):
```python
import cv2

class IPCamera(BaseCamera):
    def __init__(self, settings: dict):
        url = settings["RTSP_URL"]
        self._cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

    def get_frame(self) -> bytes:
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from IP camera")
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
```

USBCamera (device index):
```python
class USBCamera(BaseCamera):
    def __init__(self, settings: dict):
        idx = settings.get("DEVICE_INDEX", 0)
        self._cap = cv2.VideoCapture(idx)

    def get_frame(self) -> bytes:
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from USB camera")
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
```

---

## R-03 — Serial I/O: pyserial

**Decision**: Use `pyserial` (pip package `pyserial`)

**Rationale**: `pyserial` is the de-facto standard serial port library for Python on Linux. It supports all common UART parameters (baud rate, parity, stop bits) and is well-maintained. No alternatives are needed.

**Installation**: `pip install pyserial`

**Key code snippets**:

SerialController (write command):
```python
import serial

class SerialController(BaseController):
    def __init__(self, settings: dict):
        self._ser = serial.Serial(
            settings["PORT"],
            baudrate=settings.get("BAUDRATE", 9600),
            timeout=1,
        )

    def forward(self):  self._ser.write(b"f")
    def backward(self): self._ser.write(b"b")
    def left(self):     self._ser.write(b"l")
    def right(self):    self._ser.write(b"r")
    def stop(self):     self._ser.write(b"s")
```

SerialGPS (read NMEA line):
```python
class SerialGPS(BaseGPS):
    def __init__(self, settings: dict):
        self._ser = serial.Serial(
            settings["PORT"],
            baudrate=settings.get("BAUDRATE", 9600),
            timeout=1,
        )

    def get_coordinates(self):
        line = self._ser.readline().decode("ascii", errors="replace").strip()
        # Parse below — see R-04
```

---

## R-04 — NMEA Parsing: pynmea2

**Decision**: Use `pynmea2`

**Rationale**: `pynmea2` is the most widely used Python NMEA 0183 parser. It supports `$GPRMC`, `$GPGGA`, and related sentences and returns parsed objects with `.latitude` and `.longitude` float attributes. Straightforward API with no external dependencies.

**Alternatives considered**:
- Manual string split: Fragile; checksum validation would be manual. Rejected.
- `nmea-parser`: Less maintained, fewer users. Rejected.

**Installation**: `pip install pynmea2`

**Key code snippet**:
```python
import pynmea2

def get_coordinates(self):
    for _ in range(20):  # try up to 20 lines to find a fix
        line = self._ser.readline().decode("ascii", errors="replace").strip()
        if not line.startswith("$"):
            continue
        try:
            msg = pynmea2.parse(line)
            if hasattr(msg, "latitude") and msg.latitude:
                return (msg.latitude, msg.longitude)
        except pynmea2.ParseError:
            continue
    return None
```

---

## R-05 — Browser Minimap: Leaflet.js

**Decision**: Use Leaflet.js via CDN with OpenStreetMap tiles

**Rationale**: Leaflet.js is the dominant lightweight JavaScript mapping library (< 40 KB gzipped). It integrates trivially into any HTML page via a `<script>` CDN tag — no build system required. OpenStreetMap tiles work over any internet connection (LAN requires internet access for tiles; for offline operation, a local tile server such as `tileserver-gl` would be needed — out of scope for this phase).

**CDN vs bundled**: CDN is simpler and avoids adding a JavaScript build pipeline to the project. The robot already requires LAN/Tailscale/4G connectivity for WebRTC; tile loading is a minor additional dependency.

**Alternatives considered**:
- Google Maps: Requires API key, overkill for a single-marker robot dashboard. Rejected.
- Mapbox: Requires API key. Rejected.
- Canvas-only custom map: No tile support. Rejected for usability.

**Key HTML/JS snippet**:
```html
<!-- In dashboard.html <head> -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Minimap container (toggleable via CSS display:none/block) -->
<div id="minimap" style="width:100%;height:200px;display:none;"></div>

<script>
const map = L.map("minimap").setView([0, 0], 15);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);
const robotMarker = L.marker([0, 0]).addTo(map);

function updateMinimap(lat, lon) {
  robotMarker.setLatLng([lat, lon]);
  map.setView([lat, lon]);
}
</script>
```

The toggle button uses the existing `.ov-btn` CSS class (30×30px circular button) and is placed in `.ov-br` cluster alongside speaker/mic buttons, consistent with FR-063 and FR-064.

---

## R-06 — Testing Strategy: pytest + unittest.mock

**Decision**: Use `pytest` with `unittest.mock.patch` to mock all hardware dependencies

**Rationale**: `pytest` is the standard Python test framework. `unittest.mock` is part of the Python standard library and provides `patch()` as a context manager or decorator. Both `RPi.GPIO` and `serial.Serial` can be patched before import to prevent `ImportError` on dev machines and to assert call sequences in unit tests.

**Installation**: `pip install pytest pytest-mock`

**Key patterns**:

Mock RPi.GPIO in `conftest.py`:
```python
# tests/conftest.py
import sys
from unittest.mock import MagicMock

# Provide a fake RPi.GPIO before any test module imports app.py
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()
sys.modules["picamera2"] = MagicMock()
```

Mock serial.Serial in a test:
```python
from unittest.mock import patch, MagicMock

def test_serial_controller_forward():
    with patch("implementations.serial_controller.serial.Serial") as mock_ser:
        instance = mock_ser.return_value
        from implementations.serial_controller import SerialController
        ctrl = SerialController({"PORT": "/dev/ttyUSB0", "BAUDRATE": 9600})
        ctrl.forward()
        instance.write.assert_called_once_with(b"f")
```

Flask API test (mocked hardware):
```python
# tests/integration/test_api.py
import pytest
from app import app as flask_app

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

def test_api_control_returns_ok(client):
    resp = client.post("/api/control", json={"x": 0.5, "y": 0.8})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
```

---

## Summary Table

| Unknown | Decision | Key Package |
|---------|----------|-------------|
| Pi CSI camera library | `picamera2` | `python3-picamera2` (apt) |
| IP/USB camera | OpenCV headless | `opencv-python-headless` |
| Serial I/O | pyserial | `pyserial` |
| NMEA GPS parsing | pynmea2 | `pynmea2` |
| Browser minimap | Leaflet.js CDN | CDN (no pip) |
| Test framework | pytest + unittest.mock | `pytest`, `pytest-mock` |

All NEEDS CLARIFICATION items from Technical Context in `plan.md` are now resolved.
