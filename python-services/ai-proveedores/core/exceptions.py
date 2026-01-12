"""Excepciones personalizadas del dominio."""


class RepositoryError(Exception):
    """Error en operaciones del repositorio."""
    pass


class InvalidTransitionError(Exception):
    """Error en transición de estado inválida."""

    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid transition from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class StateHandlerNotFoundError(Exception):
    """Error cuando no hay handler para un estado."""

    def __init__(self, state):
        super().__init__(f"No handler found for state: {state}")
        self.state = state


class SagaExecutionError(Exception):
    """
    Exception raised when saga execution fails.

    This exception contains information about which commands were successfully
    executed before the failure, enabling diagnostic and recovery operations.

    Attributes:
        message: Human-readable error message.
        completed_commands: List of command class names that completed successfully.
        failed_at: Index of the command that failed (0-based).

    Example:
        >>> try:
        ...     await saga.execute()
        ... except SagaExecutionError as e:
        ...     print(f"Failed after {len(e.completed_commands)} commands")
        ...     print(f"Completed: {', '.join(e.completed_commands)}")
    """

    def __init__(
        self,
        message: str,
        completed_commands: list,
        failed_at: int = None
    ):
        """
        Initialize the SagaExecutionError.

        Args:
            message: Human-readable error message describing what went wrong.
            completed_commands: List of command class names that completed
                               successfully before the failure.
            failed_at: Optional index of the command that failed (0-based).
        """
        super().__init__(message)
        self.completed_commands = completed_commands
        self.failed_at = failed_at if failed_at is not None else len(completed_commands)
        self.message = message  # Store message for easy access

    def __str__(self) -> str:
        """Return a formatted error message."""
        completed = ", ".join(self.completed_commands) if self.completed_commands else "none"
        return (
            f"Saga failed: {super().__str__()}\n"
            f"  Completed commands: {completed}\n"
            f"  Failed at step: {self.failed_at + 1}"
        )
