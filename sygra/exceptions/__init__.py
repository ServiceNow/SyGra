"""SyGra Library Exceptions"""


class GraSPError(Exception):
    """Base exception for SyGra library."""

    pass


class ValidationError(GraSPError):
    """Validation error."""

    pass


class ExecutionError(GraSPError):
    """Execution error."""

    pass


class ConfigurationError(GraSPError):
    """Configuration error."""

    pass


class NodeError(GraSPError):
    """Node processing error."""

    pass


class DataError(GraSPError):
    """Data handling error."""

    pass


class ModelError(GraSPError):
    """Model error."""

    pass


class ModelServerDownError(ModelError):
    """A model kept returning server-down status codes (404/5xx) within a short window.

    Raised instead of exiting the process when the server-down action is ``"raise"``
    (the default for library runs through :class:`sygra.Workflow`).

    Attributes:
        model_name: Name of the model that is down.
        failures: Number of server-down responses counted.
        window_seconds: Time span, in seconds, over which they were received.
    """

    def __init__(self, model_name: str, failures: int, window_seconds: float) -> None:
        self.model_name = model_name
        self.failures = failures
        self.window_seconds = window_seconds
        super().__init__(
            f"Model '{model_name}' appears to be down: {failures} server-down responses "
            f"in {window_seconds:.2f} seconds."
        )


class TimeoutError(GraSPError):
    """Timeout error."""

    pass


__all__ = [
    "GraSPError",
    "ValidationError",
    "ExecutionError",
    "ConfigurationError",
    "NodeError",
    "DataError",
    "ModelError",
    "ModelServerDownError",
    "TimeoutError",
]
