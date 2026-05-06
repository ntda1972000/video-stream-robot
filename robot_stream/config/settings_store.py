import json
import logging
import os

DEFAULT_SETTINGS = {
    "resolution": [640, 480],
    "fps": 20,
    "rotation": 0,
    "io_devices": [
        {"name": "Device 1", "state": False},
        {"name": "Device 2", "state": False},
        {"name": "Device 3", "state": False},
        {"name": "Device 4", "state": False},
    ],
}

RESOLUTION_OPTIONS = [[320, 240], [640, 480]]
FPS_OPTIONS = [5, 10, 15, 20, 25, 30]


class SettingsStore:
    def __init__(self, settings_file: str, default_settings: dict | None = None):
        self._settings_file = settings_file
        self._default_settings = default_settings or DEFAULT_SETTINGS
        self._data = self._build_default()

    def _build_default(self) -> dict:
        data = dict(self._default_settings)
        data["io_devices"] = [{"name": f"Device {i+1}", "state": False} for i in range(4)]
        return data

    def load(self) -> None:
        if os.path.exists(self._settings_file):
            try:
                with open(self._settings_file) as handle:
                    saved = json.load(handle)
                for key, value in self._default_settings.items():
                    if key not in saved:
                        saved[key] = value
                saved["resolution"] = list(saved["resolution"])
                saved["io_devices"] = list(saved.get("io_devices", []))[:4]
                while len(saved["io_devices"]) < 4:
                    idx = len(saved["io_devices"]) + 1
                    saved["io_devices"].append({"name": f"Device {idx}", "state": False})
                self._data = saved
                return
            except Exception:
                pass
        self._data = self._build_default()

    def save(self) -> None:
        try:
            with open(self._settings_file, "w") as handle:
                json.dump(self._data, handle, indent=2)
        except Exception as exc:
            logging.warning("Could not save settings: %s", exc)

    @property
    def data(self) -> dict:
        return self._data
