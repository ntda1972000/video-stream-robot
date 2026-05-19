# Feature Specification: Video Stream Robot — Current State

**Feature Branch**: `001-video-stream-robot-state`

**Created**: 2026-05-19

**Status**: Draft

---

## Overview

This specification documents the **current implemented state** of the `video-stream-robot` project: a Raspberry Pi-based RC car that streams live video and audio to a browser over WebRTC, with bidirectional audio and motor control via a Flask HTTPS web interface. No future features are described — only what exists in the codebase today.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Watch Live Video Stream (Priority: P1)

An operator navigates to the robot's dashboard in a browser and watches the live video feed from the Pi CSI camera in real time.

**Why this priority**: Streaming video is the core purpose of the system. Without a working stream, all other features lose context and value.

**Independent Test**: Can be fully tested by opening `https://<robot-ip>:5000/` and confirming video playback in the browser — delivers real-time robot vision without needing any other feature.

**Acceptance Scenarios**:

1. **Given** the robot is running and MediaMTX + publisher are active, **When** an operator opens the dashboard URL, **Then** the live WebRTC video stream loads and plays in the browser within a few seconds.
2. **Given** the camera is configured with 180° rotation in settings, **When** the stream appears in the browser, **Then** the video is displayed rotated 180° via CSS transform.
3. **Given** MediaMTX or the publisher process crashes, **When** the watchdog detects the failure, **Then** the process is restarted automatically within 10 seconds.

---

### User Story 2 — Drive the Robot via Browser Joystick (Priority: P2)

An operator uses a virtual on-screen joystick (touch or mouse) to send directional commands to the robot's motors, making it move and turn.

**Why this priority**: Remote motor control is the second core capability. Steering via joystick enables the primary RC-car use case.

**Independent Test**: Can be fully tested on a Pi by moving the joystick and observing motor response, independently of video.

**Acceptance Scenarios**:

1. **Given** the dashboard is open and GPIO is available, **When** the operator drags the joystick forward, **Then** both motors receive a PWM duty cycle corresponding to forward motion.
2. **Given** the operator drags the joystick left or right, **Then** tank-drive mixing produces a differential speed between the left and right motors, causing the robot to turn.
3. **Given** the `motor_trim` setting is non-zero, **When** a drive command is sent, **Then** the trim correction is applied to compensate for mechanical speed differences between motors.
4. **Given** the application runs on a non-Pi host (RPi.GPIO unavailable), **When** joystick commands arrive, **Then** the `/api/control` endpoint returns `{"status": "ok"}` without error and motor output is silently skipped.

---

### User Story 3 — Hear Audio from the Robot's Environment (Priority: P3)

An operator listens to audio captured by the robot's USB microphone, delivered in the same WebRTC stream as the video.

**Why this priority**: Audio awareness of the robot's environment is important for remote operation. It is delivered through the same WHEP stream as video, making it easy to test independently.

**Independent Test**: Can be tested by speaking near the robot's USB mic and confirming audio is heard in the browser while the video stream is active.

**Acceptance Scenarios**:

1. **Given** a USB microphone is attached and detected by `arecord -l`, **When** the publisher starts, **Then** audio is captured via ALSA and encoded with libopus at 32 kbps (voip mode) into the RTSP stream.
2. **Given** no USB microphone is detected, **When** the publisher starts, **Then** a video-only stream is published without audio (no error, graceful degradation).

---

### User Story 4 — Send Voice to the Robot (Priority: P3)

An operator uses the browser's microphone to send their voice to the robot, which plays the audio on the Pi's speaker via PulseAudio.

**Why this priority**: Bidirectional audio completes the communication channel. It can be tested independently of driving.

**Independent Test**: Can be tested by enabling the browser mic and speaking — audio should play on the robot's connected speaker.

**Acceptance Scenarios**:

1. **Given** the operator grants browser microphone permission, **When** the browser connects via WHIP (`/proxy/whip`), **Then** audio is forwarded to MediaMTX and piped via FFmpeg to the Pi's default PulseAudio sink.
2. **Given** the browser is connected via WHIP, **When** the audio stream ends or the browser tab is closed, **Then** the FFmpeg process on the robot terminates cleanly (MediaMTX `runOnReadyRestart` handles restarts).

---

### User Story 5 — Adjust Stream Settings (Priority: P4)

An operator changes the camera resolution, frame rate, or motor trim from the dashboard. The stream updates to reflect the new settings.

**Why this priority**: Operators need to balance stream quality against bandwidth. Settings changes persist across restarts.

**Independent Test**: Can be tested by changing resolution and confirming the publisher restarts with the new parameters visible in `settings.json`.

**Acceptance Scenarios**:

1. **Given** the operator submits a new resolution (320×240 or 640×480) or FPS (5/10/15/20/25/30), **When** `POST /api/update_settings` is called, **Then** settings are saved to `settings.json`, the publisher is stopped and restarted with the new parameters.
2. **Given** the operator adjusts the motor trim slider (−1.0 to +1.0), **When** the update is submitted, **Then** the trim value is saved without restarting the publisher.
3. **Given** the operator uses the rotate CW or CCW button, **When** `POST /api/rotation` is called, **Then** the rotation setting (0/90/180/270°) is saved and the video CSS transform updates on the next status poll.

---

### User Story 6 — Toggle and Rename I/O Devices (Priority: P5)

An operator toggles one of four named digital I/O outputs from the dashboard and optionally renames the devices.

**Why this priority**: I/O control is partially implemented (UI and state persistence) but GPIO output is not yet wired.

**Independent Test**: Can be tested by toggling a device and verifying the state change is saved in `settings.json`.

**Acceptance Scenarios**:

1. **Given** the dashboard displays 4 I/O toggle buttons, **When** the operator clicks a toggle, **Then** `POST /api/io_toggle` is called, the device state flips, and the new state is saved to `settings.json`.
2. **Given** an operator double-clicks a device name in the UI, **When** a new name (up to 32 characters) is entered, **Then** `POST /api/io_rename` is called and the name is saved to `settings.json`.
3. **Given** a toggle is activated, **When** the backend processes the request, **Then** no GPIO pin output occurs (GPIO for I/O devices is not implemented — state is persisted only).

---

---

### User Story 7 — Switch Between Camera Types (Priority: P2)

A developer configures the system to use a different camera (Pi CSI camera, IP camera, or USB camera) by changing `CAMERA_TYPE` in `config.py`, without modifying application logic.

**Acceptance Scenarios**:

1. **Given** `CAMERA_TYPE="PI_CAMERA"` in `config.py`, **When** the application starts, **Then** `PiCamera` is instantiated using the resolution from `CAMERA_SETTINGS["PI_CAMERA"]`.
2. **Given** `CAMERA_TYPE="IP_CAMERA"` in `config.py`, **When** the application starts, **Then** `IPCamera` is instantiated, connecting to the RTSP URL from `CAMERA_SETTINGS["IP_CAMERA"]`.
3. **Given** `CAMERA_TYPE="USB_CAMERA"` in `config.py`, **When** the application starts, **Then** `USBCamera` is instantiated using the device index from `CAMERA_SETTINGS["USB_CAMERA"]`.
4. **Given** any concrete camera class is used, **When** `get_frame()` is called, **Then** a video frame is returned in a consistent format regardless of the underlying camera source.

---

### User Story 8 — Switch Between Motor Controllers (Priority: P2)

A developer configures the system to use either direct GPIO motor control or serial control to an Arduino, by changing `CONTROLLER_TYPE` in `config.py`, without modifying application logic.

**Acceptance Scenarios**:

1. **Given** `CONTROLLER_TYPE="GPIO_CONTROLLER"`, **When** a drive command arrives, **Then** `GPIOController` is used and PWM signals are sent to the GPIO pins defined in `CONTROLLER_SETTINGS["GPIO_CONTROLLER"]`.
2. **Given** `CONTROLLER_TYPE="SERIAL_CONTROLLER"`, **When** a drive command arrives, **Then** `SerialController` sends command strings ("f", "b", "l", "r", "s") over the serial port defined in `CONTROLLER_SETTINGS["SERIAL_CONTROLLER"]`.
3. **Given** any concrete controller class is used, **When** `forward()`, `backward()`, `left()`, `right()`, or `stop()` is called, **Then** the robot responds correctly regardless of the controller implementation.

---

### User Story 9 — View Robot Location on Minimap (Priority: P4)

An operator views the robot's current GPS position overlaid on a 2D map directly in the dashboard, and can toggle the minimap on or off.

**Acceptance Scenarios**:

1. **Given** a GPS module is connected via serial port, **When** the application polls for coordinates, **Then** latitude and longitude are returned by `SerialGPS.get_coordinates()`.
2. **Given** GPS coordinates are available, **When** the dashboard minimap is visible, **Then** the robot's position icon updates on the map.
3. **Given** the operator clicks the minimap toggle button, **When** the minimap is currently visible, **Then** it hides; when hidden, clicking the toggle makes it visible again.
4. **Given** the minimap toggle button, **When** rendered, **Then** it uses the same icon style, size, and positioning as the existing speaker and microphone overlay buttons (`.ov-btn` CSS class, 30×30px circular button).

---

### Edge Cases

- What happens when MediaMTX binary is missing at startup? → `start_mediamtx()` logs a warning and returns silently; no crash.
- What happens when `publisher.py` is not found? → `start_publisher()` logs a warning and returns; no crash.
- What happens when `settings.json` is corrupt or missing? → `load_settings()` falls back to `DEFAULT_SETTINGS` silently.
- What happens when `openssl` is unavailable for certificate generation? → `subprocess.run` raises, crashing startup; openssl is a required dependency.
- What happens when the operator sends a joystick command with values outside `[-1, 1]`? → `api_control()` clamps values to `[-1.0, 1.0]`.
- What happens when `io_toggle` or `io_rename` receives an index outside 0–3? → API returns HTTP 400 with `{"error": "index must be 0-3"}`.
- What happens if the self-signed certificate IPs change (e.g., Tailscale comes up after boot)? → The certificate is regenerated on next startup that detects the IP change.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Video Streaming Pipeline

- **FR-001**: System MUST detect and use `rpicam-vid` or `libcamera-vid` (whichever is present) to capture CSI camera video as raw YUV420 output.
- **FR-002**: System MUST encode video using `libx264` with `ultrafast` preset and `zerolatency` tuning. Hardware encoders (`h264_v4l2m2m`, `h264_omx`) are intentionally disabled.
- **FR-003**: Video bitrate MUST be computed proportionally to resolution and FPS: baseline 500 kbps at 640×480@30, clamped to a minimum of 80 kbps and maximum of 500 kbps.
- **FR-004**: System MUST push the encoded stream to `rtsp://localhost:8554/robot` using RTSP over TCP transport.
- **FR-005**: System MUST serve WebRTC video to browsers via the `/proxy/whep` endpoint (WHEP protocol, SDP forwarded to MediaMTX).

#### Audio Pipeline

- **FR-006**: System MUST detect ALSA microphone availability using `arecord -l` before starting the publisher.
- **FR-007**: When a microphone is detected, audio MUST be captured from the ALSA `default` device at 44100 Hz mono and encoded with `libopus` at 32 kbps in `voip` application mode.
- **FR-008**: When no microphone is detected, publisher MUST publish video-only stream (no audio track) without error.
- **FR-009**: System MUST accept browser microphone audio via `/proxy/whip` (WHIP protocol), forwarded to MediaMTX at `http://127.0.0.1:8889/from-browser/whip`.
- **FR-010**: When a browser connects to the `from-browser` path in MediaMTX, MUST pipe the received audio via FFmpeg to the Pi's default PulseAudio sink (resampled to 48000 Hz).

#### Motor Control

- **FR-011**: System MUST configure GPIO in BCM mode: Left motor (PWM pin 17, DIR pin 27), Right motor (PWM pin 22, DIR pin 23), 100 Hz PWM frequency.
- **FR-012**: System MUST apply tank-drive mixing: `left = throttle + steer`, `right = throttle − steer`, with both values clamped to `[−1.0, 1.0]`.
- **FR-013**: System MUST apply `motor_trim` compensation: positive trim slows the right motor; negative trim slows the left motor.
- **FR-014**: System MUST gracefully disable motor output when `RPi.GPIO` is not importable (non-Pi host).
- **FR-015**: System MUST stop motors (zero PWM) and call `GPIO.cleanup()` on process shutdown.

#### MediaMTX Management

- **FR-016**: System MUST dynamically generate `mediamtx_run.yml` at startup, populating WebRTC ICE additional hosts with all current non-loopback IPv4 addresses.
- **FR-017**: MediaMTX MUST be configured with: RTSP on port 8554, WebRTC on port 8889, TCP fallback on port 8189, local API on `127.0.0.1:9997`. RTMP, HLS, and SRT are disabled.
- **FR-018**: System MUST spawn MediaMTX as a child process (logs to `mediamtx.log`).
- **FR-019**: System MUST spawn `publisher.py` as a detached subprocess in a new session group (logs to `publisher.log`).
- **FR-020**: A watchdog thread MUST poll every 5 seconds and restart MediaMTX or publisher if either has exited.

#### TLS Certificate

- **FR-021**: System MUST auto-generate a self-signed RSA-2048 TLS certificate (`cert.pem` / `key.pem`) covering all non-loopback IPv4 addresses as Subject Alternative Names.
- **FR-022**: System MUST regenerate the certificate when any current IP address is missing from the existing certificate.

#### Settings Management

- **FR-023**: Settings MUST be loaded from `settings.json`; missing keys fall back to defaults.
- **FR-024**: Valid resolution options are `[320, 240]` and `[640, 480]`. Valid FPS options are `[5, 10, 15, 20, 25, 30]`.
- **FR-025**: Rotation MUST be one of `0`, `90`, `180`, or `270` degrees. Rotation is applied as a CSS transform in the browser; the video stream itself is not re-encoded.
- **FR-026**: `motor_trim` MUST be stored as a float in `[−1.0, 1.0]` rounded to 3 decimal places.
- **FR-027**: Changing resolution or FPS via `POST /api/update_settings` MUST stop the publisher, wait 0.5 s, and restart it.

#### I/O Devices

- **FR-028**: System MUST maintain exactly 4 I/O device entries, each with a `name` (string) and `state` (boolean).
- **FR-029**: `POST /api/io_toggle` MUST flip the state of the device at the given index (0–3) and persist to `settings.json`.
- **FR-030**: `POST /api/io_rename` MUST update the device name (trimmed, max 32 chars; defaults to `"Device N"` if empty) and persist to `settings.json`.
- **FR-031**: I/O device toggle does NOT drive any GPIO output. State persistence only.

#### Network Monitoring

- **FR-032**: A background thread MUST read `/sys/class/net/<iface>/statistics/tx_bytes` and `rx_bytes` every 2 seconds to compute TX/RX kbps.
- **FR-033**: The primary interface MUST be selected from the default route (`ip route show default`); fallback to the non-loopback interface with the highest TX byte count.

#### REST API

- **FR-034**: `GET /api/status` MUST return: `resolution`, `fps`, `rotation`, `stream_mode` (`"webrtc"`), `mediamtx_active`, `publisher_active`, `camera_ok`, `net_iface`, `net_tx_kbps`, `net_rx_kbps`, `io_devices`, `motor_trim`.
- **FR-035**: `POST /api/control` MUST accept `{x, y}` joystick values (clamped to `[−1.0, 1.0]`) and apply tank-drive + trim to drive motors.
- **FR-036**: `POST /api/rotation` MUST accept `rotation` values of `0`, `90`, `180`, or `270`; return HTTP 400 for invalid values.
- **FR-037**: `POST /api/update_settings` MUST ignore unknown resolution or FPS values (no error, no change).

#### Web Interface (Dashboard)

- **FR-038**: Dashboard MUST display a WebRTC video element consuming `/proxy/whep` with CSS rotation matching the `rotation` setting.
- **FR-039**: Dashboard MUST display overlay buttons: rotate CW and rotate CCW (top-left of video), speaker/mute popup and mic gain popup (bottom-right of video).
- **FR-040**: Dashboard MUST include a virtual joystick panel supporting both touch and mouse drag, sending `{x, y}` to `POST /api/control` at approximately 20 Hz.
- **FR-041**: Dashboard MUST display a status bar polling `GET /api/status` every 3 seconds, showing resolution, FPS, and network TX/RX kbps.
- **FR-042**: Dashboard MUST include 4 I/O toggle buttons with inline-editable names.
- **FR-043**: Dashboard MUST include a motor trim slider with range −1.0 to +1.0.

#### Process Startup Sequence

- **FR-044**: Subprocess startup (MediaMTX, publisher) MUST be deferred to gunicorn `post_worker_init` to ensure the worker process is the parent.
- **FR-045**: Startup sequence MUST be: start MediaMTX → wait 2 s → start publisher → setup GPIO → start NetworkMonitor → start watchdog thread.
- **FR-046**: At module import, any leftover `mediamtx` or `publisher.py` processes from a previous run MUST be killed.

#### Hardware Abstraction Layer — Camera

- **FR-047**: System MUST define a `BaseCamera` abstract interface in `interfaces/camera_interface.py` with at minimum a `get_frame()` abstract method.
- **FR-048**: `PiCamera` class in `implementations/pi_camera.py` MUST inherit from `BaseCamera` and implement `get_frame()` using the `picamera` library for Raspberry Pi CSI cameras.
- **FR-049**: `IPCamera` class in `implementations/ip_camera.py` MUST inherit from `BaseCamera` and implement `get_frame()` using OpenCV (`cv2.VideoCapture`) to read frames from a network RTSP stream URL.
- **FR-050**: `app.py` MUST instantiate the correct camera class at startup based on the `CAMERA_TYPE` constant in `config.py`, passing the corresponding `CAMERA_SETTINGS` entry to the constructor, with no camera-type-specific logic in `app.py`.

#### Hardware Abstraction Layer — Motor Controller

- **FR-051**: System MUST define a `BaseController` abstract interface in `interfaces/controller_interface.py` with abstract methods: `forward()`, `backward()`, `left()`, `right()`, `stop()`.
- **FR-052**: `GPIOController` class in `implementations/gpio_controller.py` MUST inherit from `BaseController` and implement all movement methods by driving L298N/L293D H-bridge GPIO pins (migrated from `app.py`).
- **FR-053**: `SerialController` class in `implementations/serial_controller.py` MUST inherit from `BaseController` and implement all movement methods by sending single-character command strings over a configured serial port (e.g., "f" = forward, "b" = backward, "l" = left, "r" = right, "s" = stop).
- **FR-054**: `app.py` MUST instantiate the correct controller class at startup based on the `CONTROLLER_TYPE` constant in `config.py`, passing the corresponding `CONTROLLER_SETTINGS` entry to the constructor, with no controller-type-specific logic in `app.py`.

#### Hardware Abstraction Layer — Configuration

- **FR-055**: `config.py` MUST define a `CAMERA_TYPE` string constant selecting the active camera implementation. Supported values: `"PI_CAMERA"`, `"IP_CAMERA"`, `"USB_CAMERA"`.
- **FR-055a**: `config.py` MUST define a `CAMERA_SETTINGS` dictionary keyed by camera type, containing per-type parameters. Example structure:
  ```python
  CAMERA_SETTINGS = {
      "IP_CAMERA":  {"RTSP_URL": "rtsp://..."},
      "PI_CAMERA":  {"RESOLUTION": (1280, 720)},
      "USB_CAMERA": {"DEVICE_INDEX": 0},
  }
  ```
- **FR-056**: `config.py` MUST define a `CONTROLLER_TYPE` string constant selecting the active motor controller. Supported values: `"GPIO_CONTROLLER"`, `"SERIAL_CONTROLLER"`.
- **FR-056a**: `config.py` MUST define a `CONTROLLER_SETTINGS` dictionary keyed by controller type, containing per-type parameters. Example structure:
  ```python
  CONTROLLER_SETTINGS = {
      "SERIAL_CONTROLLER": {"PORT": "/dev/ttyUSB0", "BAUDRATE": 9600},
      "GPIO_CONTROLLER":   {"PIN_FORWARD": 17, "PIN_BACKWARD": 18, ...},
  }
  ```
- **FR-056b**: `config.py` MUST define a `GPS_TYPE` string constant selecting the active GPS implementation. Supported values: `"SERIAL_GPS"`, `"NONE"`.
- **FR-056c**: `config.py` MUST define a `GPS_SETTINGS` dictionary keyed by GPS type, containing per-type parameters. Example structure:
  ```python
  GPS_SETTINGS = {
      "SERIAL_GPS": {"PORT": "/dev/ttyS0", "BAUDRATE": 9600},
  }
  ```
- **FR-056d**: `app.py` MUST use a factory pattern or conditional logic at startup to instantiate the correct Camera, Controller, and GPS classes, reading the `_TYPE` constants and passing the corresponding `_SETTINGS` entries. No implementation-specific logic MAY exist in `app.py`.

#### GPS and Geolocation

- **FR-057**: System MUST define a `BaseGPS` abstract interface in `interfaces/gps_interface.py` with at minimum a `get_coordinates()` abstract method returning a `(latitude, longitude)` tuple (or `None` if no fix).
- **FR-058**: `SerialGPS` class in `implementations/serial_gps.py` MUST inherit from `BaseGPS` and implement `get_coordinates()` by reading and parsing NMEA sentences from a GPS module connected via a serial port.
- **FR-059**: `app.py` MUST periodically poll the active GPS instance and cache the latest coordinates.
- **FR-060**: `GET /api/status` MUST be extended to include `gps_lat` and `gps_lon` fields (floats, or `null` if no GPS fix).

#### Minimap UI

- **FR-061**: The dashboard (`dashboard.html`) MUST include a minimap section that displays a 2D map and a robot position icon using the cached GPS coordinates from the backend.
- **FR-062**: The minimap MUST update its displayed position whenever new GPS coordinates are received via the status polling endpoint.
- **FR-063**: The minimap MUST have a visibility toggle. The toggle button MUST use the same `.ov-btn` CSS class, 30×30px circular style, and positioning approach as the existing speaker and microphone overlay buttons.
- **FR-064**: The minimap toggle button MUST be placed in the same overlay area as the speaker/mic buttons (bottom-right of the stream panel, `.ov-br` cluster) to maintain visual consistency.

### Key Entities

- **Settings**: Persistent configuration stored in `settings.json`. Fields: `resolution` (2-element list), `fps` (int), `rotation` (int), `motor_trim` (float), `io_devices` (list of 4 × `{name: str, state: bool}`).
- **I/O Device**: One of 4 named, toggleable state entries. Fields: `name` (string, max 32 chars), `state` (boolean). No physical GPIO output currently.
- **Stream Path (robot)**: RTSP stream at `rtsp://localhost:8554/robot` published by `publisher.py`, re-served as WebRTC by MediaMTX on port 8889.
- **Stream Path (from-browser)**: WHIP endpoint at `rtsp://localhost:8554/from-browser` receiving browser mic audio, piped to PulseAudio on connection.
- **BaseCamera**: Abstract interface in `interfaces/camera_interface.py`. Defines the `get_frame()` contract for all camera implementations.
- **PiCamera**: Concrete camera implementation in `implementations/pi_camera.py`. Uses the `picamera` library to capture CSI camera frames on Raspberry Pi.
- **IPCamera**: Concrete camera implementation in `implementations/ip_camera.py`. Uses OpenCV `cv2.VideoCapture` to read frames from a network RTSP stream.
- **BaseController**: Abstract interface in `interfaces/controller_interface.py`. Defines the `forward()`, `backward()`, `left()`, `right()`, `stop()` contract for all motor controller implementations.
- **GPIOController**: Concrete controller implementation in `implementations/gpio_controller.py`. Drives L298N/L293D H-bridge GPIO pins directly.
- **SerialController**: Concrete controller implementation in `implementations/serial_controller.py`. Sends single-character command strings over a serial port to an Arduino or compatible microcontroller.
- **BaseGPS**: Abstract interface in `interfaces/gps_interface.py`. Defines the `get_coordinates()` contract returning `(latitude, longitude)` or `None`.
- **SerialGPS**: Concrete GPS implementation in `implementations/serial_gps.py`. Reads and parses NMEA sentences from a serial-connected GPS module.
- **config.py**: Hardware component configuration file. Defines independent `CAMERA_TYPE`, `CONTROLLER_TYPE`, and `GPS_TYPE` string constants, each paired with a corresponding `_SETTINGS` dictionary containing per-type parameters (e.g., GPIO pins, serial port paths, RTSP URL, device index). Components can be combined freely regardless of board type.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operator can view live video from the robot's camera in the browser within 5 seconds of opening the dashboard.
- **SC-002**: Motor drive commands from the joystick are reflected in motor behavior within 100 ms of user input.
- **SC-003**: The stream automatically recovers (MediaMTX or publisher restart) within 10 seconds of an unexpected process crash.
- **SC-004**: Changing resolution or FPS from the dashboard takes effect (publisher restarts with new settings) without requiring a manual server restart.
- **SC-005**: The dashboard is accessible over HTTPS on both LAN and Tailscale IP addresses using a single auto-generated certificate.
- **SC-006**: When the operator toggles an I/O device, the updated state is visible immediately in the UI and persisted to `settings.json`.
- **SC-007**: When no USB microphone is present, the video stream starts and plays normally (no error state, no broken stream).
- **SC-008**: Changing `CAMERA_TYPE`, `CONTROLLER_TYPE`, or `GPS_TYPE` individually in `config.py` and restarting the server causes only the corresponding component to switch implementation, with no changes to `app.py` required.
- **SC-009**: When a GPS fix is available, the `/api/status` endpoint returns non-null `gps_lat` and `gps_lon` values, and the minimap displays the robot's position.
- **SC-010**: The minimap toggle button is visually indistinguishable in style from the speaker and microphone overlay buttons.

---

## Assumptions

- Deployed on a Raspberry Pi running a Debian-based Linux OS with `rpicam-vid` or `libcamera-vid` installed.
- A CSI camera module compatible with `rpicam-vid`/`libcamera-vid` is physically attached.
- MediaMTX v1.9.0 binary is pre-installed at `~/rc-car/mediamtx` (as installed by `setup_robot.sh`).
- `openssl`, `ffmpeg`, `arecord`, `python3`, and `gunicorn` are available on the system PATH.
- The browser must manually accept the self-signed TLS certificate (trust warning is expected and acceptable).
- USB microphone and speaker are optional; the system degrades gracefully to video-only when absent.
- Tailscale may be optionally installed; the TLS certificate will include the Tailscale IP if it is active at startup.
- GPIO for the 4 I/O toggle devices is **not yet implemented**; toggling only persists state to `settings.json`.
- The `index.html` template (legacy Vietnamese-UI bidirectional stream page) exists in the codebase but is **not served by any route** in `app.py`.
- Hardware video encoders (`h264_v4l2m2m`, `h264_omx`) are intentionally excluded due to VCHIQ deadlock risk; `libx264` CPU encoding is the only supported encoder.
- The robot operates as a single-operator device; no authentication, authorization, or multi-user session management is implemented.
- `config.py` defines independent `CAMERA_TYPE`, `CONTROLLER_TYPE`, and `GPS_TYPE` constants, allowing any combination of hardware components.
- When `CONTROLLER_TYPE="SERIAL_CONTROLLER"`, an Arduino or similar microcontroller must be connected via the configured serial port and programmed to respond to single-character command strings.
- For GPS functionality, an NMEA-compatible GPS module must be connected via serial port.
- For the `IPCamera` implementation, OpenCV (`cv2`) must be installed and a valid RTSP stream URL must be configured in `config.py`.

---

## Known Limitations (Current State)

The following limitations exist in the current codebase and are documented here for completeness:

| ID     | Area          | Limitation |
|--------|---------------|------------|
| LIM-01 | I/O Devices   | GPIO output for the 4 toggle devices is not implemented. Toggle operations only update `settings.json`. |
| LIM-02 | Video Encoder | Only `libx264` (CPU) encoder is supported. Hardware encoders are blocked due to VCHIQ deadlock risk. |
| LIM-03 | Routing       | `index.html` (legacy page) is not reachable via any Flask route; `dashboard.html` is served at `/`. |
| LIM-04 | Resolution    | Only two resolution options are supported: 320×240 and 640×480. |
| LIM-05 | Security      | No authentication on any API endpoint. The server is accessible to anyone on the network. |
| LIM-06 | TLS           | Self-signed certificate requires manual browser trust acceptance. |
| LIM-07 | Motor trim    | Trim is applied to PWM calculation but silently no-ops when GPIO is unavailable. |
| LIM-09 | HAL           | The `PiCamera`, `IPCamera`, `GPIOController`, `SerialController`, `BaseCamera`, `BaseController` classes are specified but not yet implemented in the codebase. |
| LIM-10 | GPS           | The `BaseGPS` and `SerialGPS` classes are specified but not yet implemented. GPS coordinates are not yet available. |
| LIM-11 | Minimap       | The minimap UI component is specified but not yet implemented. |
| LIM-12 | config.py     | `config.py` with independent `CAMERA_TYPE`, `CONTROLLER_TYPE`, and `GPS_TYPE` constants is specified but not yet implemented; current code uses hardcoded values in `app.py`. |
