# AGENTS.md - Tinkubot Microservices

Guide for agentic coding agents working in this repository.

## Project Overview
Microservices architecture for Tinkubot with Python services (FastAPI), Redis (Upstash), Supabase, and Docker. Services: ai-clientes (customer bot), ai-proveedores (provider bot), av-proveedores (availability).

## Build/Lint/Test Commands

### Running Python Scripts
```bash
# Always use absolute PYTHONPATH to ensure proper imports
PYTHONPATH=/home/du/produccion/tinkubot-microservices:/home/du/produccion/tinkubot-microservices/python-services:/home/du/produccion/tinkubot-microservices/python-services/shared-lib python3 <script>

# Example: Run a service
PYTHONPATH=/home/du/produccion/tinkubot-microservices python-services/ai-clientes/main.py
```

### Type Checking
```bash
# Pyright type checking for services
PYTHONPATH=/home/du/produccion/tinkubot-microservices/python-services/ai-clientes pyright
PYTHONPATH=/home/du/produccion/tinkubot-microservices/python-services/ai-proveedores pyright

# From service directory
cd python-services/ai-clientes && pyright .
```

### Running Tests
```bash
# Tests are standalone asyncio scripts (not pytest-based)
python3 test_service_detector_v3_standalone.py

# Run with proper PYTHONPATH
PYTHONPATH=/home/du/produccion/tinkubot-microservices python-services/ai-clientes/test_service_detector_v3_standalone.py
```

### Docker Operations
```bash
docker compose up              # Start all services
docker compose up <service>   # Start specific service
docker compose logs            # View all logs
docker compose logs -f <service>  # Follow service logs
docker compose build          # Rebuild images
docker compose down           # Stop all services
```

## Code Style Guidelines

### Imports
Organize imports by category with separators:

```python
# 1. Standard Library
import asyncio
import logging
import os
from typing import Any, Dict, Optional

# 2. FastAPI/External
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI

# 3. Local/Project
from config import settings
from services.session_manager import session_manager
```

Use `# type: ignore` for imports that don't have stub files (OpenAI, FastAPI, etc.).

### Type Annotations
Always use type hints, especially for function signatures and return types:

```python
from typing import Any, Dict, List, Optional

async def find_provider(
    phone: str,
    filters: Optional[ProviderFilter] = None
) -> Optional[Dict[str, Any]]:
    pass
```

Use `List`, `Dict`, `Optional` from `typing`, not built-in list/dict in type hints.

### Naming Conventions
- **Variables/Snake_case**: `provider_name`, `user_id`, `flow_data`
- **Classes/PascalCase**: `ProviderService`, `ServiceProfessionMapper`, `CustomerRepository`
- **Constants/UPPER_SNAKE_CASE**: `MAX_CONFIRM_ATTEMPTS`, `FLOW_TTL_SECONDS`, `OPENAI_TIMEOUT_SECONDS`
- **Private methods**: Prefix with underscore `_normalize_message()`, `_validate_with_mapper()`

### Error Handling
Define custom exceptions in `core/exceptions.py`:

```python
class RepositoryError(Exception):
    """Error en operaciones del repositorio."""
    pass

class InvalidTransitionError(Exception):
    def __init__(self, from_state, to_state):
        super().__init__(f"Invalid transition from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state
```

Handle exceptions gracefully with logging:

```python
try:
    await redis_client.get(key)
except Exception as e:
    logger.error(f"Error getting data for {phone}: {e}")
    return {}
```

### Async/Await
All service methods must be async. Use `await` for I/O operations:

```python
async def get_flow(phone: str) -> Dict[str, Any]:
    data = await redis_client.get(FLOW_KEY.format(phone))
    return data or {}
```

### Configuration
Use `pydantic-settings.BaseSettings` for configuration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
```

### Data Models
Use Pydantic `BaseModel` for API models and dataclasses for domain models:

```python
from pydantic import BaseModel, Field
from dataclasses import dataclass

class MessageProcessingResponse(BaseModel):
    response: str
    confidence: float = Field(ge=0, le=1)

@dataclass(frozen=True)
class ServiceDetectionResult:
    services: List[str]
    confidence: float
```

### Repository Pattern
Define interfaces in `repositories/interfaces.py` using ABC:

```python
from abc import ABC, abstractmethod

class IProviderRepository(ABC):
    @abstractmethod
    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        pass
```

### Logging
Configure module-level loggers:

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Processing message for {phone}")
logger.error(f"Failed to connect: {e}")
```

Use emojis sparingly for visual distinction: `✅`, `❌`, `📖`, `💾`.

### Docstrings
Use Google-style or Args/Returns format:

```python
async def extract_profession_and_location(
    history_text: str, last_message: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Extrae profesión y ubicación del mensaje.

    Args:
        history_text: Historial de conversación
        last_message: Último mensaje del usuario

    Returns:
        Tupla (profession, location) o (None, None) si no se detectan
    """
    pass
```

### Lazy Initialization
For services that depend on circular imports, use lazy initialization:

```python
def _get_query_interpreter():
    from services.query_interpreter_service import query_interpreter
    return query_interpreter
```

### Feature Flags
Feature flags defined in `core/feature_flags.py`:

```python
USE_REPOSITORY_INTERFACES = os.getenv("USE_REPOSITORY_INTERFACES", "true").lower() == "true"
USE_STATE_MACHINE = os.getenv("USE_STATE_MACHINE", "true").lower() == "true"
```

Check flags before using new features to enable gradual migration.

## Important Notes

- NO HARDCODED SERVICE DATA: Use `ServiceProfessionMapper` which reads from Supabase
- Always use absolute PYTHONPATH when running scripts
- Spanish comments and variable names are preferred for domain concepts
- Services communicate via Redis and direct API calls
- Check `docs/` for architectural plans before implementing new features
- Test changes in local environment before committing
- Use existing patterns: Repository, Service, State Machine, Saga
