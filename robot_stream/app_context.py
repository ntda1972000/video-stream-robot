import os

from robot_stream.config.settings_store import SettingsStore
from robot_stream.control import DEFAULT_IO_PINS, DEFAULT_MOTOR_PIN_CONFIG, L298NFourMotorController, OutputController
from robot_stream.control.gpio_adapter import create_gpio_backend
from robot_stream.runtime.network_monitor import NetworkMonitor
from robot_stream.runtime.process_supervisor import RuntimeProcessSupervisor
from robot_stream.services.robot_service import RobotService


class AppContext:
    """Builds and owns app-level dependencies."""

    def __init__(self, project_root: str):
        settings_path = os.path.join(project_root, "settings.json")
        self.settings = SettingsStore(settings_path)
        self.processes = RuntimeProcessSupervisor(project_root)
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
