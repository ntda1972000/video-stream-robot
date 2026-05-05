# Video Stream Robot

Professional robot-streaming stack with layered Python architecture, GPIO motor control, web-based joystick/IO control, and WebRTC proxying via MediaMTX.

## Architecture

The project now follows a clean package structure under `robot_stream`:

- `robot_stream/api`: HTTP routes and server bootstrapping
- `robot_stream/config`: settings validation and persistence
- `robot_stream/runtime`: process supervision, certificate handling, network stats
- `robot_stream/control`: GPIO adapters, motor and IO drivers, pin layout
- `robot_stream/services`: orchestration and business logic
- `robot_stream/streaming`: camera/audio publisher runtime

Top-level files are intentionally thin wrappers:

- `app.py`: server entrypoint
- `publisher.py`: stream publisher entrypoint

## Project Layout

```text
video-stream-robot/
  app.py
  publisher.py
  robot_stream/
    api/
      web_app.py
    config/
      settings_store.py
    runtime/
      process_supervisor.py
      network_monitor.py
      certificate_manager.py
    control/
      gpio_adapter.py
      motor_driver.py
      io_driver.py
      pin_layout.py
    services/
      robot_service.py
    streaming/
      publisher_app.py
  templates/
    dashboard.html
    index.html
  settings.json
  start.sh
  setup_robot.sh
```

## GPIO Configuration (BCM)

### L298N 4-Motor Drive

- Motor 0 (left): IN1=5, IN2=6, EN=12
- Motor 1 (right): IN1=13, IN2=19, EN=26
- Motor 2 (left): IN1=16, IN2=20, EN=21
- Motor 3 (right): IN1=23, IN2=24, EN=25

Joystick differential drive mapping:

- turn = x
- throttle = y
- left_speed = y + x
- right_speed = y - x

### 4 Digital Outputs

- IO 0: GPIO 17
- IO 1: GPIO 27
- IO 2: GPIO 22
- IO 3: GPIO 4

Web IO toggles remain synchronized with `settings.json` and the `/api/io_toggle` endpoint.

## Runtime Behavior

- If `RPi.GPIO` is available, the app drives real GPIO pins.
- If not available (development machine), it automatically falls back to an in-memory mock backend.
- Existing dashboard endpoints and payload contracts are preserved.
