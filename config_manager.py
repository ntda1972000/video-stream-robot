import json
import logging
import os
from typing import Any

from exceptions import ValidationError


RESOLUTION_OPTIONS = [[320, 240], [640, 480]]
FPS_OPTIONS = [5, 10, 15, 20, 25, 30]
DEVICE_COUNT = 4
MAX_DEVICE_NAME_LEN = 32


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


class SettingsManager:
    """Owns settings loading, validation, and persistence."""

    def __init__(self, settings_file: str):
        self._settings_file = settings_file
        self._settings = self._load_settings()

    @property
    def settings(self) -> dict[str, Any]:
        return self._settings

    def _default_io_devices(self) -> list[dict[str, Any]]:
        return [{"name": f"Device {i+1}", "state": False} for i in range(DEVICE_COUNT)]

    def _normalize_io_devices(self, value: Any) -> list[dict[str, Any]]:
        devices = value if isinstance(value, list) else []
        normalized = []

        for i in range(DEVICE_COUNT):
            current = devices[i] if i < len(devices) and isinstance(devices[i], dict) else {}
            name = str(current.get("name", f"Device {i+1}")).strip()[:MAX_DEVICE_NAME_LEN]
            state = bool(current.get("state", False))
            normalized.append({"name": name or f"Device {i+1}", "state": state})

        return normalized

    def _load_settings(self) -> dict[str, Any]:
        if not os.path.exists(self._settings_file):
            settings = dict(DEFAULT_SETTINGS)
            settings["io_devices"] = self._default_io_devices()
            return settings

        try:
            with open(self._settings_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logging.warning("Could not read settings file, using defaults: %s", exc)
            settings = dict(DEFAULT_SETTINGS)
            settings["io_devices"] = self._default_io_devices()
            return settings

        settings = dict(DEFAULT_SETTINGS)
        settings.update(saved if isinstance(saved, dict) else {})

        try:
            settings["resolution"] = self.validate_resolution(settings.get("resolution"))
        except ValidationError:
            settings["resolution"] = list(DEFAULT_SETTINGS["resolution"])

        try:
            settings["fps"] = self.validate_fps(settings.get("fps"))
        except ValidationError:
            settings["fps"] = DEFAULT_SETTINGS["fps"]

        try:
            settings["rotation"] = self.validate_rotation(settings.get("rotation"))
        except ValidationError:
            settings["rotation"] = DEFAULT_SETTINGS["rotation"]

        settings["io_devices"] = self._normalize_io_devices(settings.get("io_devices"))
        return settings

    def save(self) -> None:
        try:
            with open(self._settings_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except OSError as exc:
            logging.warning("Could not save settings: %s", exc)

    def validate_resolution(self, resolution: Any) -> list[int]:
        normalized = list(resolution) if isinstance(resolution, (list, tuple)) else None
        if normalized not in RESOLUTION_OPTIONS:
            raise ValidationError("resolution must be one of supported options")
        return normalized

    def validate_fps(self, fps: Any) -> int:
        normalized = int(fps)
        if normalized not in FPS_OPTIONS:
            raise ValidationError("fps must be one of supported options")
        return normalized

    def validate_rotation(self, rotation: Any) -> int:
        if rotation not in (0, 90, 180, 270):
            raise ValidationError("rotation must be 0, 90, 180 or 270")
        return int(rotation)

    def validate_io_index(self, index: Any) -> int:
        if not isinstance(index, int) or not (0 <= index < DEVICE_COUNT):
            raise ValidationError("index must be 0-3")
        return index

    def sanitize_device_name(self, index: int, name: Any) -> str:
        value = str(name if name is not None else "").strip()[:MAX_DEVICE_NAME_LEN]
        return value or f"Device {index + 1}"

    def set_rotation(self, rotation: Any) -> int:
        value = self.validate_rotation(rotation)
        self._settings["rotation"] = value
        self.save()
        return value

    def toggle_io(self, index: Any) -> tuple[int, bool]:
        idx = self.validate_io_index(index)
        state = not self._settings["io_devices"][idx]["state"]
        self._settings["io_devices"][idx]["state"] = state
        self.save()
        return idx, state

    def rename_io(self, index: Any, name: Any) -> tuple[int, str]:
        idx = self.validate_io_index(index)
        new_name = self.sanitize_device_name(idx, name)
        self._settings["io_devices"][idx]["name"] = new_name
        self.save()
        return idx, new_name

    def set_controlled_stream_settings(self, resolution: Any, fps: Any) -> bool:
        changed = False
        if resolution and isinstance(resolution, (list, tuple)) and list(resolution) in RESOLUTION_OPTIONS:
            self._settings["resolution"] = list(resolution)
            changed = True
        if fps is not None:
            try:
                fps_value = int(fps)
                if fps_value in FPS_OPTIONS:
                    self._settings["fps"] = fps_value
                    changed = True
            except (TypeError, ValueError):
                pass
        if changed:
            self.save()
        return changed
