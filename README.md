# video-stream-robot

## Controllable Components

GPIO-based controllable logic is grouped in [controllable_components](controllable_components):

- [controllable_components/l298n_controller.py](controllable_components/l298n_controller.py): 4-motor differential drive via joystick (`/api/control`)
- [controllable_components/io_controller.py](controllable_components/io_controller.py): 4 digital outputs via web IO toggles (`/api/io_toggle`)
- [controllable_components/gpio_backend.py](controllable_components/gpio_backend.py): auto-selects `RPi.GPIO` on Raspberry Pi, falls back to mock backend elsewhere
- [controllable_components/pin_config.py](controllable_components/pin_config.py): pin mapping and defaults

## GPIO Pin Configuration (BCM)

### L298N 4 Motors

- Motor 0 (left): `IN1=5`, `IN2=6`, `EN=12`
- Motor 1 (right): `IN1=13`, `IN2=19`, `EN=26`
- Motor 2 (left): `IN1=16`, `IN2=20`, `EN=21`
- Motor 3 (right): `IN1=23`, `IN2=24`, `EN=25`

Joystick mapping:

- `x` controls turn
- `y` controls throttle
- Left speed = `y + x`
- Right speed = `y - x`

### 4 Digital IO Outputs

- IO 0: GPIO `17`
- IO 1: GPIO `27`
- IO 2: GPIO `22`
- IO 3: GPIO `4`

These outputs are synchronized with the existing web IO state (`settings.json` + `/api/io_toggle`).
