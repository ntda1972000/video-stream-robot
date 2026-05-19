from abc import ABC, abstractmethod


class BaseCamera(ABC):
    @abstractmethod
    def get_frame(self) -> bytes:
        """Capture and return a single JPEG-encoded frame. Raises RuntimeError on failure."""
