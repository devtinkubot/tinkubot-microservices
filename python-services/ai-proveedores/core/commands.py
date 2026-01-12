"""
Command Pattern Implementation for Provider Registration.

This module defines the Command interface and concrete commands for executing
reversible operations in the provider registration flow. Each command implements
execute() and undo() methods, enabling automatic rollback via the Saga Pattern.

Example:
    >>> from core.commands import RegisterProviderCommand
    >>> command = RegisterProviderCommand(repository, provider_data)
    >>> result = await command.execute()
    >>> await command.undo()  # Rollback if needed
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Command(ABC):
    """
    Abstract base class for reversible commands.

    All commands in the provider registration flow must inherit from this class
    and implement both execute() and undo() methods. This enables automatic
    rollback via the Saga Pattern when any step in the registration fails.

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


class RegisterProviderCommand(Command):
    """
    Command to register a provider in the database.

    This command handles the initial registration of a provider in the database.
    It stores the provider data and the generated provider_id for potential rollback.

    Attributes:
        provider_repository: Repository instance for database operations.
        data: Dictionary containing all provider registration data.
        provider_id: The ID generated after successful registration (None if not executed).

    Example:
        >>> from repositories.provider_repository import IProviderRepository
        >>> repo = SupabaseProviderRepository(supabase_client)
        >>> data = {
        ...     "phone": "1234567890",
        ...     "city": "Lima",
        ...     "name": "Juan Pérez",
        ...     "profession": "Plomero",
        ...     # ... other fields
        ... }
        >>> command = RegisterProviderCommand(repo, data)
        >>> result = await command.execute()
        >>> print(result["id"])
        "abc-123-def"
    """

    def __init__(
        self,
        provider_repository: 'IProviderRepository',
        data: Dict[str, Any]
    ):
        """
        Initialize the RegisterProviderCommand.

        Args:
            provider_repository: Repository instance for database operations.
                               Must implement IProviderRepository interface.
            data: Dictionary containing provider registration data.
                  Must include at minimum: phone, city, name, profession

        Example:
            >>> command = RegisterProviderCommand(repo, provider_data)
        """
        self.provider_repository = provider_repository
        self.data = data
        self.provider_id: Optional[str] = None
        logger.debug(f"RegisterProviderCommand initialized for phone: {data.get('phone')}")

    async def execute(self) -> Dict[str, Any]:
        """
        Register the provider in the database.

        This method creates a new provider record in the database using the
        repository's create() method. It stores the generated provider_id
        for potential rollback operations.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if registration succeeded
                - id (str): The generated provider ID
                - ... (other fields from repository response)

        Raises:
            Exception: If the repository create operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"Provider registered with ID: {result['id']}")
            Provider registered with ID: abc-123
        """
        logger.info(f"📝 Registering provider: {self.data.get('phone')}")

        try:
            result = await self.provider_repository.create(self.data)
            self.provider_id = result.get("id")

            logger.info(
                f"✅ Provider registered successfully: {self.provider_id} "
                f"(phone: {self.data.get('phone')})"
            )

            return result

        except Exception as e:
            logger.error(
                f"❌ Failed to register provider {self.data.get('phone')}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Delete the provider from the database (rollback operation).

        This method removes the provider record from the database if it was
        successfully created. It's called automatically by the Saga Pattern
        when a subsequent command in the registration flow fails.

        Best Effort Policy:
            - If provider_id is None, nothing to undo (log and return)
            - If delete fails, log error but don't raise (best effort)
            - Always log undo operations for debugging

        Example:
            >>> await command.undo()
            >>> # Provider record deleted from database
        """
        if self.provider_id is None:
            logger.warning(
                "⚠️ RegisterProviderCommand undo called but no provider_id "
                "(command was not executed)"
            )
            return

        logger.info(f"↩️ Rolling back provider registration: {self.provider_id}")

        try:
            await self.provider_repository.delete(self.provider_id)
            logger.info(
                f"✅ Provider registration undone: {self.provider_id} "
                f"(deleted from database)"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to undo provider registration {self.provider_id}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback


# TODO: Implement image upload commands for future phases
#
# The following commands will be implemented when integrating with the
# image upload service:
#
# class UploadDniFrontCommand(Command):
#     """Upload DNI front photo to storage."""
#
#     def __init__(self, image_service, provider_id: str, image_base64: str):
#         self.image_service = image_service
#         self.provider_id = provider_id
#         self.image_base64 = image_base64
#         self.image_url: Optional[str] = None
#
#     async def execute(self) -> Dict[str, Any]:
#         """Upload the image to Supabase Storage."""
#         self.image_url = await self.image_service.upload_dni_front(
#             self.provider_id, self.image_base64
#         )
#         return {"dni_front_url": self.image_url}
#
#     async def undo(self) -> None:
#         """Delete the image from storage."""
#         if self.image_url:
#             await self.image_service.delete_image(self.image_url)
#
#
# class UploadDniBackCommand(Command):
#     """Upload DNI back photo to storage."""
#     # Similar implementation to UploadDniFrontCommand
#
#
# class UploadFacePhotoCommand(Command):
#     """Upload face/selfie photo to storage."""
#     # Similar implementation to UploadDniFrontCommand
#
#
# class UpdateSocialMediaCommand(Command):
#     """Update provider's social media information."""
#
#     def __init__(self, provider_repository, provider_id: str,
#                  social_media_url: Optional[str], social_media_type: Optional[str]):
#         self.provider_repository = provider_repository
#         self.provider_id = provider_id
#         self.social_media_url = social_media_url
#         self.social_media_type = social_media_type
#         self.old_url: Optional[str] = None
#         self.old_type: Optional[str] = None
#
#     async def execute(self) -> Dict[str, Any]:
#         """Update social media in database."""
#         provider = await self.provider_repository.find_by_id(self.provider_id)
#         self.old_url = provider.get("social_media_url")
#         self.old_type = provider.get("social_media_type")
#
#         updated = await self.provider_repository.update(
#             self.provider_id,
#             {
#                 "social_media_url": self.social_media_url,
#                 "social_media_type": self.social_media_type
#             }
#         )
#         return updated
#
#     async def undo(self) -> None:
#         """Restore previous social media information."""
#         await self.provider_repository.update(
#             self.provider_id,
#             {
#                 "social_media_url": self.old_url,
#                 "social_media_type": self.old_type
#             }
#         )
