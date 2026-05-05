class RobotAppError(Exception):
    """Base exception for robot streaming app."""


class ValidationError(RobotAppError):
    """Raised when user-provided values are invalid."""


class ConfigError(RobotAppError):
    """Raised when configuration loading/saving fails."""


class ProcessError(RobotAppError):
    """Raised when subprocess lifecycle operations fail."""
