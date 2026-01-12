# Core Architecture Module

This module implements the foundational design patterns for the AI Proveedores provider registration system.

## Overview

The core module provides three essential design patterns:

1. **Command Pattern** - Encapsulates operations as reversible objects
2. **Saga Pattern** - Orchestrates multi-step operations with automatic rollback
3. **Domain Exceptions** - Custom exceptions for error handling

## Architecture

```
core/
├── __init__.py           # Module exports
├── commands.py           # Command Pattern implementation
├── saga.py              # Saga Pattern implementation
├── exceptions.py        # Domain exceptions
├── README.md            # This file
└── USAGE_EXAMPLES.md    # Comprehensive usage examples
```

## Quick Start

### Basic Usage

```python
from core import ProviderRegistrationSaga, RegisterProviderCommand
from core.exceptions import SagaExecutionError

# Create a saga
saga = ProviderRegistrationSaga()
saga.add_command(RegisterProviderCommand(repository, provider_data))

# Execute with automatic rollback
try:
    result = await saga.execute()
    print("Success!")
except SagaExecutionError as e:
    print(f"Failed: {e}")
    # Rollback executed automatically
```

### Fluent Interface

```python
saga = (ProviderRegistrationSaga()
    .add_command(RegisterProviderCommand(repository, data))
    .add_command(UploadDniFrontCommand(image_service, pid, img))
    .add_command(UploadDniBackCommand(image_service, pid, img)))

result = await saga.execute()
```

## Components

### 1. Command Pattern (`commands.py`)

**Abstract Base Class:**
```python
class Command(ABC):
    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """Execute the command."""
        
    @abstractmethod
    async def undo(self) -> None:
        """Rollback the command."""
```

**Implemented Commands:**
- `RegisterProviderCommand` - Register provider in database
- TODO: `UploadDniFrontCommand` - Upload DNI front photo
- TODO: `UploadDniBackCommand` - Upload DNI back photo
- TODO: `UploadFacePhotoCommand` - Upload face/selfie photo
- TODO: `UpdateSocialMediaCommand` - Update social media info

**Creating Custom Commands:**
```python
from core import Command

class MyCustomCommand(Command):
    async def execute(self) -> Dict[str, Any]:
        # Do something
        return {"success": True}
    
    async def undo(self) -> None:
        # Undo it
        pass
```

### 2. Saga Pattern (`saga.py`)

**Main Class:**
```python
class ProviderRegistrationSaga:
    def add_command(self, command: Command) -> 'ProviderRegistrationSaga':
        """Add command to saga (fluent interface)."""
        
    async def execute(self) -> Dict[str, Any]:
        """Execute all commands with automatic rollback."""
        
    def get_status(self) -> Dict[str, Any]:
        """Get current saga status."""
        
    def reset(self) -> None:
        """Reset saga for reuse."""
```

**Key Features:**
- Automatic rollback on failure
- Detailed logging of each step
- Best-effort compensation
- Fluent interface
- Status monitoring

### 3. Exceptions (`exceptions.py`)

**Available Exceptions:**
- `SagaExecutionError` - Raised when saga execution fails
- `RepositoryError` - Repository operation errors
- `InvalidTransitionError` - Invalid state transitions
- `StateHandlerNotFoundError` - Missing state handlers

**Usage:**
```python
from core.exceptions import SagaExecutionError

try:
    await saga.execute()
except SagaExecutionError as e:
    print(f"Failed: {e.message}")
    print(f"Completed: {e.completed_commands}")
    print(f"Failed at: {e.failed_at}")
```

## Design Principles

### SOLID Principles Applied

1. **Single Responsibility Principle (SRP)**
   - Each command does one thing
   - Saga orchestrates, commands execute

2. **Open/Closed Principle (OCP)**
   - Easy to add new commands without modifying existing code
   - Extend Command ABC for new operations

3. **Liskov Substitution Principle (LSP)**
   - All Command implementations are interchangeable
   - Any Command can be used in Saga

4. **Interface Segregation Principle (ISP)**
   - Command interface is minimal (execute/undo only)
   - No forced dependencies

5. **Dependency Inversion Principle (DIP)**
   - Commands depend on repository interfaces, not concrete implementations
   - Easy to mock for testing

## Benefits

### Reliability
- Automatic rollback prevents partial updates
- Best-effort compensation handles edge cases
- Detailed logging for debugging

### Maintainability
- Clear separation of concerns
- Each command is self-contained
- Easy to add new operations

### Testability
- Commands can be unit tested independently
- Saga can be tested with mock commands
- Repository interface allows easy mocking

### Scalability
- Easy to add new commands
- Fluent interface for complex workflows
- Status monitoring for observability

## Logging

The implementation includes comprehensive logging:

```python
# Command execution
logger.info("📝 Registering provider: {phone}")
logger.info("✅ Provider registered successfully: {id}")

# Saga execution
logger.info("🚀 Starting saga execution with {n} commands")
logger.info("⚙️ Executing command {i}/{n}: {name}")
logger.info("✅ Command {i}/{n} completed: {name}")
logger.info("🎉 Saga completed successfully!")

# Rollback
logger.info("🔄 Rolling back {n} executed commands...")
logger.info("↩️ Rolling back command {i}: {name}")
logger.info("✅ Rollback successful for command {i}: {name}")

# Errors
logger.error("❌ Saga failed at command {i}/{n}: {name}")
logger.warning("⚠️ Rollback FAILED for command {i}: {name}")
```

## Integration with Repository

The Command Pattern is designed to work with the Repository Pattern:

```python
# Repository interface (another agent is implementing this)
class IProviderRepository(ABC):
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create provider."""
        
    async def find_by_phone(self, phone: str) -> Optional[Dict]:
        """Find provider by phone."""
        
    async def update(self, provider_id: str, data: Dict) -> Dict:
        """Update provider."""
        
    async def delete(self, provider_id: str) -> None:
        """Delete provider."""

# Command uses repository interface
class RegisterProviderCommand(Command):
    def __init__(self, provider_repository: IProviderRepository, data: Dict):
        self.provider_repository = provider_repository
        # ...
```

## Documentation

- **README.md** (this file) - Module overview and architecture
- **USAGE_EXAMPLES.md** - Comprehensive usage examples with code samples
- **Plan** - `/home/du/.claude/plans/refactored-toasting-valley.md`

## Testing

### Unit Test Example

```python
import pytest
from core import RegisterProviderCommand

class MockRepository:
    async def create(self, data):
        return {"id": "test-123", **data}
    
    async def delete(self, provider_id):
        pass

@pytest.mark.asyncio
async def test_register_provider_command():
    mock_repo = MockRepository()
    command = RegisterProviderCommand(mock_repo, {"phone": "123"})
    
    result = await command.execute()
    assert result["id"] == "test-123"
    
    await command.undo()  # Should not raise
```

## Future Enhancements

### Planned Commands (TODO)
- `UploadDniFrontCommand` - Upload DNI front photo
- `UploadDniBackCommand` - Upload DNI back photo
- `UploadFacePhotoCommand` - Upload face/selfie photo
- `UpdateSocialMediaCommand` - Update social media info
- `UpdateServicesCommand` - Update provider services
- `ToggleAvailabilityCommand` - Change availability status
- `DeleteProviderCommand` - Delete provider (soft delete)

### Planned Features
- Parallel command execution (for independent uploads)
- Command retry mechanism
- Saga persistence (for long-running sagas)
- Command timeout handling
- Metrics and monitoring

## File Statistics

- **Total Lines:** 733 lines of Python code
- **commands.py:** 298 lines (Command ABC + RegisterProviderCommand + TODOs)
- **saga.py:** 342 lines (ProviderRegistrationSaga + enhanced error handling)
- **exceptions.py:** 73 lines (4 custom exceptions)
- **__init__.py:** 53 lines (module exports and documentation)

## Contributing

When adding new commands:

1. Inherit from `Command` ABC
2. Implement `execute()` method
3. Implement `undo()` method with best-effort approach
4. Add comprehensive docstrings
5. Include type hints
6. Add logging (info, success, error)
7. Test independently
8. Update USAGE_EXAMPLES.md

Example:
```python
class MyNewCommand(Command):
    """
    Brief description.
    
    Detailed description with purpose, attributes, and example.
    """
    
    def __init__(self, dependency, param: str):
        self.dependency = dependency
        self.param = param
        self.old_value = None
    
    async def execute(self) -> Dict[str, Any]:
        """Execute with logging."""
        logger.info(f"Executing: {self.param}")
        result = await self.dependency.do_something(self.param)
        logger.info(f"Success: {result}")
        return result
    
    async def undo(self) -> None:
        """Undo with best-effort."""
        try:
            await self.dependency.undo(self.param)
            logger.info(f"Undo successful")
        except Exception as e:
            logger.error(f"Undo failed: {e}")
            # Don't raise - best effort
```

## License

This module is part of the Tinkubot Microservices project.

## Contact

For questions or issues, refer to the main project documentation.
