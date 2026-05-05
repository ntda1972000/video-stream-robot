from config_manager import SettingsManager
from controllable_components.io_controller import OutputController
from controllable_components.l298n_controller import L298NFourMotorController
from network_monitor import NetworkMonitor
from process_manager import RuntimeProcessManager


class RobotService:
    """Coordinates app state and runtime operations behind route handlers."""

    def __init__(
        self,
        settings: SettingsManager,
        processes: RuntimeProcessManager,
        network: NetworkMonitor,
        motor_controller: L298NFourMotorController,
        output_controller: OutputController,
    ):
        self.settings = settings
        self.processes = processes
        self.network = network
        self.motor_controller = motor_controller
        self.output_controller = output_controller
        self._ctrl = {"x": 0.0, "y": 0.0}

    def start_runtime(self) -> None:
        self.processes.start_all()
        self.processes.start_watchdog()
        self.network.start()
        self.output_controller.apply_states(device["state"] for device in self.settings.settings["io_devices"])

    def status_payload(self) -> dict:
        net = self.network.stats()
        ok = self.processes.mediamtx_active() and self.processes.publisher_active()
        return {
            "resolution": self.settings.settings["resolution"],
            "fps": self.settings.settings["fps"],
            "rotation": self.settings.settings.get("rotation", 0),
            "stream_mode": "webrtc",
            "mediamtx_active": self.processes.mediamtx_active(),
            "publisher_active": self.processes.publisher_active(),
            "camera_ok": ok,
            "net_iface": net["iface"],
            "net_tx_kbps": net["tx_kbps"],
            "net_rx_kbps": net["rx_kbps"],
            "io_devices": [
                {"name": d["name"], "state": d["state"]}
                for d in self.settings.settings["io_devices"]
            ],
        }

    def update_control(self, x: float, y: float) -> dict:
        self._ctrl["x"] = max(-1.0, min(1.0, float(x)))
        self._ctrl["y"] = max(-1.0, min(1.0, float(y)))
        self.motor_controller.drive(self._ctrl["x"], self._ctrl["y"])
        return dict(self._ctrl)

    def toggle_io(self, index: int) -> tuple[int, bool]:
        idx, state = self.settings.toggle_io(index)
        self.output_controller.set_state(idx, state)
        return idx, state

    def rename_io(self, index: int, name: str) -> tuple[int, str]:
        return self.settings.rename_io(index, name)

    def set_rotation(self, rotation: int) -> int:
        return self.settings.set_rotation(rotation)

    def update_stream_settings(self, resolution, fps) -> dict:
        changed = self.settings.set_controlled_stream_settings(resolution, fps)
        if changed:
            self.processes.restart_publisher()
        return {
            "status": "ok",
            "resolution": self.settings.settings["resolution"],
            "fps": self.settings.settings["fps"],
        }
