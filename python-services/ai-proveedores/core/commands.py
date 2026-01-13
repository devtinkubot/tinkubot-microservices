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
from typing import Dict, Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from repositories.interfaces import IProviderRepository
    from services.image_service import ImageService

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


# Image Upload Commands (Phase 3)


class UploadDniFrontCommand(Command):
    """
    Command to upload DNI front photo to Supabase Storage.

    This command handles uploading the front side of a DNI document to
    Supabase Storage. It stores the generated URL for potential rollback.

    Attributes:
        image_service: ImageService instance for storage operations.
        provider_id: The ID of the provider.
        image_base64: Base64-encoded image data.
        image_url: The URL generated after successful upload (None if not executed).
        old_url: The previous DNI front URL (for restore on rollback).

    Example:
        >>> command = UploadDniFrontCommand(image_service, provider_id, base64_data)
        >>> result = await command.execute()
        >>> print(result["dni_front_url"])
        "https://supabase.storage.com/..."
        >>> await command.undo()  # Deletes the uploaded image
    """

    def __init__(
        self,
        image_service: 'ImageService',
        provider_id: str,
        image_base64: str
    ):
        """
        Initialize the UploadDniFrontCommand.

        Args:
            image_service: ImageService instance for storage operations.
            provider_id: The ID of the provider (UUID).
            image_base64: Base64-encoded image data.

        Example:
            >>> command = UploadDniFrontCommand(img_svc, "abc-123", "data:image/jpeg;base64,...")
        """
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None
        self.old_url: Optional[str] = None
        logger.debug(
            f"UploadDniFrontCommand initialized for provider: {provider_id}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Upload DNI front photo to Supabase Storage.

        This method uploads the base64-encoded image to Supabase Storage
        and updates the provider record with the new URL. It stores both
        the new URL and the old URL for potential rollback.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if upload succeeded
                - dni_front_url (str): The generated image URL

        Raises:
            Exception: If the upload operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"DNI front uploaded: {result['dni_front_url']}")
        """
        logger.info(f"📤 Uploading DNI front for provider: {self.provider_id}")

        try:
            # Get old URL for rollback
            self.old_url = await self.image_service.get_dni_front_url(
                self.provider_id
            )

            # Upload new image
            self.image_url = await self.image_service.upload_dni_front(
                self.provider_id,
                self.image_base64
            )

            if not self.image_url:
                raise ValueError("Failed to upload DNI front - no URL returned")

            logger.info(
                f"✅ DNI front uploaded successfully for {self.provider_id}: "
                f"{self.image_url}"
            )

            return {
                "success": True,
                "dni_front_url": self.image_url
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to upload DNI front for {self.provider_id}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Delete the uploaded DNI front image (rollback operation).

        This method removes the uploaded image from Supabase Storage and
        restores the previous URL in the provider record. It's called
        automatically by the Saga Pattern when a subsequent command fails.

        Best Effort Policy:
            - If image_url is None, nothing to undo (log and return)
            - If delete fails, log error but don't raise (best effort)
            - Always restore old_url if it exists

        Example:
            >>> await command.undo()
            >>> # Uploaded image deleted, old URL restored
        """
        if self.image_url is None:
            logger.warning(
                "⚠️ UploadDniFrontCommand undo called but no image_url "
                "(command was not executed)"
            )
            return

        logger.info(
            f"↩️ Rolling back DNI front upload for provider: {self.provider_id}"
        )

        try:
            # Delete the uploaded image
            await self.image_service.delete_image(self.image_url)
            logger.info(
                f"✅ DNI front image deleted from storage: {self.image_url}"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to delete DNI front image {self.image_url}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback

        try:
            # Restore old URL
            if self.old_url:
                await self.image_service.update_dni_front_url(
                    self.provider_id,
                    self.old_url
                )
                logger.info(
                    f"✅ Previous DNI front URL restored for {self.provider_id}"
                )
            else:
                # Clear the URL field if there was no old URL
                await self.image_service.update_dni_front_url(
                    self.provider_id,
                    None
                )
                logger.info(
                    f"✅ DNI front URL cleared for {self.provider_id}"
                )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to restore DNI front URL for {self.provider_id}: {e}"
            )
            # Don't raise - best effort rollback


class UploadDniBackCommand(Command):
    """
    Command to upload DNI back photo to Supabase Storage.

    This command handles uploading the back side of a DNI document to
    Supabase Storage. It stores the generated URL for potential rollback.

    Attributes:
        image_service: ImageService instance for storage operations.
        provider_id: The ID of the provider.
        image_base64: Base64-encoded image data.
        image_url: The URL generated after successful upload (None if not executed).
        old_url: The previous DNI back URL (for restore on rollback).

    Example:
        >>> command = UploadDniBackCommand(image_service, provider_id, base64_data)
        >>> result = await command.execute()
        >>> print(result["dni_back_url"])
        "https://supabase.storage.com/..."
        >>> await command.undo()  # Deletes the uploaded image
    """

    def __init__(
        self,
        image_service: 'ImageService',
        provider_id: str,
        image_base64: str
    ):
        """
        Initialize the UploadDniBackCommand.

        Args:
            image_service: ImageService instance for storage operations.
            provider_id: The ID of the provider (UUID).
            image_base64: Base64-encoded image data.

        Example:
            >>> command = UploadDniBackCommand(img_svc, "abc-123", "data:image/jpeg;base64,...")
        """
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None
        self.old_url: Optional[str] = None
        logger.debug(
            f"UploadDniBackCommand initialized for provider: {provider_id}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Upload DNI back photo to Supabase Storage.

        This method uploads the base64-encoded image to Supabase Storage
        and updates the provider record with the new URL. It stores both
        the new URL and the old URL for potential rollback.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if upload succeeded
                - dni_back_url (str): The generated image URL

        Raises:
            Exception: If the upload operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"DNI back uploaded: {result['dni_back_url']}")
        """
        logger.info(f"📤 Uploading DNI back for provider: {self.provider_id}")

        try:
            # Get old URL for rollback
            self.old_url = await self.image_service.get_dni_back_url(
                self.provider_id
            )

            # Upload new image
            self.image_url = await self.image_service.upload_dni_back(
                self.provider_id,
                self.image_base64
            )

            if not self.image_url:
                raise ValueError("Failed to upload DNI back - no URL returned")

            logger.info(
                f"✅ DNI back uploaded successfully for {self.provider_id}: "
                f"{self.image_url}"
            )

            return {
                "success": True,
                "dni_back_url": self.image_url
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to upload DNI back for {self.provider_id}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Delete the uploaded DNI back image (rollback operation).

        This method removes the uploaded image from Supabase Storage and
        restores the previous URL in the provider record. It's called
        automatically by the Saga Pattern when a subsequent command fails.

        Best Effort Policy:
            - If image_url is None, nothing to undo (log and return)
            - If delete fails, log error but don't raise (best effort)
            - Always restore old_url if it exists

        Example:
            >>> await command.undo()
            >>> # Uploaded image deleted, old URL restored
        """
        if self.image_url is None:
            logger.warning(
                "⚠️ UploadDniBackCommand undo called but no image_url "
                "(command was not executed)"
            )
            return

        logger.info(
            f"↩️ Rolling back DNI back upload for provider: {self.provider_id}"
        )

        try:
            # Delete the uploaded image
            await self.image_service.delete_image(self.image_url)
            logger.info(
                f"✅ DNI back image deleted from storage: {self.image_url}"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to delete DNI back image {self.image_url}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback

        try:
            # Restore old URL
            if self.old_url:
                await self.image_service.update_dni_back_url(
                    self.provider_id,
                    self.old_url
                )
                logger.info(
                    f"✅ Previous DNI back URL restored for {self.provider_id}"
                )
            else:
                # Clear the URL field if there was no old URL
                await self.image_service.update_dni_back_url(
                    self.provider_id,
                    None
                )
                logger.info(
                    f"✅ DNI back URL cleared for {self.provider_id}"
                )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to restore DNI back URL for {self.provider_id}: {e}"
            )
            # Don't raise - best effort rollback


class UploadFacePhotoCommand(Command):
    """
    Command to upload face/selfie photo to Supabase Storage.

    This command handles uploading a face photo for identity verification
    to Supabase Storage. It stores the generated URL for potential rollback.

    Attributes:
        image_service: ImageService instance for storage operations.
        provider_id: The ID of the provider.
        image_base64: Base64-encoded image data.
        image_url: The URL generated after successful upload (None if not executed).
        old_url: The previous face photo URL (for restore on rollback).

    Example:
        >>> command = UploadFacePhotoCommand(image_service, provider_id, base64_data)
        >>> result = await command.execute()
        >>> print(result["face_url"])
        "https://supabase.storage.com/..."
        >>> await command.undo()  # Deletes the uploaded image
    """

    def __init__(
        self,
        image_service: 'ImageService',
        provider_id: str,
        image_base64: str
    ):
        """
        Initialize the UploadFacePhotoCommand.

        Args:
            image_service: ImageService instance for storage operations.
            provider_id: The ID of the provider (UUID).
            image_base64: Base64-encoded image data.

        Example:
            >>> command = UploadFacePhotoCommand(img_svc, "abc-123", "data:image/jpeg;base64,...")
        """
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None
        self.old_url: Optional[str] = None
        logger.debug(
            f"UploadFacePhotoCommand initialized for provider: {provider_id}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Upload face photo to Supabase Storage.

        This method uploads the base64-encoded image to Supabase Storage
        and updates the provider record with the new URL. It stores both
        the new URL and the old URL for potential rollback.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if upload succeeded
                - face_url (str): The generated image URL

        Raises:
            Exception: If the upload operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"Face photo uploaded: {result['face_url']}")
        """
        logger.info(f"📤 Uploading face photo for provider: {self.provider_id}")

        try:
            # Get old URL for rollback
            self.old_url = await self.image_service.get_face_photo_url(
                self.provider_id
            )

            # Upload new image
            self.image_url = await self.image_service.upload_face_photo(
                self.provider_id,
                self.image_base64
            )

            if not self.image_url:
                raise ValueError("Failed to upload face photo - no URL returned")

            logger.info(
                f"✅ Face photo uploaded successfully for {self.provider_id}: "
                f"{self.image_url}"
            )

            return {
                "success": True,
                "face_url": self.image_url
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to upload face photo for {self.provider_id}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Delete the uploaded face photo (rollback operation).

        This method removes the uploaded image from Supabase Storage and
        restores the previous URL in the provider record. It's called
        automatically by the Saga Pattern when a subsequent command fails.

        Best Effort Policy:
            - If image_url is None, nothing to undo (log and return)
            - If delete fails, log error but don't raise (best effort)
            - Always restore old_url if it exists

        Example:
            >>> await command.undo()
            >>> # Uploaded image deleted, old URL restored
        """
        if self.image_url is None:
            logger.warning(
                "⚠️ UploadFacePhotoCommand undo called but no image_url "
                "(command was not executed)"
            )
            return

        logger.info(
            f"↩️ Rolling back face photo upload for provider: {self.provider_id}"
        )

        try:
            # Delete the uploaded image
            await self.image_service.delete_image(self.image_url)
            logger.info(
                f"✅ Face photo deleted from storage: {self.image_url}"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to delete face photo {self.image_url}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback

        try:
            # Restore old URL
            if self.old_url:
                await self.image_service.update_face_photo_url(
                    self.provider_id,
                    self.old_url
                )
                logger.info(
                    f"✅ Previous face photo URL restored for {self.provider_id}"
                )
            else:
                # Clear the URL field if there was no old URL
                await self.image_service.update_face_photo_url(
                    self.provider_id,
                    None
                )
                logger.info(
                    f"✅ Face photo URL cleared for {self.provider_id}"
                )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to restore face photo URL for {self.provider_id}: {e}"
            )
            # Don't raise - best effort rollback


class UpdateProviderSocialMediaCommand(Command):
    """
    Command to update provider's social media information.

    This command handles updating the social media URL and type for a provider.
    It stores the previous values for potential rollback.

    Attributes:
        provider_repository: Repository instance for database operations.
        provider_id: The ID of the provider.
        social_url: New social media URL.
        social_type: New social media type.
        old_url: Previous social media URL (for rollback).
        old_type: Previous social media type (for rollback).

    Example:
        >>> command = UpdateProviderSocialMediaCommand(
        ...     repository, provider_id, "https://instagram.com/user", "instagram"
        ... )
        >>> result = await command.execute()
        >>> print(result["social_media_url"])
        "https://instagram.com/user"
        >>> await command.undo()  # Restores old values
    """

    def __init__(
        self,
        provider_repository: 'IProviderRepository',
        provider_id: str,
        social_url: Optional[str],
        social_type: Optional[str]
    ):
        """
        Initialize the UpdateProviderSocialMediaCommand.

        Args:
            provider_repository: Repository instance for database operations.
            provider_id: The ID of the provider (UUID).
            social_url: New social media URL.
            social_type: New social media type.

        Example:
            >>> command = UpdateProviderSocialMediaCommand(
            ...     repo, "abc-123", "https://facebook.com/user", "facebook"
            ... )
        """
        self.provider_repository = provider_repository
        self.provider_id = provider_id
        self.social_url = social_url
        self.social_type = social_type
        self.old_url: Optional[str] = None
        self.old_type: Optional[str] = None
        logger.debug(
            f"UpdateProviderSocialMediaCommand initialized for provider: {provider_id}"
        )

    async def execute(self) -> Dict[str, Any]:
        """
        Update provider's social media information.

        This method retrieves the current social media values, stores them
        for rollback, and updates the provider record with the new values.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - success (bool): True if update succeeded
                - social_media_url (str): The new social media URL
                - social_media_type (str): The new social media type

        Raises:
            Exception: If the update operation fails.

        Example:
            >>> result = await command.execute()
            >>> print(f"Social media updated: {result['social_media_url']}")
        """
        logger.info(
            f"📝 Updating social media for provider: {self.provider_id} "
            f"(type: {self.social_type})"
        )

        try:
            # Get current values for rollback
            provider = await self.provider_repository.find_by_id(
                self.provider_id
            )

            if not provider:
                raise ValueError(f"Provider {self.provider_id} not found")

            self.old_url = provider.get("social_media_url")
            self.old_type = provider.get("social_media_type")

            # Update with new values
            updated = await self.provider_repository.update(
                self.provider_id,
                {
                    "social_media_url": self.social_url,
                    "social_media_type": self.social_type
                }
            )

            logger.info(
                f"✅ Social media updated successfully for {self.provider_id}: "
                f"{self.social_url} (type: {self.social_type})"
            )

            return {
                "success": True,
                "social_media_url": self.social_url,
                "social_media_type": self.social_type,
                "updated": updated
            }

        except Exception as e:
            logger.error(
                f"❌ Failed to update social media for {self.provider_id}: {e}"
            )
            raise

    async def undo(self) -> None:
        """
        Restore previous social media information (rollback operation).

        This method restores the previous social media URL and type in the
        provider record. It's called automatically by the Saga Pattern when
        a subsequent command fails.

        Best Effort Policy:
            - If old_url and old_type are None, nothing to undo (log and return)
            - If update fails, log error but don't raise (best effort)
            - Always log undo operations for debugging

        Example:
            >>> await command.undo()
            >>> # Previous social media values restored
        """
        if self.old_url is None and self.old_type is None:
            logger.warning(
                "⚠️ UpdateProviderSocialMediaCommand undo called but no old values "
                "(command may not have been executed or had no previous values)"
            )
            return

        logger.info(
            f"↩️ Rolling back social media update for provider: {self.provider_id}"
        )

        try:
            await self.provider_repository.update(
                self.provider_id,
                {
                    "social_media_url": self.old_url,
                    "social_media_type": self.old_type
                }
            )

            logger.info(
                f"✅ Social media restored for {self.provider_id}: "
                f"{self.old_url} (type: {self.old_type})"
            )

        except Exception as e:
            logger.error(
                f"⚠️ Failed to restore social media for {self.provider_id}: {e}. "
                f"Manual cleanup may be required."
            )
            # Don't raise - best effort rollback
