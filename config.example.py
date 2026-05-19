# config.example.py — Hardware configuration template
#
# Copy this file to config.py and adjust the settings for your hardware.
# config.py is NOT committed to the repo (.gitignore).
#
# Each component is selected independently — mix and match freely:
#   CAMERA_TYPE      picks which camera implementation is used
#   CONTROLLER_TYPE  picks which motor controller is used
#   GPS_TYPE         picks the GPS source (or disables GPS)

# ---------------------------------------------------------------------------
# Camera — pick ONE type, fill in the matching _SETTINGS entry
# ---------------------------------------------------------------------------
CAMERA_TYPE = "PI_CAMERA"
# Options:
#   "PI_CAMERA"   — Raspberry Pi CSI camera via picamera2 (requires: python3-picamera2)
#   "IP_CAMERA"   — Network/RTSP camera via OpenCV (requires: opencv-python-headless)
#   "USB_CAMERA"  — USB webcam via OpenCV (requires: opencv-python-headless)

CAMERA_SETTINGS = {
    # Raspberry Pi CSI camera (picamera2)
    "PI_CAMERA": {
        "RESOLUTION": (640, 480),   # (width, height) — must match publisher.py settings
    },
    # IP / RTSP camera
    "IP_CAMERA": {
        "RTSP_URL": "rtsp://192.168.1.100:8554/stream",   # full RTSP URL of the camera feed
    },
    # USB webcam (cv2.VideoCapture index)
    "USB_CAMERA": {
        "DEVICE_INDEX": 0,   # 0 = first USB camera, 1 = second, etc.
    },
}

# ---------------------------------------------------------------------------
# Motor Controller — pick ONE type
# ---------------------------------------------------------------------------
CONTROLLER_TYPE = "GPIO_CONTROLLER"
# Options:
#   "GPIO_CONTROLLER"    — L298N / L293D H-bridge wired directly to GPIO (BCM numbering)
#   "SERIAL_CONTROLLER"  — Arduino or other MCU on a serial port receiving single-byte commands

CONTROLLER_SETTINGS = {
    # Direct GPIO H-bridge (e.g. L298N)
    # ENA/ENB jumpers must be set to 5 V (always enabled).
    "GPIO_CONTROLLER": {
        "PIN_L_PWM": 17,   # BCM pin — left motor speed
        "PIN_L_DIR": 27,   # BCM pin — left motor direction
        "PIN_R_PWM": 22,   # BCM pin — right motor speed
        "PIN_R_DIR": 23,   # BCM pin — right motor direction
        "PWM_HZ":    100,  # PWM frequency in Hz
    },
    # Arduino / serial MCU
    # The MCU must accept single ASCII bytes: f=forward b=backward l=left r=right s=stop
    "SERIAL_CONTROLLER": {
        "PORT":     "/dev/ttyUSB0",   # serial device path
        "BAUDRATE": 9600,
    },
}

# ---------------------------------------------------------------------------
# GPS — pick ONE type (or "NONE" to disable)
# ---------------------------------------------------------------------------
GPS_TYPE = "NONE"
# Options:
#   "SERIAL_GPS"  — NMEA 0183 GPS module on a serial port (requires: pyserial, pynmea2)
#   "NONE"        — GPS disabled; /api/status returns gps_lat=null, gps_lon=null

GPS_SETTINGS = {
    # Serial GPS (e.g. u-blox, SIM28, NEO-6M)
    # Wire: GPS TX → Pi RX (e.g. /dev/ttyS0 on GPIO 15)
    "SERIAL_GPS": {
        "PORT":     "/dev/ttyS0",   # serial device — /dev/ttyS0 (UART) or /dev/ttyUSB0 (USB adapter)
        "BAUDRATE": 9600,
    },
}
