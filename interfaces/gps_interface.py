from abc import ABC, abstractmethod


class BaseGPS(ABC):
    @abstractmethod
    def get_coordinates(self) -> tuple[float, float] | None:
        """Return (latitude, longitude) in decimal degrees, or None if no GPS fix."""
