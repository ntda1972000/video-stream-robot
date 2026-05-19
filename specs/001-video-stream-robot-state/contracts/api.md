# REST API Contract — Video Stream Robot

**Phase 1 output for**: `specs/001-video-stream-robot-state/plan.md`
**Date**: 2026-05-19
**Base URL**: `https://<robot-ip>:5000`

---

## Authentication

None. All endpoints are accessible to any host on the network. (LIM-05)

---

## Endpoints

### `GET /`

Serves the main control dashboard (`dashboard.html`).

**Response**: `200 OK` — HTML page

---

### `GET /api/status`

Returns the current system status, stream state, settings, network stats, and GPS position.

**Response**: `200 OK` — `application/json`

```json
{
  "resolution": [640, 480],
  "fps": 20,
  "rotation": 180,
  "stream_mode": "webrtc",
  "mediamtx_active": true,
  "publisher_active": true,
  "camera_ok": true,
  "net_iface": "wlan0",
  "net_tx_kbps": 412.3,
  "net_rx_kbps": 18.7,
  "io_devices": [
    {"name": "light", "state": true},
    {"name": "Device 2", "state": false},
    {"name": "Device 3", "state": false},
    {"name": "Device 4", "state": false}
  ],
  "motor_trim": 0.0,
  "gps_lat": 10.762622,
  "gps_lon": 106.660172
}
```

**Notes**:
- `camera_ok` is `true` only when both `mediamtx_active` and `publisher_active` are `true`.
- `gps_lat` and `gps_lon` are `null` when GPS type is `"NONE"` or no fix has been obtained.

---

### `POST /api/control`

Send a joystick movement command. Applies tank-drive mixing + motor trim, then drives the active `BaseController`.

**Request body**: `application/json`

```json
{ "x": 0.0, "y": 1.0 }
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `x` | `float` | `[-1.0, 1.0]` | Horizontal axis (left/right steering) |
| `y` | `float` | `[-1.0, 1.0]` | Vertical axis (forward/backward throttle) |

Values outside `[-1.0, 1.0]` are clamped silently.

**Response**: `200 OK`

```json
{ "status": "ok", "x": 0.0, "y": 1.0 }
```

---

### `POST /api/io_toggle`

Toggle the on/off state of one of the four I/O devices.

**Request body**: `application/json`

```json
{ "index": 0 }
```

| Field | Type | Constraints |
|---|---|---|
| `index` | `int` | `0`–`3` |

**Response**: `200 OK`

```json
{ "status": "ok", "index": 0, "state": true }
```

**Error**: `400 Bad Request` when `index` is outside `0`–`3`

```json
{ "error": "index must be 0-3" }
```

---

### `POST /api/io_rename`

Rename one of the four I/O devices.

**Request body**: `application/json`

```json
{ "index": 0, "name": "headlight" }
```

| Field | Type | Constraints |
|---|---|---|
| `index` | `int` | `0`–`3` |
| `name` | `str` | Max 32 chars; empty → `"Device N"` |

**Response**: `200 OK`

```json
{ "status": "ok", "index": 0, "name": "headlight" }
```

**Error**: `400 Bad Request` when `index` is outside `0`–`3`

---

### `POST /api/rotation`

Set the camera display rotation (CSS transform on video element; stream not re-encoded).

**Request body**: `application/json`

```json
{ "rotation": 180 }
```

| Field | Type | Allowed values |
|---|---|---|
| `rotation` | `int` | `0`, `90`, `180`, `270` |

**Response**: `200 OK`

```json
{ "status": "ok", "rotation": 180 }
```

**Error**: `400 Bad Request` for any other value

```json
{ "error": "rotation must be 0, 90, 180 or 270" }
```

---

### `POST /api/update_settings`

Update camera resolution, FPS, and/or motor trim. Resolution/FPS changes restart the publisher.

**Request body**: `application/json` (all fields optional)

```json
{
  "resolution": [640, 480],
  "fps": 20,
  "motor_trim": 0.05
}
```

| Field | Type | Allowed values |
|---|---|---|
| `resolution` | `[int, int]` | `[320, 240]` or `[640, 480]` |
| `fps` | `int` | `5`, `10`, `15`, `20`, `25`, `30` |
| `motor_trim` | `float` | `[-1.0, 1.0]` |

Unknown or invalid `resolution`/`fps` values are silently ignored (no error, no change).

**Response**: `200 OK`

```json
{ "status": "ok", "resolution": [640, 480], "fps": 20, "motor_trim": 0.05 }
```

---

### `POST /proxy/whep`

WebRTC signalling proxy — forwards SDP offer to MediaMTX WHEP endpoint for viewing the robot camera stream.

**Request body**: `application/sdp` — SDP offer from browser

**Response**: `200 OK` — `application/sdp` — SDP answer from MediaMTX

**Error**: `502 Bad Gateway` if MediaMTX is unreachable

---

### `POST /proxy/whip`

WebRTC signalling proxy — forwards SDP offer to MediaMTX WHIP endpoint for sending browser mic audio to the robot.

**Request body**: `application/sdp` — SDP offer from browser

**Response**: `200 OK` — `application/sdp` — SDP answer from MediaMTX

**Error**: `502 Bad Gateway` if MediaMTX is unreachable

---

## Python ABC Contracts

### `BaseCamera` (`interfaces/camera_interface.py`)

```python
from abc import ABC, abstractmethod

class BaseCamera(ABC):
    @abstractmethod
    def get_frame(self) -> bytes:
        """Capture and return a single JPEG-encoded frame.
        Raises RuntimeError on capture failure."""
```

---

### `BaseController` (`interfaces/controller_interface.py`)

```python
from abc import ABC, abstractmethod

class BaseController(ABC):
    @abstractmethod
    def forward(self) -> None: ...
    @abstractmethod
    def backward(self) -> None: ...
    @abstractmethod
    def left(self) -> None: ...
    @abstractmethod
    def right(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
```

---

### `BaseGPS` (`interfaces/gps_interface.py`)

```python
from abc import ABC, abstractmethod

class BaseGPS(ABC):
    @abstractmethod
    def get_coordinates(self) -> tuple[float, float] | None:
        """Return (latitude, longitude) in decimal degrees, or None if no fix."""
```

---

## WebRTC Stream Paths (MediaMTX)

| Path | Protocol | Direction | Port |
|---|---|---|---|
| `/robot` | WHEP | Robot → Browser (video + audio) | 8889 |
| `/from-browser` | WHIP | Browser → Robot (mic audio) | 8889 |
| `/robot` | RTSP | publisher.py → MediaMTX | 8554 |

WebRTC ICE: TCP fallback on port 8189 (for carriers blocking UDP).
