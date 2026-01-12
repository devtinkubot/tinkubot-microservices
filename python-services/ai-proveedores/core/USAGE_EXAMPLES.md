# Command and Saga Pattern Usage Examples

This document provides comprehensive examples of how to use the Command and Saga patterns implemented in the core module.

## Table of Contents
1. [Basic Command Usage](#basic-command-usage)
2. [Creating Custom Commands](#creating-custom-commands)
3. [Saga Pattern - Basic Usage](#saga-pattern---basic-usage)
4. [Saga Pattern - Advanced Usage](#saga-pattern---advanced-usage)
5. [Error Handling](#error-handling)
6. [Integration Example](#integration-example)

---

## Basic Command Usage

### Using RegisterProviderCommand

```python
from core import RegisterProviderCommand
from repositories.provider_repository import SupabaseProviderRepository

# Initialize repository
repository = SupabaseProviderRepository(supabase_client)

# Prepare provider data
provider_data = {
    "phone": "1234567890",
    "city": "Lima",
    "name": "Juan Pérez",
    "profession": "Plomero",
    "specialty": "Pipelines",
    "experience": "5 años",
    "email": "juan@example.com",
    "social_media_url": "https://instagram.com/juanperez",
    "social_media_type": "instagram"
}

# Create and execute command
command = RegisterProviderCommand(repository, provider_data)

try:
    result = await command.execute()
    print(f"Provider registered with ID: {result['id']}")
except Exception as e:
    print(f"Registration failed: {e}")
```

---

## Creating Custom Commands

### Example: UploadDniFrontCommand

```python
from core import Command
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class UploadDniFrontCommand(Command):
    """Upload DNI front photo to storage."""

    def __init__(self, image_service, provider_id: str, image_base64: str):
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url = None

    async def execute(self) -> Dict[str, Any]:
        """Upload the image to Supabase Storage."""
        logger.info(f"Uploading DNI front for provider {self.provider_id}")
        
        self.image_url = await self.image_service.upload_dni_front(
            self.provider_id, 
            self.image_base64
        )
        
        logger.info(f"DNI front uploaded: {self.image_url}")
        return {"dni_front_url": self.image_url}

    async def undo(self) -> None:
        """Delete the image from storage."""
        if self.image_url:
            logger.info(f"Deleting DNI front: {self.image_url}")
            try:
                await self.image_service.delete_image(self.image_url)
                logger.info(f"DNI front deleted successfully")
            except Exception as e:
                logger.error(f"Failed to delete DNI front: {e}")
```

### Example: UpdateSocialMediaCommand

```python
class UpdateSocialMediaCommand(Command):
    """Update provider's social media information."""

    def __init__(
        self, 
        provider_repository, 
        provider_id: str,
        social_media_url: str = None,
        social_media_type: str = None
    ):
        self.provider_repository = provider_repository
        self.provider_id = provider_id
        self.social_media_url = social_media_url
        self.social_media_type = social_media_type
        
        # Store old values for rollback
        self.old_url = None
        self.old_type = None

    async def execute(self) -> Dict[str, Any]:
        """Update social media in database."""
        # Fetch current provider data
        provider = await self.provider_repository.find_by_id(self.provider_id)
        
        # Store old values for potential rollback
        self.old_url = provider.get("social_media_url")
        self.old_type = provider.get("social_media_type")
        
        # Update with new values
        updated = await self.provider_repository.update(
            self.provider_id,
            {
                "social_media_url": self.social_media_url,
                "social_media_type": self.social_media_type
            }
        )
        
        logger.info(f"Social media updated for provider {self.provider_id}")
        return updated

    async def undo(self) -> None:
        """Restore previous social media information."""
        await self.provider_repository.update(
            self.provider_id,
            {
                "social_media_url": self.old_url,
                "social_media_type": self.old_type
            }
        )
        logger.info(f"Social media restored for provider {self.provider_id}")
```

---

## Saga Pattern - Basic Usage

### Single Command Saga

```python
from core import ProviderRegistrationSaga, RegisterProviderCommand

# Create saga
saga = ProviderRegistrationSaga()
saga.add_command(RegisterProviderCommand(repository, provider_data))

# Execute with automatic rollback
try:
    result = await saga.execute()
    print("Registration successful!")
except SagaExecutionError as e:
    print(f"Registration failed: {e}")
    # Rollback already executed automatically
```

### Multiple Command Saga (Fluent Interface)

```python
from core import (
    ProviderRegistrationSaga,
    RegisterProviderCommand,
    UploadDniFrontCommand,
    UploadDniBackCommand
)

# Build saga with fluent interface
saga = (ProviderRegistrationSaga()
    .add_command(RegisterProviderCommand(repository, provider_data))
    .add_command(UploadDniFrontCommand(image_service, provider_id, dni_front_image))
    .add_command(UploadDniBackCommand(image_service, provider_id, dni_back_image))
)

# Execute with automatic rollback
try:
    result = await saga.execute()
    print(f"Success! Executed {result['commands_executed']} commands")
except SagaExecutionError as e:
    print(f"Failed: {e}")
    print(f"Completed before failure: {e.completed_commands}")
```

---

## Saga Pattern - Advanced Usage

### Checking Saga Status

```python
# Before execution
status = saga.get_status()
print(f"Total commands: {status['total_commands']}")
print(f"Pending commands: {status['pending_commands']}")
print(f"Command names: {status['command_names']}")

# After execution
status = saga.get_status()
print(f"Executed commands: {status['executed_commands']}")
print(f"Executed names: {status['executed_names']}")
```

### Reusing a Saga

```python
# Execute once
await saga.execute()

# Reset for reuse
saga.reset()

# Add new commands
saga.add_command(RegisterProviderCommand(repository, new_provider_data))

# Execute again
await saga.execute()
```

### Building Complex Sagas Conditionally

```python
saga = ProviderRegistrationSaga()

# Always register provider
saga.add_command(RegisterProviderCommand(repository, provider_data))

# Conditionally add image upload commands
if flow.get("dni_front_image"):
    saga.add_command(
        UploadDniFrontCommand(image_service, provider_id, flow["dni_front_image"])
    )

if flow.get("dni_back_image"):
    saga.add_command(
        UploadDniBackCommand(image_service, provider_id, flow["dni_back_image"])
    )

if flow.get("face_image"):
    saga.add_command(
        UploadFacePhotoCommand(image_service, provider_id, flow["face_image"])
    )

# Execute with automatic rollback
try:
    result = await saga.execute()
except SagaExecutionError as e:
    print(f"Registration failed: {e}")
```

---

## Error Handling

### Handling SagaExecutionError

```python
from core.exceptions import SagaExecutionError

try:
    result = await saga.execute()
except SagaExecutionError as e:
    # Access error details
    print(f"Error message: {e.message}")
    print(f"Completed commands: {e.completed_commands}")
    print(f"Failed at step: {e.failed_at}")
    
    # Log for debugging
    for cmd_name in e.completed_commands:
        print(f"  - {cmd_name} completed successfully")
    
    # Rollback already executed automatically
    # Notify user
    return {
        "success": False,
        "message": "*Hubo un error al guardar tu información. Por favor intenta de nuevo.*"
    }
```

### Best Practices for Error Handling

```python
async def handle_provider_registration(flow, phone):
    """Handle provider registration with proper error handling."""
    
    try:
        # Build saga
        saga = build_registration_saga(flow, phone)
        
        # Execute
        result = await saga.execute()
        
        # Success
        return {
            "success": True,
            "message": "*¡Registro completado con éxito!*",
            "provider_id": result.get("provider_id")
        }
        
    except SagaExecutionError as e:
        # Automatic rollback occurred
        logger.error(
            f"Registration failed for phone {phone}: {e}. "
            f"Completed: {e.completed_commands}"
        )
        
        return {
            "success": False,
            "message": "*Hubo un error al guardar tu información. Por favor intenta de nuevo.*"
        }
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error during registration: {e}")
        
        return {
            "success": False,
            "message": "*Ocurrió un error inesperado. Por favor intenta más tarde.*"
        }
```

---

## Integration Example

### Complete Registration Handler

```python
from core import (
    ProviderRegistrationSaga,
    RegisterProviderCommand
)
from core.exceptions import SagaExecutionError

async def handle_confirm(flow, phone, provider_repository):
    """
    Handle provider confirmation with Saga Pattern.
    
    This function demonstrates a complete integration of the Command and Saga
    patterns for provider registration.
    """
    
    # Prepare provider data from flow
    provider_data = {
        "phone": phone,
        "city": flow.get("city"),
        "name": flow.get("name"),
        "profession": flow.get("profession"),
        "specialty": flow.get("specialty"),
        "experience": flow.get("experience"),
        "email": flow.get("email"),
        "social_media_url": flow.get("social_media_url"),
        "social_media_type": flow.get("social_media_type"),
        "verified": False,
        "available": False
    }
    
    # Build saga
    saga = ProviderRegistrationSaga()
    saga.add_command(RegisterProviderCommand(provider_repository, provider_data))
    
    # TODO: Add image upload commands when implemented
    # if flow.get("dni_front_image"):
    #     provider_id = await get_provider_id_from_flow(flow)
    #     saga.add_command(
    #         UploadDniFrontCommand(image_service, provider_id, flow["dni_front_image"])
    #     )
    
    # Execute with automatic rollback
    try:
        result = await saga.execute()
        
        logger.info(f"✅ Provider registration completed for phone {phone}")
        
        return {
            "success": True,
            "response": (
                "*¡Gracias! Tu registro ha sido completado exitosamente.*\n"
                "*Te notificaremos cuando tu cuenta sea verificada.*"
            )
        }
        
    except SagaExecutionError as e:
        logger.warning(
            f"⚠️ Registration failed for phone {phone}: {e.message}. "
            f"Commands completed before failure: {e.completed_commands}"
        )
        
        return {
            "success": False,
            "response": "*Hubo un error al guardar tu información. Por favor intenta de nuevo.*"
        }
```

---

## Testing Commands

### Unit Test Example

```python
import pytest
from core import RegisterProviderCommand

class MockRepository:
    """Mock repository for testing."""
    
    def __init__(self):
        self.created_providers = []
        self.deleted_ids = []
    
    async def create(self, data):
        provider = {"id": "test-123", **data}
        self.created_providers.append(provider)
        return provider
    
    async def delete(self, provider_id):
        self.deleted_ids.append(provider_id)

@pytest.mark.asyncio
async def test_register_provider_command():
    """Test RegisterProviderCommand execute and undo."""
    
    # Setup
    mock_repo = MockRepository()
    data = {"phone": "123", "name": "Test Provider"}
    command = RegisterProviderCommand(mock_repo, data)
    
    # Test execute
    result = await command.execute()
    assert result["id"] == "test-123"
    assert result["phone"] == "123"
    assert len(mock_repo.created_providers) == 1
    
    # Test undo
    await command.undo()
    assert "test-123" in mock_repo.deleted_ids
```

---

## Best Practices

1. **Always use type hints** - Makes code more maintainable
2. **Log all operations** - Essential for debugging
3. **Handle exceptions gracefully in undo()** - Use best effort approach
4. **Store state for rollback** - Keep old values before updating
5. **Use fluent interface for sagas** - More readable and maintainable
6. **Test commands independently** - Easier to debug
7. **Check if command executed before undoing** - Prevents errors
8. **Provide detailed error messages** - Helps with debugging
9. **Use saga.get_status() for monitoring** - Track execution progress
10. **Reset sagas only when safe** - Don't reset if rollback needed

---

## Migration Guide

### From Direct Registration to Command Pattern

**Before (without pattern):**
```python
async def register_provider(data):
    result = await supabase.table("providers").insert(data).execute()
    return result
```

**After (with Command Pattern):**
```python
async def register_provider(data):
    command = RegisterProviderCommand(repository, data)
    return await command.execute()
```

### From Manual Rollback to Saga Pattern

**Before (manual rollback):**
```python
async def register_with_images(provider_data, images):
    try:
        provider = await register_provider(provider_data)
        dni_front = await upload_dni_front(images["front"])
        dni_back = await upload_dni_front(images["back"])
    except Exception as e:
        # Manual rollback - error-prone
        if dni_back: await delete_image(dni_back)
        if dni_front: await delete_image(dni_front)
        if provider: await delete_provider(provider["id"])
        raise
```

**After (with Saga Pattern):**
```python
async def register_with_images(provider_data, images):
    saga = (ProviderRegistrationSaga()
        .add_command(RegisterProviderCommand(repository, provider_data))
        .add_command(UploadDniFrontCommand(image_service, provider_id, images["front"]))
        .add_command(UploadDniBackCommand(image_service, provider_id, images["back"])))
    
    # Automatic rollback!
    return await saga.execute()
```

---

## Summary

The Command and Saga patterns provide:
- **Automatic rollback** on failure
- **Separation of concerns** (each command does one thing)
- **Testability** (easy to unit test)
- **Maintainability** (easy to add new commands)
- **Reliability** (best-effort compensation)

For more information, see:
- `/home/du/.claude/plans/refactored-toasting-valley.md` - Architecture plan
- `core/commands.py` - Command implementations
- `core/saga.py` - Saga implementation
- `core/exceptions.py` - Custom exceptions
