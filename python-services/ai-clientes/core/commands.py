"""
Command Pattern Implementation for Client Conversation Flow.

This module defines the Command interface and concrete commands for executing
reversible operations in the client conversation flow. Each command implements
execute() and undo() methods, enabling automatic rollback via the Saga Pattern.

Example:
    >>> from core.commands import UpdateCustomerCityCommand
    >>> command = UpdateCustomerCityCommand(customer_service, customer_id, "Lima")
    >>> result = await command.execute()
    >>> await command.undo()  # Rollback if needed
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from services.customer.customer_service import CustomerService

logger = logging.getLogger(__name__)


class Command(ABC):
    """
    Abstract base class for reversible commands.

    All commands in the client conversation flow must inherit from this class
    and implement both execute() and undo() methods. This enables automatic
    rollback via the Saga Pattern when any step in the conversation fails.

    Attributes:
        None (base class)

    Methods:
        execute(): Execute the command's primary action.
        undo(): Rollback the command's action (compensating transaction).

    Example:
        >>> class MyCommand(Command):
        ...     async def execute(self) -> Dict[str, Any]:
        ...         # Do something
        ...         return {"success": True}
        ...
        ...     async def undo(self) -> None:
        ...         # Undo it
        ...         pass
    """

    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        Execute the command's primary action.

        This method should perform the main operation of the command and
        return a dictionary with the results. If the operation fails,
        it should raise an exception.

        Returns:
            Dict[str, Any]: A dictionary containing the results of the execution.
                           Must include at least a "success" boolean key.

        Raises:
            Exception: Any exception that occurs during execution.

        Example:
            >>> result = await command.execute()
            >>> print(result["success"])
            True
        """
        pass

    @abstractmethod
    async def undo(self) -> None:
        """
        Rollback the command's action (compensating transaction).

        This method should undo whatever execute() did. It's called automatically
        by the Saga Pattern when a subsequent command fails. The implementation
        should be idempotent and handle edge cases gracefully.

        Best Practices:
            - Always check if the command was executed before undoing
            - Log all undo operations for debugging
            - Handle exceptions gracefully (best effort)
            - Clean up any resources created during execute()

        Example:
            >>> await command.undo()
            >>> # Command's effects are rolled back
        """
        pass


class UpdateCustomerCityCommand(Command):
    """
    Command to update customer's city in the database.

    This command handles updating the city field for a customer. It stores
    the previous city value for potential rollback operations.

    Attributes:
        customer_service: Service instance for customer operations.
        customer_id: The ID of the customer to update.
        new_city: The new city value to set.
        previous_city: The previous city value before update (None if not executed).

    Example:
        >>> command = UpdateCustomerCityCommand(
        ...     customer_service,
        ...     "customer-123",
        ...     "Lima"
        ... )
        >>> result = await command.execute()
        >>> print(result["city"])
        "Lima"
    """

    def __init__(
        self,
        customer_service: 'CustomerService',
        customer_id: str,
        new_city: str
    ):
        """
        Initialize the UpdateCustomerCityCommand.

        Args:
            customer_service: Service instance for customer operations.
            customer_id: The ID of the customer to update.
            new_city: The new city value to set.

        Example:
            >>> command = UpdateCustomerCityCommand(service, "cust-123", "Lima")
        """
        self.customer_service = customer_service
        self.customer_id = customer_id
        self.new_city = new_city
        self.previous_city: Optional[str] = None
        logger.debug(
            f"UpdateCustomerCityCommand initialized for customer: {customer_id}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Update the customer's city in the database.

        This method updates the city field for a customer using the
        customer service's update_customer_city() method. It stores
        the previous city value for potential rollback operations.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if update succeeded
                - city (str): The updated city value
                - previous_city (str): The city value before update

        Raises:
            Exception: If the update operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"City updated to: {result['city']}")
            City updated to: Lima
        """
        logger.info(
            f"📍 Updating city for customer {self.customer_id}: "
            f"'{self.new_city}'"
        )

        try:
            # Get current customer to preserve previous city
            customer = await self.customer_service.find_customer_by_id(
                self.customer_id
            )
            self.previous_city = customer.get("city") if customer else None

            # Update city
            result = await self.customer_service.update_customer_city(
                self.customer_id,
                self.new_city
            )

            logger.info(
                f"✅ City updated successfully for customer {self.customer_id}: "
                f"'{self.previous_city}' → '{self.new_city}'"
            )

            return {
                "success": True,
                "city": self.new_city,
                "previous_city": self.previous_city
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to update city for customer {self.customer_id}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Revert the customer's city to previous value (rollback operation).

        This method restores the previous city value if the update was
        successfully executed. It's called automatically by the Saga Pattern
        when a subsequent command in the conversation flow fails.

        Best Effort Policy:
            - If previous_city is None, sets city to None (clears it)
            - If update fails, log error but don't raise (best effort)
            - Always log undo operations for debugging

        Example:
            >>> await command.undo()
            >>> # City reverted to previous value
        """
        if self.previous_city is None and self.new_city:
            logger.warning(
                f"⚠️ UpdateCustomerCityCommand undo called for {self.customer_id} "
                f"but no previous_city stored (will clear city)"
            )

        logger.info(
            f"↩️ Rolling back city update for customer {self.customer_id}: "
            f"'{self.new_city}' → '{self.previous_city}'"
        )

        try:
            # Revert to previous city (or clear if was None)
            if self.previous_city:
                await self.customer_service.update_customer_city(
                    self.customer_id,
                    self.previous_city
                )
                logger.info(
                    f"✅ City reverted for customer {self.customer_id}: "
                    f"'{self.new_city}' → '{self.previous_city}'"
                )
            else:
                # Clear city if it was None before
                await self.customer_service.clear_customer_city(self.customer_id)
                logger.info(
                    f"✅ City cleared for customer {self.customer_id} "
                    f"(reverted from '{self.new_city}')"
                )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to undo city update for customer {self.customer_id}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback


class SaveSearchResultsCommand(Command):
    """
    Command to save search results in Redis session.

    This command handles saving provider search results to the customer's
    session in Redis. It stores the session key for potential rollback.

    Attributes:
        session_manager: Session manager instance for Redis operations.
        phone: Customer's phone number (used as session key).
        results: Dictionary containing search results to save.
        was_saved: Boolean flag indicating if results were saved.

    Example:
        >>> command = SaveSearchResultsCommand(
        ...     session_manager,
        ...     "1234567890",
        ...     {"providers": [...], "service": "plomero"}
        ... )
        >>> result = await command.execute()
        >>> print(result["saved"])
        True
    """

    def __init__(
        self,
        session_manager,
        phone: str,
        results: Dict[str, Any]
    ):
        """
        Initialize the SaveSearchResultsCommand.

        Args:
            session_manager: Session manager instance for Redis operations.
            phone: Customer's phone number (used as session key).
            results: Dictionary containing search results to save.

        Example:
            >>> command = SaveSearchResultsCommand(
            ...     session_manager, "1234567890", results_dict
            ... )
        """
        self.session_manager = session_manager
        self.phone = phone
        self.results = results
        self.was_saved = False
        logger.debug(
            f"SaveSearchResultsCommand initialized for phone: {phone}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Save search results to Redis session.

        This method saves the search results to the customer's session
        using the session manager's redis_client.set() method.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if save succeeded
                - saved (bool): True if results were saved to Redis

        Raises:
            Exception: If the save operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"Results saved: {result['saved']}")
            Results saved: True
        """
        logger.info(f"💾 Saving search results for phone: {self.phone}")

        try:
            flow_key = f"flow:{self.phone}"
            ttl = 3600  # 1 hour default

            await self.session_manager.redis_client.set(
                flow_key,
                self.results,
                expire=ttl
            )

            self.was_saved = True

            logger.info(
                f"✅ Search results saved for phone: {self.phone} "
                f"(key: {flow_key}, ttl: {ttl}s)"
            )

            return {
                "success": True,
                "saved": True,
                "key": flow_key
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to save search results for phone {self.phone}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Clear search results from Redis session (rollback operation).

        This method removes the search results from the customer's session
        if they were successfully saved. It's called automatically by the
        Saga Pattern when a subsequent command fails.

        Best Effort Policy:
            - If was_saved is False, nothing to undo (log and return)
            - If delete fails, log error but don't raise (best effort)
            - Always log undo operations for debugging

        Example:
            >>> await command.undo()
            >>> # Search results removed from Redis
        """
        if not self.was_saved:
            logger.warning(
                f"⚠️ SaveSearchResultsCommand undo called for {self.phone} "
                f"but results were not saved"
            )
            return

        logger.info(
            f"↩️ Rolling back search results for phone: {self.phone}"
        )

        try:
            flow_key = f"flow:{self.phone}"

            # Clear the flow key
            await self.session_manager.redis_client.delete(flow_key)

            logger.info(
                f"✅ Search results cleared for phone: {self.phone} "
                f"(key: {flow_key} deleted)"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to undo search results save for phone {self.phone}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback
