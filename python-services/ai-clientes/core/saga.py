"""
Saga Pattern Implementation for Client Conversation Flow.

This module implements the Saga Pattern for orchestrating multi-step operations
with automatic rollback capabilities. The saga executes a sequence of commands
and ensures that if any step fails, all previously executed steps are rolled back
in reverse order using their undo() methods.

The Saga Pattern provides:
- Automatic rollback on failure
- Detailed logging of each step
- Best-effort compensation (continues even if undo fails)
- Fluent interface for building complex operations

Example:
    >>> from core.saga import ClientSaga
    >>> from core.commands import UpdateCustomerCityCommand, SaveSearchResultsCommand
    >>>
    >>> saga = ClientSaga()
    >>> saga.add_command(UpdateCustomerCityCommand(customer_service, customer_id, "Lima"))
    >>> saga.add_command(SaveSearchResultsCommand(session_manager, phone, results))
    >>> result = await saga.execute()
    >>> # If any command fails, all previous ones are automatically undone
"""

import logging
from typing import List, Dict, Any
from core.commands import Command
from core.exceptions import RepositoryError

logger = logging.getLogger(__name__)


class SagaExecutionError(RepositoryError):
    """
    Exception raised when a saga execution fails.

    This exception contains information about which commands completed
    before the failure, making it easier to diagnose and debug issues.

    Attributes:
        message: Error message describing the failure.
        completed_commands: List of command names that completed successfully.
        failed_at: Index of the command that failed (0-based).
    """

    def __init__(
        self,
        message: str,
        completed_commands: List[str] = None,
        failed_at: int = None
    ):
        """
        Initialize the SagaExecutionError.

        Args:
            message: Error message describing the failure.
            completed_commands: List of command names that completed before failure.
            failed_at: Index of the command that failed.
        """
        super().__init__(message)
        self.completed_commands = completed_commands or []
        self.failed_at = failed_at


class ClientSaga:
    """
    Orchestrates client conversation operations with automatic rollback.

    This saga executes a sequence of commands to handle conversation flow,
    ensuring that if any step fails, all previously executed steps are
    rolled back in reverse order. This provides transactional semantics
    across multiple operations (database, Redis, external services, etc.).

    The saga uses a fluent interface for building command chains and provides
    detailed logging for debugging and monitoring.

    Attributes:
        commands: List of commands to execute (in order).
        executed_commands: List of commands that were successfully executed.

    Example:
        >>> from core.saga import ClientSaga
        >>> from core.commands import UpdateCustomerCityCommand
        >>>
        >>> # Build saga with fluent interface
        >>> saga = (ClientSaga()
        ...     .add_command(UpdateCustomerCityCommand(service, customer_id, "Lima"))
        ...     .add_command(SaveSearchResultsCommand(session_manager, phone, results)))
        >>>
        >>> # Execute with automatic rollback on failure
        >>> try:
        ...     result = await saga.execute()
        ...     print("Operation successful!")
        ... except SagaExecutionError as e:
        ...     print(f"Operation failed: {e}")
        ...     # Rollback already executed automatically
    """

    def __init__(self):
        """
        Initialize the ClientSaga.

        Creates empty lists for commands and executed commands. The saga is
        built incrementally using the add_command() method.

        Example:
            >>> saga = ClientSaga()
            >>> saga.add_command(UpdateCustomerCityCommand(service, customer_id, "Lima"))
        """
        self.commands: List[Command] = []
        self.executed_commands: List[Command] = []

        logger.debug("ClientSaga initialized")

    def add_command(self, command: Command) -> 'ClientSaga':
        """
        Add a command to the saga (fluent interface).

        This method adds a command to the execution queue and returns self,
        enabling method chaining for building complex sagas.

        Args:
            command: Command instance to execute. Must inherit from Command
                    and implement execute() and undo() methods.

        Returns:
            self: Returns the saga instance for method chaining (fluent interface).

        Example:
            >>> saga = (ClientSaga()
            ...     .add_command(UpdateCustomerCityCommand(service, customer_id, "Lima"))
            ...     .add_command(SaveSearchResultsCommand(session_manager, phone, results)))
        """
        self.commands.append(command)
        logger.debug(
            f"📋 Command added to saga: {command.__class__.__name__} "
            f"(total: {len(self.commands)})"
        )
        return self

    async def execute(self) -> Dict[str, Any]:
        """
        Execute all commands in order with automatic rollback.

        This method executes each command in the order they were added. If any
        command fails, it automatically rolls back all previously executed
        commands in reverse order using their undo() methods.

        Execution Flow:
            1. Clear executed_commands list
            2. For each command in commands:
               a. Execute command.execute()
               b. Append to executed_commands
               c. Log success
            3. If all succeed, return success result
            4. If any fails, execute _rollback() and raise SagaExecutionError

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if all commands executed successfully
                - message (str): Success message
                - commands_executed (int): Number of commands executed

        Raises:
            SagaExecutionError: If any command fails. The exception contains
                               information about which commands completed
                               before the failure.

        Example:
            >>> try:
            ...     result = await saga.execute()
            ...     print(f"Success! Executed {result['commands_executed']} commands")
            ... except SagaExecutionError as e:
            ...     print(f"Failed: {e}")
            ...     print(f"Completed before failure: {e.completed_commands}")
        """
        self.executed_commands = []

        logger.info(
            f"🚀 Starting saga execution with {len(self.commands)} commands"
        )

        try:
            for index, command in enumerate(self.commands, start=1):
                logger.info(
                    f"⚙️ Executing command {index}/{len(self.commands)}: "
                    f"{command.__class__.__name__}"
                )

                await command.execute()
                self.executed_commands.append(command)

                logger.info(
                    f"✅ Command {index}/{len(self.commands)} completed: "
                    f"{command.__class__.__name__}"
                )

            logger.info(
                f"🎉 Saga completed successfully! "
                f"({len(self.executed_commands)} commands executed)"
            )

            return {
                "success": True,
                "message": "Saga completed",
                "commands_executed": len(self.executed_commands)
            }

        except Exception as e:
            # Capture the command that failed
            failed_index = len(self.executed_commands)
            failed_command = (
                self.commands[failed_index].__class__.__name__
                if failed_index < len(self.commands)
                else "unknown"
            )

            logger.error(
                f"❌ Saga failed at command {failed_index + 1}/{len(self.commands)}: "
                f"{failed_command} - {str(e)}"
            )

            # Automatic rollback
            await self._rollback()

            # Raise detailed exception
            raise SagaExecutionError(
                f"Saga failed at step {failed_index + 1}: {str(e)}",
                completed_commands=[c.__class__.__name__ for c in self.executed_commands],
                failed_at=failed_index
            )

    async def _rollback(self) -> None:
        """
        Execute undo() for all executed commands in reverse order.

        This private method is called automatically when a command fails.
        It iterates through executed_commands in reverse order and calls
        each command's undo() method to compensate for the changes.

        Best Effort Policy:
            - Logs each undo operation
            - Continues even if individual undo fails
            - Logs errors but doesn't raise exceptions
            - Provides detailed diagnostic information

        The rollback is executed in reverse order (LIFO - Last In, First Out)
        to ensure dependencies are handled correctly. For example, if we
        updated a city and saved results, then results save failed, we undo
        the city update first.

        Example:
            >>> # Automatic rollback - don't call this directly
            >>> await saga._rollback()
            >>> # All executed commands are undone in reverse order
        """
        if not self.executed_commands:
            logger.warning("⚠️ No commands to rollback")
            return

        logger.info(
            f"🔄 Rolling back {len(self.executed_commands)} executed commands "
            f"(in reverse order)..."
        )

        # Iterate in reverse order
        for index, command in enumerate(reversed(self.executed_commands), start=1):
            original_index = len(self.executed_commands) - index
            command_name = command.__class__.__name__

            try:
                logger.info(
                    f"↩️ Rolling back command {original_index + 1}: {command_name}"
                )

                await command.undo()

                logger.info(
                    f"✅ Rollback successful for command {original_index + 1}: "
                    f"{command_name}"
                )

            except Exception as undo_error:
                logger.error(
                    f"⚠️ Rollback FAILED for command {original_index + 1}: "
                    f"{command_name} - {str(undo_error)}"
                )
                logger.error(
                    f"⚠️ Manual cleanup may be required for {command_name}"
                )
                # Continue with next undo (best effort)

        logger.info("🏁 Rollback process completed")

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the saga.

        Returns diagnostic information about the saga state, useful for
        debugging and monitoring.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - total_commands (int): Total number of commands in the saga
                - executed_commands (int): Number of commands successfully executed
                - pending_commands (int): Number of commands yet to be executed
                - command_names (List[str]): Names of all commands in order
                - executed_names (List[str]): Names of executed commands

        Example:
            >>> status = saga.get_status()
            >>> print(f"Total: {status['total_commands']}, "
            ...       f"Executed: {status['executed_commands']}")
        """
        return {
            "total_commands": len(self.commands),
            "executed_commands": len(self.executed_commands),
            "pending_commands": len(self.commands) - len(self.executed_commands),
            "command_names": [c.__class__.__name__ for c in self.commands],
            "executed_names": [c.__class__.__name__ for c in self.executed_commands]
        }

    def reset(self) -> None:
        """
        Reset the saga to its initial state.

        Clears both the commands list and executed_commands list, allowing
        the saga instance to be reused for a new operation.

        Warning:
            This does NOT rollback executed commands. Only use this method
            if you haven't executed the saga yet, or if you've already
            handled rollback manually.

        Example:
            >>> saga.reset()
            >>> saga.add_command(UpdateCustomerCityCommand(service, customer_id, "Lima"))
            >>> # Ready for a new execution
        """
        self.commands.clear()
        self.executed_commands.clear()
        logger.debug("Saga reset to initial state")
