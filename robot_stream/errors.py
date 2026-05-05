class RobotStreamError(Exception):
    """Base exception for robot stream domain errors."""


class ValidationError(RobotStreamError):
    """Raised when user input or configuration values are invalid."""
