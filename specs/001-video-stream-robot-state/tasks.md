# Tasks: Video Stream Robot — HAL Refactoring & New Features

**Input**: Design documents from `specs/001-video-stream-robot-state/`

**Prerequisites**: plan.md ✓ | spec.md ✓ | research.md ✓ | data-model.md ✓ | contracts/api.md ✓ | quickstart.md ✓

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US9); absent for setup and foundational phases
- All file paths are relative to repo root

---

## Phase 1: Setup

**Purpose**: Create the new file structure, base configuration file, test scaffolding, and update the setup script. Must complete before any interface or implementation work.

- [X] T001 Create directory structure: `interfaces/`, `implementations/`, `tests/unit/`, `tests/integration/` at repo root
- [X] T002 Create `config.py` at repo root with `CAMERA_TYPE="PI_CAMERA"`, `CONTROLLER_TYPE="GPIO_CONTROLLER"`, `GPS_TYPE="NONE"`, and fully populated `CAMERA_SETTINGS`, `CONTROLLER_SETTINGS`, `GPS_SETTINGS` dicts per `data-model.md` (all three camera types, both controller types, SERIAL_GPS)
- [X] T003 [P] Create `tests/conftest.py`: patch `sys.modules` before any import with `MagicMock()` stubs for `RPi`, `RPi.GPIO`, `picamera2`, `cv2`, `serial` so all tests run on non-Pi dev machines
- [X] T004 [P] Update `setup_robot.sh`: add `python3-picamera2` to the `apt-get install` line; add `pyserial pynmea2 opencv-python-headless pytest pytest-mock` to the `.venv/bin/pip install` line

**Checkpoint**: Directory scaffolding exists, `config.py` is present with all profile options, `tests/conftest.py` mocks hardware modules, setup script installs new dependencies.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the three abstract base interfaces. All concrete implementations and factory code in `app.py` depend on these. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: Phases 3–5 cannot start until T005–T008 are done.

- [X] T005 [P] Create `BaseCamera` ABC in `interfaces/camera_interface.py`: inherit `abc.ABC`; define `@abstractmethod get_frame(self) -> bytes` with docstring "Capture and return a single JPEG-encoded frame. Raises RuntimeError on failure." (FR-047)
- [X] T006 [P] Create `BaseController` ABC in `interfaces/controller_interface.py`: inherit `abc.ABC`; define `@abstractmethod` methods `forward()`, `backward()`, `left()`, `right()`, `stop()` each returning `None` with one-line docstrings (FR-051)
- [X] T007 [P] Create `BaseGPS` ABC in `interfaces/gps_interface.py`: inherit `abc.ABC`; define `@abstractmethod get_coordinates(self) -> tuple[float, float] | None` with docstring "Return (latitude, longitude) in decimal degrees, or None if no GPS fix." (FR-057)
- [X] T008 [P] Create `interfaces/__init__.py` and `implementations/__init__.py` as empty files to make both directories importable Python packages

**Checkpoint**: All three ABCs exist and are importable. Concrete implementations can now be written.

---

## Phase 3: User Story 7 — Switch Between Camera Types (Priority: P2)

**Goal**: Deliver three concrete `BaseCamera` implementations and a factory in `app.py` so the active camera is selected purely from `config.py` with no camera-specific logic in `app.py`.

**Independent Test**: Set `CAMERA_TYPE="USB_CAMERA"` with `DEVICE_INDEX=0`, start the app on a dev machine with a webcam, call `_camera.get_frame()` from a Python shell — should return JPEG bytes. Changing to `CAMERA_TYPE="PI_CAMERA"` on a Pi should work identically.

- [X] T009 [P] [US7] Implement `PiCamera(BaseCamera)` in `implementations/pi_camera.py`: `__init__` receives `settings` dict, reads `RESOLUTION` tuple, lazily imports `picamera2.Picamera2`, creates still config (`RGB888`), calls `start()`; `get_frame()` captures via `capture_file()` into `io.BytesIO`, returns JPEG bytes (research.md R-01, data-model.md PiCamera)
- [X] T010 [P] [US7] Implement `IPCamera(BaseCamera)` in `implementations/ip_camera.py`: `__init__` receives `settings` dict, reads `RTSP_URL`, lazily imports `cv2`, opens `cv2.VideoCapture(url, cv2.CAP_FFMPEG)`; `get_frame()` calls `read()`, encodes to JPEG via `imencode(".jpg")`, raises `RuntimeError` if `read()` returns `False` (research.md R-02)
- [X] T011 [P] [US7] Implement `USBCamera(BaseCamera)` in `implementations/usb_camera.py`: `__init__` receives `settings` dict, reads `DEVICE_INDEX`, lazily imports `cv2`, opens `cv2.VideoCapture(index)`; `get_frame()` calls `read()`, encodes to JPEG, raises `RuntimeError` if read fails (research.md R-02)
- [X] T012 [US7] Add camera factory block inside `app.py` `_start_bg_threads()`: import `CAMERA_TYPE`, `CAMERA_SETTINGS` from `config`; use lazy `if/elif/else` to instantiate `PiCamera`, `IPCamera`, or `USBCamera` with `CAMERA_SETTINGS[CAMERA_TYPE]`; assign result to module-level `_camera`; raise `ValueError` for unknown `CAMERA_TYPE` (FR-050)

**Checkpoint**: US7 complete. `_camera.get_frame()` returns JPEG bytes regardless of which camera type is configured in `config.py`. Changing `CAMERA_TYPE` and restarting uses a different implementation — no change to `app.py` body.

---

## Phase 4: User Story 8 — Switch Between Motor Controllers (Priority: P2)

**Goal**: Extract all inline GPIO motor code from `app.py` into `GPIOController`, add `SerialController`, and wire both through a factory. After this phase `app.py` contains zero GPIO-specific code.

**Independent Test**: Set `CONTROLLER_TYPE="GPIO_CONTROLLER"` on a Pi, call `/api/control` with `{"x":0,"y":1}` — motors spin forward. Set `CONTROLLER_TYPE="SERIAL_CONTROLLER"` with an Arduino connected — byte `b"f"` is transmitted on the serial port.

- [X] T013 [US8] Create `GPIOController(BaseController)` in `implementations/gpio_controller.py`: constructor reads `PIN_L_PWM`, `PIN_L_DIR`, `PIN_R_PWM`, `PIN_R_DIR`, `PWM_HZ` from `settings` dict; migrate `_setup_motors`, `_drive_motors`, `_stop_motors`, `_cleanup_gpio` logic from `app.py` into this class; `forward(speed=1.0)` / `backward(speed=1.0)` call `_drive_motors(±speed, ±speed)`; `left()` / `right()` apply differential; `stop()` zeros PWM; all methods are silent no-ops when `RPi.GPIO` is unavailable (FR-052, data-model.md GPIOController)
- [X] T014 [P] [US8] Create `SerialController(BaseController)` in `implementations/serial_controller.py`: constructor opens `serial.Serial(PORT, BAUDRATE, timeout=1)`; `forward()` → `write(b"f")`, `backward()` → `write(b"b")`, `left()` → `write(b"l")`, `right()` → `write(b"r")`, `stop()` → `write(b"s")`; `close()` shuts serial port (FR-053, research.md R-03)
- [X] T015 [US8] Add controller factory block inside `app.py` `_start_bg_threads()` (after MediaMTX/publisher start): import `CONTROLLER_TYPE`, `CONTROLLER_SETTINGS` from `config`; instantiate `GPIOController` or `SerialController` via lazy import with `CONTROLLER_SETTINGS[CONTROLLER_TYPE]`; assign to module-level `_controller`; register `_controller.stop()` with `atexit` (FR-054)
- [X] T016 [US8] Remove all inline GPIO code from `app.py`: delete module-level constants `_MOTOR_L_PWM`, `_MOTOR_L_DIR`, `_MOTOR_R_PWM`, `_MOTOR_R_DIR`, `_MOTOR_PWM_HZ`, `_pwm_l`, `_pwm_r`, `_GPIO_READY`, `_GPIO_AVAILABLE`, `_GPIO`; delete functions `_setup_motors`, `_drive_motors`, `_stop_motors`, `_cleanup_gpio`; remove their `atexit.register` calls; confirm no references remain (FR-054)

**Checkpoint**: US8 complete. `app.py` has no GPIO imports or motor constants. `GPIOController` and `SerialController` are independently testable. Switching `CONTROLLER_TYPE` in `config.py` changes the motor backend without touching `app.py`.

---

## Phase 5: User Story 2 — Drive the Robot via Browser Joystick (Priority: P2)

**Goal**: Re-wire `/api/control` to dispatch through the active `BaseController` instance instead of the now-deleted inline GPIO functions. Tank-drive mixing and motor_trim logic move into the dispatch call.

**Independent Test**: POST `{"x": 0.5, "y": 0.8}` to `/api/control` on a Pi with GPIO controller — differential PWM applied. On a non-Pi host with `_controller=None` — returns `{"status": "ok"}` without error (FR-035, spec US2 scenario 4).

- [X] T017 [US2] Update `/api/control` route in `app.py`: compute `raw_l = y + x`, `raw_r = y - x` with motor_trim clamping (existing logic); determine dominant command from `(raw_l, raw_r)` — forward if both >0.05, backward if both <-0.05, left if raw_l < raw_r and |diff|>0.1, right if raw_r < raw_l and |diff|>0.1, else stop; call corresponding `_controller` method if `_controller` is not `None`; for `GPIOController` additionally pass speed magnitude; return `{"status": "ok", "x": x, "y": y}` (FR-035, US2)

**Checkpoint**: US2 complete. Joystick commands route through `_controller`. `app.py` has no GPIO code. Motor response works for both `GPIOController` (continuous PWM) and `SerialController` (discrete byte).

---

## Phase 6: User Story 1 — Watch Live Video Stream (Priority: P1)

**Goal**: Confirm the existing RTSP→MediaMTX→WebRTC pipeline, TLS cert generation, watchdog, and dashboard WebRTC element are all intact after the `app.py` refactoring in Phases 3–5.

**Independent Test**: Open `https://<robot-ip>:5000/` — dashboard loads, WebRTC video stream starts within a few seconds, watchdog log messages appear in `server.log`.

- [X] T018 [US1] Verify `_start_bg_threads()` in `app.py` still calls `start_mediamtx()`, waits 2 s, calls `start_publisher()`, starts `NetworkMonitor`, and starts the watchdog thread — in that exact order — after the factory additions from T012 and T015 (FR-044, FR-045)
- [X] T019 [P] [US1] Verify `publisher.py` is unchanged: `detect_camera_cmd()` still selects `rpicam-vid`/`libcamera-vid`, video bitrate scaling formula is intact, RTSP push to `rtsp://localhost:8554/robot` is unchanged, and `_SETTINGS_FILE` read for resolution/fps still works (FR-001 through FR-005)

**Checkpoint**: US1 complete. Live video stream works end-to-end after all `app.py` refactoring. No regressions in MediaMTX management, publisher lifecycle, TLS cert, or WebRTC proxy routes.

---

## Phase 7: User Story 3 + User Story 4 — Audio Pipeline (Priority: P3)

**Goal**: Confirm both audio paths (robot mic → browser, browser mic → robot) are intact after the refactoring. No new code — verification only.

**Independent Test (US3)**: Speak near the robot's USB mic — audio plays in the browser alongside the video stream. With no USB mic — stream plays video-only without error.
**Independent Test (US4)**: Click mic button in dashboard — browser mic audio plays on the Pi's speaker via PulseAudio.

- [X] T020 [US3] Verify `publisher.py` audio path: `has_alsa_mic()` check via `arecord -l`, ALSA capture at `44100 Hz mono`, `libopus` at `32k voip` mode, and video-only fallback are all present and unchanged (FR-006, FR-007, FR-008)
- [X] T021 [US4] Verify `_write_mtx_config()` in `app.py` still generates the `from-browser` path with `runOnReady` FFmpeg→PulseAudio command and `runOnReadyRestart: yes`; verify `/proxy/whip` route forwards SDP to `http://127.0.0.1:8889/from-browser/whip` (FR-009, FR-010)

**Checkpoint**: US3 + US4 complete. Both audio directions work. No audio code was touched during HAL refactoring.

---

## Phase 8: User Story 5 + User Story 6 — Settings & I/O Devices (Priority: P4 / P5)

**Goal**: Confirm settings management and I/O toggle/rename endpoints are intact after refactoring. No new code — verification only.

**Independent Test (US5)**: POST `{"resolution": [320, 240]}` to `/api/update_settings` — `settings.json` updates and publisher restarts.
**Independent Test (US6)**: POST `{"index": 0}` to `/api/io_toggle` — device state flips in `settings.json`.

- [X] T022 [P] [US5] Verify `load_settings()`, `save_settings()`, `/api/update_settings`, and `/api/rotation` in `app.py` are intact: publisher restart on resolution/fps change (0.5 s wait), motor_trim save without restart, rotation validation (0/90/180/270), fallback to `DEFAULT_SETTINGS` on corrupt file (FR-023 through FR-027)
- [X] T023 [P] [US6] Verify `/api/io_toggle` and `/api/io_rename` in `app.py` are intact: index validation (0–3, HTTP 400 on invalid), state flip + persist, name trim to 32 chars + persist, exactly 4 `io_devices` entries maintained (FR-028 through FR-031)

**Checkpoint**: US5 + US6 complete. Settings and I/O routes function correctly post-refactor.

---

## Phase 9: User Story 9 — GPS + Minimap (Priority: P4)

**Goal**: Add `SerialGPS` implementation, GPS polling thread in `app.py`, extend `/api/status` with coordinates, and add a Leaflet.js minimap with toggle button to `dashboard.html`.

**Independent Test**: With `GPS_TYPE="SERIAL_GPS"` and a GPS module on `/dev/ttyS0`, GET `/api/status` returns `gps_lat` and `gps_lon` as non-null floats. Open dashboard — minimap shows robot position. Click toggle button — map hides/shows. Toggle button visually matches speaker/mic buttons.

- [X] T024 [US9] Implement `SerialGPS(BaseGPS)` in `implementations/serial_gps.py`: constructor opens `serial.Serial(PORT, BAUDRATE, timeout=1)`; `get_coordinates()` reads up to 20 lines, decodes `ascii` (ignore errors), skips non-`$` lines, calls `pynmea2.parse(line)`, returns `(msg.latitude, msg.longitude)` on first sentence with non-zero `latitude`, catches `pynmea2.ParseError` and continues; returns `None` after 20 failed lines (FR-058, research.md R-04)
- [X] T025 [US9] Add GPS factory and polling thread to `app.py` `_start_bg_threads()`: if `GPS_TYPE=="SERIAL_GPS"` instantiate `SerialGPS(GPS_SETTINGS["SERIAL_GPS"])`; else `_gps=None`; start daemon thread that calls `_gps.get_coordinates()` every 1 s and writes to module-level `_gps_coords = {"lat": ..., "lon": ...}`; handle exceptions silently (FR-059)
- [X] T026 [US9] Extend `GET /api/status` in `app.py` to include `"gps_lat": _gps_coords["lat"]` and `"gps_lon": _gps_coords["lon"]` (float or `null`); initialize `_gps_coords = {"lat": None, "lon": None}` at module level (FR-060, contracts/api.md)
- [X] T027 [P] [US9] Add Leaflet.js CDN to `templates/dashboard.html` `<head>`: `<link>` for `leaflet.css` and `<script>` for `leaflet.js` both from `https://unpkg.com/leaflet@1.9.4/dist/` (research.md R-05)
- [X] T028 [US9] Add minimap container to `templates/dashboard.html`: place `<div id="minimap">` below the `.shell` main grid, styled `width:100%; height:220px; display:none; border-radius:10px; overflow:hidden; border:1px solid #3f3f3f`; in JS initialize `L.map("minimap").setView([0,0],15)`, add OSM tile layer, add `L.marker([0,0])` as `robotMarker`; write `updateMinimap(lat,lon)` to call `robotMarker.setLatLng` + `map.setView` (FR-061, FR-062)
- [X] T029 [US9] Add minimap toggle button to `templates/dashboard.html` `.ov-br` cluster: button uses `.ov-btn` CSS class (30×30px circular, `border-radius:50%`, `backdrop-filter:blur(6px)`) placed as a third `.ov-item` alongside the existing speaker and mic items; SVG map-pin icon; onclick toggles `#minimap` `display` between `none`/`block`, toggles `.active` class on button, calls `map.invalidateSize()` when shown (FR-063, FR-064)
- [X] T030 [US9] Wire minimap to status polling in `templates/dashboard.html` JS: in the existing `setInterval` that calls `GET /api/status`, after updating status fields, if `data.gps_lat !== null` call `updateMinimap(data.gps_lat, data.gps_lon)` (do not auto-show map — user must toggle); if null leave minimap state unchanged (FR-062)

**Checkpoint**: US9 complete. GPS coordinates appear in `/api/status`. Dashboard minimap shows robot position when GPS data is available. Toggle button is visually identical to speaker/mic overlay buttons (SC-009, SC-010).

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, `.gitignore` hygiene, and developer experience.

- [X] T031 Add `config.py`, `cert.pem`, `key.pem`, `*.log`, `mediamtx_run.yml` to `.gitignore` (config contains machine-specific hardware paths; certs and logs are generated at runtime)
- [X] T032 [P] Create `config.example.py` at repo root documenting all three camera types, both controllers, and `SERIAL_GPS` with inline comments explaining each setting; this file IS committed to the repo
- [X] T033 [P] Update `README.md`: add "Configuration" section documenting `config.py` setup, new pip/apt packages from `setup_robot.sh`, GPS hardware wiring note, and minimap usage; update "Quick Start" to reference `config.example.py`

**Checkpoint**: All 33 tasks complete. Full HAL refactoring done, GPS and minimap operational, developer documentation updated.

---

## Dependencies

```
Phase 1 (T001–T004)
  └── Phase 2 (T005–T008)
        ├── Phase 3: US7 (T009–T012)   ─┐
        │     T012 depends on T005        │ can overlap
        └── Phase 4: US8 (T013–T016)   ─┤
              T013 depends on T006        │
              T014 depends on T006        │
              T015 depends on T013,T014   │
              T016 depends on T015      ─┘
                  └── Phase 5: US2 (T017)
                        └── Phase 6: US1 (T018–T019)   ─┐
                              Phase 7: US3+US4 (T020–T021) │ can overlap
                              Phase 8: US5+US6 (T022–T023) ┤
                                    └── Phase 9: US9 (T024–T030)
                                              T024 depends on T007
                                              T025 depends on T024
                                              T026 depends on T025
                                              T027–T030 depend on T025,T026
                                                    └── Phase 10 (T031–T033)
```

## Parallel Execution Opportunities

| User Story Phase | Parallel Tasks |
|---|---|
| Phase 2: Foundational | T005, T006, T007, T008 — all different files |
| Phase 3: US7 | T009, T010, T011 — three independent implementation files |
| Phase 4: US8 | T013 and T014 — two independent implementation files |
| Phase 7: US3+US4 | T020 and T021 — different code areas |
| Phase 8: US5+US6 | T022 and T023 — different endpoints |
| Phase 9: US9 | T027 can start as soon as Phase 8 is done; T028, T029 can overlap |
| Phase 10 | T032 and T033 can run in parallel |

## Implementation Strategy

**MVP scope** (deliver working system first): Complete Phases 1–6 (T001–T017) to deliver the full HAL refactoring with all existing features preserved. At that point the robot drives, streams video, and handles audio exactly as before — but through clean, swappable hardware abstractions.

**Increment 2**: Phases 7–8 (T018–T023) verify no audio/settings regressions.

**Increment 3**: Phase 9 (T024–T030) adds GPS and minimap — entirely new capability, isolated to `implementations/serial_gps.py`, `app.py` polling, `/api/status`, and `dashboard.html`.

**Increment 4**: Phase 10 (T031–T033) — polish, always last.
