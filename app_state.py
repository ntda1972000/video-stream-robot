import os

from controllable_components import (
    DEFAULT_IO_PINS,
    DEFAULT_MOTOR_PIN_CONFIG,
    L298NFourMotorController,
    OutputController,
)
from controllable_components.gpio_backend import create_gpio_backend
from config_manager import SettingsManager
from network_monitor import NetworkMonitor
from process_manager import RuntimeProcessManager
from services import RobotService


class AppState:
    """Composes concrete dependencies used by Flask controllers."""

    def __init__(self, base_dir: str):
        settings_file = os.path.join(base_dir, "settings.json")
        self.settings = SettingsManager(settings_file)
        self.processes = RuntimeProcessManager(base_dir)
        self.network = NetworkMonitor()
        self.gpio = create_gpio_backend()
        self.motor_controller = L298NFourMotorController(self.gpio, DEFAULT_MOTOR_PIN_CONFIG)
        self.output_controller = OutputController(self.gpio, DEFAULT_IO_PINS)
        self.robot = RobotService(
            self.settings,
            self.processes,
            self.network,
            self.motor_controller,
            self.output_controller,
        )
