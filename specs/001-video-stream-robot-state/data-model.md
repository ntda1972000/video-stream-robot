# Data Model: Video Stream Robot — HAL Refactoring

**Phase 1 output for**: `specs/001-video-stream-robot-state/plan.md`
**Date**: 2026-05-19

---

## Abstract Interfaces

### `BaseCamera` — `interfaces/camera_interface.py`

| Field / Method | Type | Description |
|---|---|---|
| `get_frame()` | `bytes` | Capture and return a single JPEG-encoded frame. Raises `RuntimeError` on failure. |

**Notes**:
- All concrete camera classes MUST inherit from `BaseCamera` and implement `get_frame()`.
- Callers may not assume anything about the underlying capture mechanism.

---

### `BaseController` — `interfaces/controller_interface.py`

| Method | Description |
|---|---|
| `forward()` | Move robot forward (both motors forward, equal speed) |
| `backward()` | Move robot backward (both motors reversed, equal speed) |
| `left()` | Turn left (right motor forward, left motor stopped or reversed) |
| `right()` | Turn right (left motor forward, right motor stopped or reversed) |
| `stop()` | Stop all motors immediately |

**Notes**:
- All concrete controller classes MUST inherit from `BaseController` and implement all five methods.
- The existing tank-drive mixing logic (from `app.py`) is the responsibility of `GPIOController`; `SerialController` maps `(x, y)` joystick values to the closest discrete command.

---

### `BaseGPS` — `interfaces/gps_interface.py`

| Method | Return Type | Description |
|---|---|---|
| `get_coordinates()` | `tuple[float, float] \| None` | Returns `(latitude, longitude)` in decimal degrees, or `None` if no fix available. |

---

## Concrete Implementations

### `PiCamera` — `implementations/pi_camera.py`

| Attribute | Type | Description |
|---|---|---|
| `_cam` | `picamera2.Picamera2` | Underlying picamera2 instance |
| `_resolution` | `tuple[int, int]` | Width × Height, from `CAMERA_SETTINGS["PI_CAMERA"]["RESOLUTION"]` |

**State transitions**: `__init__` → configure → start; `get_frame()` → capture JPEG → return bytes; `__del__` / `close()` → stop camera.

---

### `IPCamera` — `implementations/ip_camera.py`

| Attribute | Type | Description |
|---|---|---|
| `_cap` | `cv2.VideoCapture` | OpenCV capture object opened with RTSP URL |
| `_rtsp_url` | `str` | From `CAMERA_SETTINGS["IP_CAMERA"]["RTSP_URL"]` |

**State transitions**: `__init__` → open VideoCapture; `get_frame()` → `_cap.read()` → encode JPEG → return bytes.

---

### `USBCamera` — `implementations/usb_camera.py`

| Attribute | Type | Description |
|---|---|---|
| `_cap` | `cv2.VideoCapture` | OpenCV capture object opened with device index |
| `_device_index` | `int` | From `CAMERA_SETTINGS["USB_CAMERA"]["DEVICE_INDEX"]` |

---

### `GPIOController` — `implementations/gpio_controller.py`

| Attribute | Type | Description |
|---|---|---|
| `_pin_l_pwm` | `int` | Left motor PWM pin (BCM), from `CONTROLLER_SETTINGS` |
| `_pin_l_dir` | `int` | Left motor direction pin (BCM) |
| `_pin_r_pwm` | `int` | Right motor PWM pin (BCM) |
| `_pin_r_dir` | `int` | Right motor direction pin (BCM) |
| `_pwm_l` | `RPi.GPIO.PWM` | Left PWM object |
| `_pwm_r` | `RPi.GPIO.PWM` | Right PWM object |
| `_motor_trim` | `float` | Compensation offset `[-1.0, 1.0]`, read from `settings.json` |
| `_ready` | `bool` | True when GPIO initialized successfully |

**Validation rules**:
- Pin values must be valid BCM GPIO numbers (1–27).
- All methods silently no-op when `_ready` is `False` (non-Pi host).
- `stop()` sets both PWM duty cycles to 0.

**State transitions**: `__init__` → GPIO.setmode → setup pins → start PWM; each movement method → `_apply(dir_pin, pwm, speed)`; shutdown → stop PWM → GPIO.cleanup.

---

### `SerialController` — `implementations/serial_controller.py`

| Attribute | Type | Description |
|---|---|---|
| `_ser` | `serial.Serial` | Open serial port |
| `_port` | `str` | Device path, e.g., `/dev/ttyUSB0` |
| `_baudrate` | `int` | Baud rate, default 9600 |

**Command map**:

| Method | Byte sent |
|---|---|
| `forward()` | `b"f"` |
| `backward()` | `b"b"` |
| `left()` | `b"l"` |
| `right()` | `b"r"` |
| `stop()` | `b"s"` |

---

### `SerialGPS` — `implementations/serial_gps.py`

| Attribute | Type | Description |
|---|---|---|
| `_ser` | `serial.Serial` | Open serial port to GPS module |
| `_port` | `str` | Device path, e.g., `/dev/ttyS0` |
| `_baudrate` | `int` | Baud rate, default 9600 |
| `_last_coords` | `tuple[float, float] \| None` | Cached last known coordinates |

**Parsing rules**:
- Read up to 20 lines per `get_coordinates()` call to find a valid NMEA sentence.
- Accept `$GPGGA`, `$GPRMC`, or any sentence that `pynmea2` can parse with `.latitude` attribute.
- Return `None` if no fix found within the read window.
- `pynmea2.ParseError` is caught and suppressed; loop continues to next line.

---

## Configuration Entity

### `config.py` — Hardware Selection

| Constant | Type | Allowed Values |
|---|---|---|
| `CAMERA_TYPE` | `str` | `"PI_CAMERA"`, `"IP_CAMERA"`, `"USB_CAMERA"` |
| `CAMERA_SETTINGS` | `dict[str, dict]` | Per-type params (see below) |
| `CONTROLLER_TYPE` | `str` | `"GPIO_CONTROLLER"`, `"SERIAL_CONTROLLER"` |
| `CONTROLLER_SETTINGS` | `dict[str, dict]` | Per-type params (see below) |
| `GPS_TYPE` | `str` | `"SERIAL_GPS"`, `"NONE"` |
| `GPS_SETTINGS` | `dict[str, dict]` | Per-type params (see below) |

**`CAMERA_SETTINGS` sub-keys**:

| Key | Sub-keys |
|---|---|
| `"PI_CAMERA"` | `RESOLUTION: tuple[int,int]` — capture resolution |
| `"IP_CAMERA"` | `RTSP_URL: str` — full RTSP URL |
| `"USB_CAMERA"` | `DEVICE_INDEX: int` — V4L2 device index |

**`CONTROLLER_SETTINGS` sub-keys**:

| Key | Sub-keys |
|---|---|
| `"GPIO_CONTROLLER"` | `PIN_L_PWM`, `PIN_L_DIR`, `PIN_R_PWM`, `PIN_R_DIR`: `int`; `PWM_HZ: int` |
| `"SERIAL_CONTROLLER"` | `PORT: str`, `BAUDRATE: int` |

**`GPS_SETTINGS` sub-keys**:

| Key | Sub-keys |
|---|---|
| `"SERIAL_GPS"` | `PORT: str`, `BAUDRATE: int` |

---

## Runtime State Entities

### `Settings` — `settings.json`

| Field | Type | Constraints |
|---|---|---|
| `resolution` | `[int, int]` | Must be in `[[320,240], [640,480]]` |
| `fps` | `int` | Must be in `[5, 10, 15, 20, 25, 30]` |
| `rotation` | `int` | Must be in `[0, 90, 180, 270]` |
| `motor_trim` | `float` | `[-1.0, 1.0]`, 3 decimal places |
| `io_devices` | `list[IODevice]` | Exactly 4 entries |

### `IODevice`

| Field | Type | Constraints |
|---|---|---|
| `name` | `str` | Max 32 chars; defaults to `"Device N"` if blank |
| `state` | `bool` | Toggle state (no GPIO output currently) |

### `GPSCoordinates` (runtime cache in `app.py`)

| Field | Type | Description |
|---|---|---|
| `lat` | `float \| None` | Latitude in decimal degrees |
| `lon` | `float \| None` | Longitude in decimal degrees |

Populated by periodic poll of the active `BaseGPS` instance; exposed via `GET /api/status` as `gps_lat` and `gps_lon`.

---

## Factory Pattern in `app.py`

```python
# Camera factory
_cam_settings = CAMERA_SETTINGS.get(CAMERA_TYPE, {})
if CAMERA_TYPE == "PI_CAMERA":
    from implementations.pi_camera import PiCamera
    camera = PiCamera(_cam_settings)
elif CAMERA_TYPE == "IP_CAMERA":
    from implementations.ip_camera import IPCamera
    camera = IPCamera(_cam_settings)
elif CAMERA_TYPE == "USB_CAMERA":
    from implementations.usb_camera import USBCamera
    camera = USBCamera(_cam_settings)
else:
    raise ValueError(f"Unknown CAMERA_TYPE: {CAMERA_TYPE}")

# Controller factory (analogous pattern for CONTROLLER_TYPE)
# GPS factory (analogous pattern for GPS_TYPE; "NONE" → camera = None)
```

Lazy imports inside the factory blocks ensure that `picamera2` and `cv2` are only imported when the relevant type is selected, preventing `ImportError` on platforms where only one is installed.
