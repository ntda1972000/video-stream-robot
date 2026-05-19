/specify

Update the existing `SPEC.md` file with the following major refactoring goals and new features. The objective is to evolve the project into a more professional, modular, scalable, and feature-rich application.

---

## 1. Refactoring Goal: Hardware Abstraction Layer

Modify the project specification to decouple the application logic from specific hardware. This will be achieved by introducing abstraction layers for all hardware-dependent components.

### 1.1. Camera Abstraction
- **Requirement:** The system must support multiple camera types.
- **Implementation:**
    - Define a `BaseCamera` abstract interface in a new file, `interfaces/camera_interface.py`. This interface must define a core method: `get_frame()`.
    - Specify two concrete implementation classes that inherit from `BaseCamera`:
        1.  `PiCamera` in `implementations/pi_camera.py`: This class will use the `picamera` library, specific to Raspberry Pi.
        2.  `IPCamera` in `implementations/ip_camera.py`: This class will use OpenCV to read a network video stream (e.g., RTSP).

### 1.2. Robot Controller Abstraction
- **Requirement:** The system must support different robot motor controllers.
- **Implementation:**
    - Define a `BaseController` abstract interface in a new file, `interfaces/controller_interface.py`. This interface must define methods like `forward()`, `backward()`, `left()`, `right()`, and `stop()`.
    - Specify two concrete implementation classes that inherit from `BaseController`:
        1.  `GPIOController` in `implementations/gpio_controller.py`: For direct control of motors via Raspberry Pi's GPIO pins.
        2.  `SerialController` in `implementations/serial_controller.py`: To send control commands (e.g., "f", "b", "s") over a serial port to an external microcontroller like an Arduino.

### 1.3. Configuration
- **Requirement:** The application must be easily configurable to switch between hardware setups.
- **Implementation:**
    - Add a new section to the spec describing a `config.py` file. This file will define a "hardware profile" (e.g., `PROFILE="RASPBERRY_PI"` or `PROFILE="TX_BOX"`).
    - The main application logic (`app.py`) will read this profile at startup to decide which concrete `Camera` and `Controller` classes to instantiate.

---

## 2. New Features

Incorporate the following new features into the specification.

### 2.1. GPS and Geolocation
- **Requirement:** The robot must be able to determine and report its geographical coordinates.
- **Implementation:**
    - Introduce a new GPS component, also using an abstraction layer.
    - Define a `BaseGPS` abstract interface in `interfaces/gps_interface.py`. This must define a method `get_coordinates()`, which should return latitude and longitude.
    - Specify an initial concrete implementation, `SerialGPS` in `implementations/serial_gps.py`, which reads NMEA data from a GPS module connected via a serial port.
    - The main application will periodically fetch the coordinates and make them available to the UI.

### 2.2. Toggleable Minimap on UI
- **Requirement:** The web control interface must display the robot's position on a map.
- **Implementation:**
    - On the main control page (where the camera stream is shown), add a **minimap** section.
    - The minimap will display a 2D map and an icon representing the robot's current position, updated using data from the new GPS component.
    - The minimap's visibility must be **toggleable** (can be turned on or off by the user).
    - The on/off toggle button for the minimap **must use the same icon set and visual style** as the speaker and microphone buttons to ensure UI consistency.

---

Please apply all these changes to the `SPEC.md` file to reflect the new, improved architecture and feature set.
