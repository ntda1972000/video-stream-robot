from robot_stream.config.settings_store import SettingsStore
from robot_stream.control.io_driver import OutputController
from robot_stream.control.motor_driver import L298NFourMotorController
from robot_stream.runtime.network_monitor import NetworkMonitor
from robot_stream.runtime.process_supervisor import RuntimeProcessSupervisor


class RobotService:
    """Coordinates robot runtime state and control actions behind the API."""

    def __init__(
        self,
        settings: SettingsStore,
        processes: RuntimeProcessSupervisor,
        network: NetworkMonitor,
        motor_controller: L298NFourMotorController,
        output_controller: OutputController,
    ):
        self.settings = settings
        self.processes = processes
        self.network = network
        self.motor_controller = motor_controller
        self.output_controller = output_controller
        self._control_state = {"x": 0.0, "y": 0.0}

    def start_runtime(self) -> None:
        self.processes.start_all()
        self.processes.start_watchdog()
        self.network.start()
        self.output_controller.apply_states(device["state"] for device in self.settings.settings["io_devices"])

    def status_payload(self) -> dict:
        network_stats = self.network.stats()
        camera_ok = self.processes.mediamtx_active() and self.processes.publisher_active()
        return {
            "resolution": self.settings.settings["resolution"],
            "fps": self.settings.settings["fps"],
            "rotation": self.settings.settings.get("rotation", 0),
            "stream_mode": "webrtc",
            "mediamtx_active": self.processes.mediamtx_active(),
            "publisher_active": self.processes.publisher_active(),
            "camera_ok": camera_ok,
            "net_iface": network_stats["iface"],
            "net_tx_kbps": network_stats["tx_kbps"],
            "net_rx_kbps": network_stats["rx_kbps"],
            "io_devices": [
                {"name": device["name"], "state": device["state"]}
                for device in self.settings.settings["io_devices"]
            ],
        }

    def update_control(self, x: float, y: float) -> dict:
        self._control_state["x"] = max(-1.0, min(1.0, float(x)))
        self._control_state["y"] = max(-1.0, min(1.0, float(y)))
        self.motor_controller.drive(self._control_state["x"], self._control_state["y"])
        return dict(self._control_state)

    def toggle_io(self, index: int) -> tuple[int, bool]:
        idx, state = self.settings.toggle_io(index)
        self.output_controller.set_state(idx, state)
        return idx, state

    def rename_io(self, index: int, name: str) -> tuple[int, str]:
        return self.settings.rename_io(index, name)

    def set_rotation(self, rotation: int) -> int:
        return self.settings.set_rotation(rotation)

    def update_stream_settings(self, resolution, fps) -> dict:
        changed = self.settings.set_stream_settings(resolution, fps)
        if changed:
            self.processes.restart_publisher()
        return {
            "status": "ok",
            "resolution": self.settings.settings["resolution"],
            "fps": self.settings.settings["fps"],
        }
