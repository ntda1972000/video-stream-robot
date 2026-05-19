from abc import ABC, abstractmethod


class BaseController(ABC):
    @abstractmethod
    def forward(self) -> None:
        """Move the robot forward."""

    @abstractmethod
    def backward(self) -> None:
        """Move the robot backward."""

    @abstractmethod
    def left(self) -> None:
        """Turn the robot left."""

    @abstractmethod
    def right(self) -> None:
        """Turn the robot right."""

    @abstractmethod
    def stop(self) -> None:
        """Stop all motors immediately."""
