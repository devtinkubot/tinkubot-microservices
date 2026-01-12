# Plan Arquitectónico: Registro de Proveedores con Patrones SOLID

## Resumen Ejecutivo

**Objetivo:** Rediseñar el proceso de registro de proveedores aplicando patrones de diseño SOLID para mejorar mantenibilidad, testabilidad y robustez.

**Problemas Críticos Identificados:**
1. **Bug de Rollback:** Si falla la subida de imágenes después de registrar en BD, no hay compensación
2. **Alto Acoplamiento:** ProviderFlow depende directamente de 6+ servicios diferentes
3. **Violaciones SOLID:** SRP (responsabilidades mezcladas), ISP (interfaces sobrecargadas), DIP (depende de implementaciones concretas)
4. **Edge Cases No Manejados:** Desconexiones, timeouts, fallos parciales, validaciones faltantes

**Recomendación:** Implementar **State Machine + Command/Saga + Repository** - una combinación que soluciona problemas reales sin over-engineering.

---

## Estado Actual del Arte

### Patrones Implementados

| Patrón | Implementación | Calidad | Archivo |
|--------|---------------|---------|---------|
| **Strategy** | StateRouter para routing dinámico | ✅ Excelente | `handlers/state_router.py` |
| **Delegation** | ProviderFlowDelegateService | ⚠️ Parcial | `services/provider_flow_delegate_service.py` |
| **Repository** | Implícito en business_logic.py | ❌ Incompleto | `services/business_logic.py` |
| **Template Method** | Handler pattern similar | ❌ Sin interfaz común | `flows/provider_flow.py` |

### Flujo Conversacional Actual

```
WhatsApp → WaProveedores → AI Proveedores
                                   ↓
                         WhatsAppOrchestratorService
                                   ↓
                         ProviderFlowDelegateService
                                   ↓
                         ProviderFlow (StateRouter)
                                   ↓
                    [13 Handlers: city → name → profession → ... → confirm]
                                   ↓
                         BusinessLogic → Supabase
                                   ↓
                         ImageService → Supabase Storage
```

### Estados del Flujo (13 totales)

```python
awaiting_city → awaiting_name → awaiting_profession → awaiting_specialty
→ awaiting_experience → awaiting_email → awaiting_social_media
→ awaiting_dni_front_photo → awaiting_dni_back_photo → awaiting_face_photo
→ confirm

+ awaiting_real_phone (solo para teléfonos tipo @lid)
```

---

## Arquitectura Recomendada

### Patrón Core: State Machine

**Problema que resuelve:**
- Transiciones de estado están dispersas en 13 handlers diferentes
- No hay validación de transiciones inválidas
- No hay visualización del flujo completo

**Implementación:**

```python
# core/state_machine.py
from enum import Enum
from typing import Dict, Callable, Optional

class ProviderState(str, Enum):
    """Estados del flujo de registro de proveedores."""
    AWAITING_CITY = "awaiting_city"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PROFESSION = "awaiting_profession"
    AWAITING_SPECIALTY = "awaiting_specialty"
    AWAITING_EXPERIENCE = "awaiting_experience"
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_SOCIAL_MEDIA = "awaiting_social_media"
    AWAITING_DNI_FRONT_PHOTO = "awaiting_dni_front_photo"
    AWAITING_DNI_BACK_PHOTO = "awaiting_dni_back_photo"
    AWAITING_FACE_PHOTO = "awaiting_face_photo"
    AWAITING_REAL_PHONE = "awaiting_real_phone"
    CONFIRM = "confirm"

class ProviderStateMachine:
    """
    Máquina de estados para el registro de proveedores.

    Aplica State Pattern + transiciones validadas.
    """

    # Transiciones permitidas: current_state -> [next_states]
    TRANSITIONS: Dict[ProviderState, list[ProviderState]] = {
        ProviderState.AWAITING_CITY: [ProviderState.AWAITING_NAME],
        ProviderState.AWAITING_NAME: [ProviderState.AWAITING_PROFESSION],
        ProviderState.AWAITING_PROFESSION: [ProviderState.AWAITING_SPECIALTY],
        ProviderState.AWAITING_SPECIALTY: [ProviderState.AWAITING_EXPERIENCE],
        ProviderState.AWAITING_EXPERIENCE: [ProviderState.AWAITING_EMAIL],
        ProviderState.AWAITING_EMAIL: [ProviderState.AWAITING_SOCIAL_MEDIA],
        ProviderState.AWAITING_SOCIAL_MEDIA: [ProviderState.AWAITING_DNI_FRONT_PHOTO],
        ProviderState.AWAITING_DNI_FRONT_PHOTO: [ProviderState.AWAITING_DNI_BACK_PHOTO],
        ProviderState.AWAITING_DNI_BACK_PHOTO: [ProviderState.AWAITING_FACE_PHOTO],
        ProviderState.AWAITING_FACE_PHOTO: [ProviderState.CONFIRM],
        ProviderState.AWAITING_REAL_PHONE: [ProviderState.AWAITING_CITY],
        ProviderState.CONFIRM: [],  # Estado final
    }

    def __init__(self):
        self._handlers: Dict[ProviderState, Callable] = {}

    def register_handler(self, state: ProviderState, handler: Callable) -> None:
        """Registra un handler para un estado."""
        self._handlers[state] = handler

    def can_transition(self, from_state: ProviderState, to_state: ProviderState) -> bool:
        """Valida si una transición es permitida."""
        allowed = self.TRANSITIONS.get(from_state, [])
        return to_state in allowed

    def transition(self, from_state: ProviderState, to_state: ProviderState,
                  flow: Dict, message: str) -> Dict[str, Any]:
        """
        Ejecuta una transición de estado con validación.

        Raises:
            InvalidTransitionError: Si la transición no es permitida
            StateHandlerNotFoundError: Si no hay handler para el estado
        """
        if not self.can_transition(from_state, to_state):
            raise InvalidTransitionError(from_state, to_state)

        handler = self._handlers.get(to_state)
        if not handler:
            raise StateHandlerNotFoundError(to_state)

        return handler(flow, message)

    def get_next_states(self, current_state: ProviderState) -> list[ProviderState]:
        """Retorna los estados posibles desde el estado actual."""
        return self.TRANSITIONS.get(current_state, [])
```

**Beneficios:**
- ✅ Visualización clara del flujo completo
- ✅ Prevención de transiciones inválidas
- ✅ Fácil agregar nuevos estados (Open/Closed)
- ✅ Testeable independientemente

---

### Patrón de Transacciones: Command + Saga

**Problema que resuelve:**
- **BUG CRÍTICO:** Si falla upload de imágenes después de registrar en BD, hay rollback parcial
- No hay compensating transactions
- El flujo no es reversible

**Implementación:**

```python
# core/commands.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class Command(ABC):
    """Interfaz para comandos reversibles."""

    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """Ejecuta el comando."""

    @abstractmethod
    async def undo(self) -> None:
        """Deshace el comando (compensating transaction)."""

class RegisterProviderCommand(Command):
    """Comando para registrar un proveedor en la base de datos."""

    def __init__(self, provider_repository, data: Dict[str, Any]):
        self.provider_repository = provider_repository
        self.data = data
        self.provider_id: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Registra el proveedor en Supabase."""
        result = await self.provider_repository.create(self.data)
        self.provider_id = result.get("id")
        logger.info(f"✅ Provider registered: {self.provider_id}")
        return result

    async def undo(self) -> None:
        """Elimina el proveedor de la base de datos."""
        if self.provider_id:
            await self.provider_repository.delete(self.provider_id)
            logger.info(f"↩️ Provider registration undone: {self.provider_id}")

class UploadDniFrontCommand(Command):
    """Comando para subir foto frontal de DNI."""

    def __init__(self, image_service, provider_id: str, image_base64: str):
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Sube la imagen a Supabase Storage."""
        self.image_url = await self.image_service.upload_dni_front(
            self.provider_id, self.image_base64
        )
        return {"dni_front_url": self.image_url}

    async def undo(self) -> None:
        """Elimina la imagen de Supabase Storage."""
        if self.image_url:
            await self.image_service.delete_image(self.image_url)
            logger.info(f"↩️ DNI front image deleted: {self.image_url}")

# Similar commands for:
# - UploadDniBackCommand
# - UploadFacePhotoCommand
# - UpdateProviderSocialMediaCommand
```

```python
# core/saga.py
from typing import List, Optional

class SagaExecutionError(Exception):
    """Error en la ejecución de la saga."""
    def __init__(self, message: str, completed_commands: List[str]):
        super().__init__(message)
        self.completed_commands = completed_commands

class ProviderRegistrationSaga:
    """
    Orquesta el registro de proveedor con compensating transactions.

    Si cualquier paso falla, ejecuta undo() de todos los pasos anteriores.
    """

    def __init__(self):
        self.commands: List[Command] = []
        self.executed_commands: List[Command] = []

    def add_command(self, command: Command) -> 'ProviderRegistrationSaga':
        """Agrega un comando a la saga (fluent interface)."""
        self.commands.append(command)
        return self

    async def execute(self) -> Dict[str, Any]:
        """
        Ejecuta todos los comandos en orden.

        Si alguno falla, ejecuta undo() de todos los anteriores.
        """
        self.executed_commands = []

        try:
            for command in self.commands:
                result = await command.execute()
                self.executed_commands.append(command)
                logger.info(f"✅ Command executed: {command.__class__.__name__}")

            return {"success": True, "message": "Registration completed"}

        except Exception as e:
            logger.error(f"❌ Saga failed at command {len(self.executed_commands) + 1}: {e}")
            await self._rollback()
            raise SagaExecutionError(
                f"Registration failed: {str(e)}",
                [c.__class__.__name__ for c in self.executed_commands]
            )

    async def _rollback(self) -> None:
        """
        Ejecuta undo() de todos los comandos ejecutados, en orden inverso.
        """
        logger.info("🔄 Rolling back saga...")

        for command in reversed(self.executed_commands):
            try:
                await command.undo()
                logger.info(f"↩️ Undone: {command.__class__.__name__}")
            except Exception as undo_error:
                logger.error(f"⚠️ Undo failed for {command.__class__.__name__}: {undo_error}")
                # Continuar con el siguiente undo (best effort)

# Uso en handle_confirm():
async def handle_confirm(flow, phone, register_provider_fn, upload_media_fn, reset_flow_fn):
    # Crear saga con todos los pasos
    saga = ProviderRegistrationSaga()
    saga.add_command(RegisterProviderCommand(provider_repo, provider_payload))
    saga.add_command(UploadDniFrontCommand(image_service, provider_id, flow["dni_front_image"]))
    saga.add_command(UploadDniBackCommand(image_service, provider_id, flow["dni_back_image"]))
    saga.add_command(UploadFacePhotoCommand(image_service, provider_id, flow["face_image"]))

    # Ejecutar con rollback automático si falla
    try:
        result = await saga.execute()
        # Continuar con el flujo normal...
    except SagaExecutionError as e:
        # Ya se hizo rollback automáticamente
        return {"success": False, "response": "*Hubo un error al guardar tu información. Por favor intenta de nuevo.*"}
```

**Beneficios:**
- ✅ **Rollback automático** si falla cualquier paso
- ✅ **Transacciones atómicas lógicas** entre BD y Storage
- ✅ **Mejor manejo de errores** con logging granular
- ✅ **Testeable** cada comando independientemente

---

### Patrón de Acceso a Datos: Repository

**Problema que resuelve:**
- `registrar_proveedor()` conoce detalles de Supabase
- Difícil de testear (requiere Supabase real o mock complejo)
- Violación de Dependency Inversion Principle

**Implementación:**

```python
# repositories/provider_repository.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class IProviderRepository(ABC):
    """Interfaz de repositorio de proveedores (DIP)."""

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo proveedor."""
        pass

    @abstractmethod
    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Busca proveedor por teléfono."""
        pass

    @abstractmethod
    async def update(self, provider_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza proveedor."""
        pass

    @abstractmethod
    async def delete(self, provider_id: str) -> None:
        """Elimina proveedor."""
        pass

class SupabaseProviderRepository(IProviderRepository):
    """Implementación de repositorio con Supabase."""

    def __init__(self, supabase_client):
        self._supabase = supabase_client

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea proveedor con upsert por teléfono."""
        from utils.db_utils import run_supabase

        upsert_payload = {
            **data,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .upsert(upsert_payload, on_conflict="phone")
            .execute(),
            timeout=5.0,
            label="providers.create",
        )

        # Extraer resultado (código existente refactorizado)
        registro = self._extract_result(result)
        if not registro:
            raise RepositoryError("Failed to create provider")

        return registro

    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Busca proveedor por teléfono."""
        from utils.db_utils import run_supabase

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute(),
            timeout=5.0,
            label="providers.find_by_phone",
        )

        data = getattr(result, "data", [])
        return data[0] if data else None

    async def update(self, provider_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza campos específicos del proveedor."""
        from utils.db_utils import run_supabase

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .update(data)
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.update",
        )

        data = getattr(result, "data", [])
        if not data:
            raise RepositoryError(f"Provider {provider_id} not found")

        return data[0]

    async def delete(self, provider_id: str) -> None:
        """Elimina proveedor (para rollback)."""
        from utils.db_utils import run_supabase

        await run_supabase(
            lambda: self._supabase.table("providers")
            .delete()
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.delete",
        )
        logger.info(f"🗑️ Provider {provider_id} deleted from repository")

    def _extract_result(self, result) -> Optional[Dict[str, Any]]:
        """Extrae el resultado de la operación de Supabase."""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and result.data:
                return result.data[0]
            elif isinstance(result.data, dict):
                return result.data
        return None
```

**Beneficios:**
- ✅ **Testing:** Se puede mock con IProviderRepository
- ✅ **Desacoplamiento:** Lógica de negocio no depende de Supabase
- ✅ **Flexibilidad:** Fácil cambiar de implementación (MongoDB, Postgres directo, etc.)
- ✅ **SOLID:** Cumple Dependency Inversion Principle

---

## Situaciones Pasadas por Alto

### 1. Edge Cases Críticos

| Situación | Riesgo | Solución Recomendada |
|-----------|--------|---------------------|
| **Desconexión durante registro** | Datos huérfanos en Redis | Cleanup automático de flujos expirados (TTL + job) |
| **Falla de Supabase después de upload** | Imágenes huérfanas en Storage | Saga con compensating transactions |
| **Registro simultáneo desde 2 dispositivos** | Race conditions | Lock distribuido en Redis por teléfono |
| **Timeout de OpenAI** | Flujo atascado | Timeout configurable + fallback |
| **Redis down durante proceso** | Inconsistencia de datos | Fallback a memoria + retry |

### 2. Validaciones Faltantes

| Campo | Validación Actual | Falta | Prioridad |
|-------|------------------|-------|-----------|
| **Imágenes** | No hay validación de tamaño/formato | Validar tamaño (máx 10MB), formato (JPG/PNG), contenido real | 🔴 Alta |
| **Email duplicado** | No se valida antes de registro | Verificar que email no esté ya registrado | 🟠 Media |
| **Teléfono duplicado** | Solo maneja upsert | Validar antes de iniciar flujo | 🟠 Media |
| **Rate limiting** | No hay límite de intentos | Limitar por IP y teléfono | 🟠 Media |
| **Sanitización XSS** | Básica con Pydantic | Sanitizar mensajes antes de guardar | 🟡 Baja |

### 3. Problemas de Performance

| Problema | Impacto | Solución |
|----------|---------|----------|
| **Upload secuencial de imágenes** | Registro lento (3 imágenes = 3x tiempo) | Upload paralelo con límite de concurrencia (2-3) |
| **Refetch innecesario en upsert** | Latencia adicional | Usar `return=representation` en upsert |
| **Sin caché de datos maestros** | Validación repetida de ciudades | Caché en Redis de ciudades, profesiones |
| **Sin pool de conexiones** | Sobrecarga de Supabase | Connection pooling con asyncpg |

### 4. Monitoreo Inadecuado

| Métrica | Estado | Acción |
|---------|--------|--------|
| **Tiempo promedio de registro** | ❌ No se mide | Agregar tracking de tiempo |
| **Tasa de éxito/fallo por etapa** | ❌ No se trackea | Logs estructurados con etapa |
| **Alertas de errores recurrentes** | ❌ No hay | Implementar alertas en Sentry/Datadog |
| **Storage cuota** | ❌ No se monitorea | Alertar al 80% de capacidad |

---

## Archivos a Crear

| Archivo | Propósito | Prioridad |
|---------|-----------|-----------|
| `core/__init__.py` | Paquete de core architecture | 🔴 Alta |
| `core/state_machine.py` | State Machine para flujo conversacional | 🔴 Alta |
| `core/commands.py` | Command Pattern para operaciones reversibles | 🔴 Alta |
| `core/saga.py` | Saga orquestador con rollback automático | 🔴 Alta |
| `core/exceptions.py` | Excepciones personalizadas del dominio | 🔴 Alta |
| `repositories/__init__.py` | Paquete de repositorios | 🟠 Media |
| `repositories/provider_repository.py` | Repository Pattern para proveedores | 🟠 Media |
| `repositories/interfaces.py` | Interfaces de repositorios (IProviderRepository) | 🟠 Media |
| `validators/validator_factory.py` | Factory Pattern para validadores | 🟡 Baja |
| `validators/state_validator.py` | Validador de transiciones de estado | 🟡 Baja |

---

## Archivos a Modificar

| Archivo | Cambio | Esfuerzo |
|---------|--------|---------|
| `flows/provider_flow.py` | Migrar a State Machine | 3-4 días |
| `services/provider_flow_delegate_service.py` | Usar Saga para orquestar comandos | 2-3 días |
| `services/business_logic.py` | Migrar lógica a ProviderRepository | 1-2 días |
| `services/validation_service.py` | Migrar a ValidatorFactory | 1-2 días |
| `services/image_service.py` | Crear Command objects para upload | 1 día |
| `app/dependencies.py` | Inyectar repositorios y servicios | 0.5 días |
| `main.py` o `bootstrap.py` | Configurar contenedor de DI | 0.5 días |

---

## Estrategia de Implementación: Evitación de Breaking Changes

### Principios Clave para Sin Breaking Changes

1. **Strangler Fig Pattern**: Crear nuevo código alongside código viejo, migrar gradualmente
2. **Feature Flags**: Usar flags para habilitar/deshabilitar nuevas funcionalidades
3. **Adapters/Shims**: Crear adaptadores para mantener interfaces compatibles
4. **Parallel Implementation**: Ambas implementaciones conviven durante transición
5. **Gradual Migration**: Migrar uso incremental, no Big Bang

### Estrategia de 5 Fases por Implementación

Cada fase sigue este ciclo riguroso:

```python
# 1. EXTRACT: Extraer nueva funcionalidad sin modificar código existente
#    - Crear nuevos archivos/paquetes
#    - Implementar nueva lógica en paralelo
#    - NO modificar código existente aún

# 2. UPDATE: Actualizar código existente para usar nueva implementación
#    - Agregar feature flags
#    - Crear adaptadores si es necesario
#    - Migrar llamadas gradualmente
#    - Mantener código viejo como fallback

# 3. CLEANUP: Eliminar código obsoleto
#    - Remover código viejo solo después de validar
#    - Eliminar adaptadores temporales
#    - Limpiar imports no usados

# 4. RECONSTRUIR CONTENEDORES: Docker build + restart
#    - docker compose build <servicio>
#    - docker compose up -d <servicio>
#    - Verificar logs de startup

# 5. PROBAR: Testing exhaustivo antes de continuar
#    - Probar flujo completo de registro
#    - Verificar que no hay errores en logs
#    - Testing manual con WhatsApp real
#    - Revertir si hay problemas

# 6. PUSH MAIN GITHUB: Commit + push a main
#    - git add .
#    - git commit -m "feat: descripcion del cambio"
#    - git push origin main
```

---

## Fases de Implementación

### Fase 1: Repository Pattern + Command Básico

#### 🎯 Objetivo
Implementar Repository Pattern para acceso a datos y Command básico, **sin romper el código existente**.

#### 📋 Paso 1: EXTRACT (2 días)

**Crear nuevos archivos (NO modificar existentes):**

```bash
# Crear paquete repositories
mkdir -p python-services/ai-proveedores/repositories
touch python-services/ai-proveedores/repositories/__init__.py

# Crear paquete core
mkdir -p python-services/ai-proveedores/core
touch python-services/ai-proveedores/core/__init__.py
```

**1.1 Crear `repositories/interfaces.py`:**
```python
"""Interfaces de repositorios (DIP - Dependency Inversion Principle)."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IProviderRepository(ABC):
    """Interfaz abstracta para repositorio de proveedores."""

    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un nuevo proveedor."""
        pass

    @abstractmethod
    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Busca proveedor por teléfono."""
        pass

    @abstractmethod
    async def update(self, provider_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza proveedor."""
        pass

    @abstractmethod
    async def delete(self, provider_id: str) -> None:
        """Elimina proveedor."""
        pass
```

**1.2 Crear `repositories/provider_repository.py`:**
```python
"""Implementación de Repository Pattern para proveedores."""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from repositories.interfaces import IProviderRepository
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Excepción base para errores del repositorio."""
    pass


class SupabaseProviderRepository(IProviderRepository):
    """
    Implementación de repositorio con Supabase.

    Wraps la lógica existente de business_logic.py sin romperla.
    """

    def __init__(self, supabase_client):
        self._supabase = supabase_client

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea proveedor con upsert por teléfono."""
        # IMPORTANTE: Reutilizamos código existente de business_logic
        # NO modificamos business_logic todavía
        from services.business_logic import normalizar_datos_proveedor

        # Normalizar datos usando función existente
        datos_normalizados = normalizar_datos_proveedor(data)

        upsert_payload = {
            **datos_normalizados,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .upsert(upsert_payload, on_conflict="phone")
            .execute(),
            timeout=5.0,
            label="providers.create",
        )

        registro = self._extract_result(result)
        if not registro:
            raise RepositoryError("Failed to create provider")

        return registro

    async def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Busca proveedor por teléfono."""
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute(),
            timeout=5.0,
            label="providers.find_by_phone",
        )

        data = getattr(result, "data", [])
        return data[0] if data else None

    async def update(self, provider_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza campos específicos del proveedor."""
        result = await run_supabase(
            lambda: self._supabase.table("providers")
            .update(data)
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.update",
        )

        data = getattr(result, "data", [])
        if not data:
            raise RepositoryError(f"Provider {provider_id} not found")

        return data[0]

    async def delete(self, provider_id: str) -> None:
        """Elimina proveedor (para rollback)."""
        await run_supabase(
            lambda: self._supabase.table("providers")
            .delete()
            .eq("id", provider_id)
            .execute(),
            timeout=5.0,
            label="providers.delete",
        )
        logger.info(f"🗑️ Provider {provider_id} deleted from repository")

    def _extract_result(self, result) -> Optional[Dict[str, Any]]:
        """Extrae el resultado de la operación de Supabase."""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and result.data:
                return result.data[0]
            elif isinstance(result.data, dict):
                return result.data
        return None
```

**1.3 Crear `core/commands.py`:**
```python
"""Command Pattern para operaciones reversibles."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Command(ABC):
    """Interfaz para comandos reversibles."""

    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """Ejecuta el comando."""

    @abstractmethod
    async def undo(self) -> None:
        """Deshace el comando (compensating transaction)."""


class RegisterProviderCommand(Command):
    """Comando para registrar un proveedor en la base de datos."""

    def __init__(self, provider_repository, data: Dict[str, Any]):
        self.provider_repository = provider_repository
        self.data = data
        self.provider_id: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Registra el proveedor usando el repositorio."""
        result = await self.provider_repository.create(self.data)
        self.provider_id = result.get("id")
        logger.info(f"✅ Provider registered: {self.provider_id}")
        return result

    async def undo(self) -> None:
        """Elimina el proveedor de la base de datos."""
        if self.provider_id:
            await self.provider_repository.delete(self.provider_id)
            logger.info(f"↩️ Provider registration undone: {self.provider_id}")
```

**1.4 Crear `core/exceptions.py`:**
```python
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
    """Error en la ejecución de la saga."""

    def __init__(self, message: str, completed_commands: list):
        super().__init__(message)
        self.completed_commands = completed_commands
```

**1.5 Crear `core/saga.py`:**
```python
"""Saga Pattern para orquestación con compensating transactions."""
import logging
from typing import List, Dict, Any
from core.exceptions import SagaExecutionError

logger = logging.getLogger(__name__)


class ProviderRegistrationSaga:
    """
    Orquesta el registro de proveedor con compensating transactions.

    Si cualquier paso falla, ejecuta undo() de todos los pasos anteriores.
    """

    def __init__(self):
        from core.commands import Command
        self.commands: List[Command] = []
        self.executed_commands: List[Command] = []

    def add_command(self, command) -> 'ProviderRegistrationSaga':
        """Agrega un comando a la saga (fluent interface)."""
        self.commands.append(command)
        return self

    async def execute(self) -> Dict[str, Any]:
        """
        Ejecuta todos los comandos en orden.

        Si alguno falla, ejecuta undo() de todos los anteriores.
        """
        self.executed_commands = []

        try:
            for command in self.commands:
                result = await command.execute()
                self.executed_commands.append(command)
                logger.info(f"✅ Command executed: {command.__class__.__name__}")

            return {"success": True, "message": "Registration completed"}

        except Exception as e:
            logger.error(f"❌ Saga failed at command {len(self.executed_commands) + 1}: {e}")
            await self._rollback()
            raise SagaExecutionError(
                f"Registration failed: {str(e)}",
                [c.__class__.__name__ for c in self.executed_commands]
            )

    async def _rollback(self) -> None:
        """
        Ejecuta undo() de todos los comandos ejecutados, en orden inverso.
        """
        logger.info("🔄 Rolling back saga...")

        for command in reversed(self.executed_commands):
            try:
                await command.undo()
                logger.info(f"↩️ Undone: {command.__class__.__name__}")
            except Exception as undo_error:
                logger.error(f"⚠️ Undo failed for {command.__class__.__name__}: {undo_error}")
                # Continuar con el siguiente undo (best effort)
```

#### 📋 Paso 2: UPDATE (1 día)

**2.1 Modificar `services/business_logic.py` - Agregar Feature Flag:**

```python
# Agregar al principio del archivo
USE_REPOSITORY_PATTERN = False  # Feature flag: cambiar a True cuando esté listo

async def registrar_proveedor(
    supabase: Client,
    datos_proveedor: Dict[str, Any],
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.

    FEATURE FLAG: USE_REPOSITORY_PATTERN
    - False: Usa implementación original (actual)
    - True: Usa nuevo Repository Pattern
    """
    if USE_REPOSITORY_PATTERN:
        # NUEVA implementación con Repository
        from repositories.provider_repository import SupabaseProviderRepository
        from core.commands import RegisterProviderCommand
        from core.saga import ProviderRegistrationSaga

        repo = SupabaseProviderRepository(supabase)
        saga = ProviderRegistrationSaga()
        saga.add_command(RegisterProviderCommand(repo, datos_proveedor))

        try:
            result = await saga.execute()
            # Extraer proveedor registrado para mantener compatibilidad
            provider = await repo.find_by_phone(datos_proveedor.get("phone", ""))
            return provider
        except Exception as e:
            logger.error(f"❌ Repository pattern failed: {e}")
            # Fallback a implementación original si falla
            logger.warning("⚠️ Falling back to original implementation")
            USE_REPOSITORY_PATTERN = False  # Deshabilitar flag temporalmente

    # IMPLEMENTACIÓN ORIGINAL (sin cambios)
    # ... [código existente保持不变] ...
```

**2.2 Crear `app/dependencies.py` (o modificar si existe):**

```python
"""Inyección de dependencias para la aplicación."""
from functools import lru_cache
from supabase import Client
from repositories.provider_repository import SupabaseProviderRepository
from repositories.interfaces import IProviderRepository


@lru_cache()
def get_provider_repository(supabase: Client) -> IProviderRepository:
    """
    Factory para el repositorio de proveedores.

    Permite cambiar la implementación fácilmente (DIP).
    """
    return SupabaseProviderRepository(supabase)
```

#### 📋 Paso 3: CLEANUP (0.5 días)

**No aplica en esta fase** - mantenemos ambas implementaciones.

#### 📋 Paso 4: RECONSTRUIR CONTENEDORES (0.5 días)

```bash
cd /home/du/produccion/tinkubot-microservices
docker compose build ai-proveedores
docker compose up -d ai-proveedores
docker compose logs -f ai-proveedores --tail=50
```

#### 📋 Paso 5: PROBAR (1 día)

**5.1 Verificar que el servicio inicia sin errores:**
```bash
docker compose logs ai-proveedores | grep -i error
# Debería estar vacío (no errores)
```

**5.2 Test de funcionalidad existente:**
- Iniciar un registro de proveedor real por WhatsApp
- Verificar que el flujo funciona normalmente
- Verificar que NO se usa el nuevo código aún (USE_REPOSITORY_PATTERN=False)

**5.3 Test con feature flag habilitado (opcional):**
- Cambiar `USE_REPOSITORY_PATTERN = True` en business_logic.py
- Reconstruir contenedor
- Hacer un registro de prueba
- Verificar que funciona igual

**5.4 Verificar logs:**
```bash
docker compose logs ai-proveedores | grep "Repository pattern"
docker compose logs ai-proveedores | grep "Provider registered"
```

#### 📋 Paso 6: PUSH MAIN GITHUB (0.5 días)

```bash
cd /home/du/produccion/tinkubot-microservices
git add python-services/ai-proveedores/repositories/
git add python-services/ai-proveedores/core/
git add python-services/ai-proveedores/services/business_logic.py
git add python-services/ai-proveedores/app/dependencies.py
git commit -m "feat(ai-proveedores): add Repository Pattern + Command (v1)

- Add IProviderRepository interface
- Add SupabaseProviderRepository implementation
- Add Command base interface
- Add RegisterProviderCommand
- Add ProviderRegistrationSaga
- Add feature flag USE_REPOSITORY_PATTERN (disabled by default)
- Maintain backward compatibility with original implementation

BREAKING CHANGES: None (feature flag disabled)"
git push origin main
```

#### ✅ Entregable Fase 1
- ✅ Repository Pattern implementado
- ✅ Command Pattern base implementado
- ✅ Saga Pattern base implementado
- ✅ **NO BREAKING CHANGES** - código original intacto
- ✅ Feature flag permite migración gradual
- ✅ Testeado y en producción

---

### Fase 2: State Machine para Flujo Conversacional

#### 🎯 Objetivo
Implementar State Machine para validar transiciones de estado, **sin romper el flujo existente**.

#### 📋 Paso 1: EXTRACT (2 días)

**1.1 Crear `core/state_machine.py`:**
```python
"""State Machine para flujo de registro de proveedores."""
from enum import Enum
from typing import Dict, Callable, Optional
import logging

from core.exceptions import InvalidTransitionError, StateHandlerNotFoundError

logger = logging.getLogger(__name__)


class ProviderState(str, Enum):
    """Estados del flujo de registro de proveedores."""
    AWAITING_CITY = "awaiting_city"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PROFESSION = "awaiting_profession"
    AWAITING_SPECIALTY = "awaiting_specialty"
    AWAITING_EXPERIENCE = "awaiting_experience"
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_SOCIAL_MEDIA = "awaiting_social_media"
    AWAITING_DNI_FRONT_PHOTO = "awaiting_dni_front_photo"
    AWAITING_DNI_BACK_PHOTO = "awaiting_dni_back_photo"
    AWAITING_FACE_PHOTO = "awaiting_face_photo"
    AWAITING_REAL_PHONE = "awaiting_real_phone"
    CONFIRM = "confirm"


class ProviderStateMachine:
    """
    Máquina de estados para el registro de proveedores.

    Aplica State Pattern + transiciones validadas.
    """

    # Transiciones permitidas: current_state -> [next_states]
    TRANSITIONS: Dict[ProviderState, list[ProviderState]] = {
        ProviderState.AWAITING_CITY: [ProviderState.AWAITING_NAME],
        ProviderState.AWAITING_NAME: [ProviderState.AWAITING_PROFESSION],
        ProviderState.AWAITING_PROFESSION: [ProviderState.AWAITING_SPECIALTY],
        ProviderState.AWAITING_SPECIALTY: [ProviderState.AWAITING_EXPERIENCE],
        ProviderState.AWAITING_EXPERIENCE: [ProviderState.AWAITING_EMAIL],
        ProviderState.AWAITING_EMAIL: [ProviderState.AWAITING_SOCIAL_MEDIA],
        ProviderState.AWAITING_SOCIAL_MEDIA: [ProviderState.AWAITING_DNI_FRONT_PHOTO],
        ProviderState.AWAITING_DNI_FRONT_PHOTO: [ProviderState.AWAITING_DNI_BACK_PHOTO],
        ProviderState.AWAITING_DNI_BACK_PHOTO: [ProviderState.AWAITING_FACE_PHOTO],
        ProviderState.AWAITING_FACE_PHOTO: [ProviderState.CONFIRM],
        ProviderState.AWAITING_REAL_PHONE: [ProviderState.AWAITING_CITY],
        ProviderState.CONFIRM: [],  # Estado final
    }

    def __init__(self, enable_validation: bool = False):
        """
        Inicializa la máquina de estados.

        Args:
            enable_validation: Si True, valida transiciones (feature flag)
        """
        self._handlers: Dict[ProviderState, Callable] = {}
        self._enable_validation = enable_validation

    def register_handler(self, state: ProviderState, handler: Callable) -> None:
        """Registra un handler para un estado."""
        self._handlers[state] = handler

    def can_transition(self, from_state: ProviderState, to_state: ProviderState) -> bool:
        """Valida si una transición es permitida."""
        allowed = self.TRANSITIONS.get(from_state, [])
        return to_state in allowed

    def transition(self, from_state: ProviderState, to_state: ProviderState,
                  flow: Dict, message: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta una transición de estado.

        Si enable_validation=False, usa comportamiento original (sin validación).
        """
        if self._enable_validation:
            # Validar transición
            if not self.can_transition(from_state, to_state):
                logger.warning(f"⚠️ Invalid transition: {from_state} → {to_state}")
                raise InvalidTransitionError(from_state, to_state)

        # Obtener handler
        handler = self._handlers.get(to_state)
        if not handler:
            raise StateHandlerNotFoundError(to_state)

        # Ejecutar handler
        return handler(flow, message, **kwargs)

    def get_next_states(self, current_state: ProviderState) -> list[ProviderState]:
        """Retorna los estados posibles desde el estado actual."""
        return self.TRANSITIONS.get(current_state, [])
```

#### 📋 Paso 2: UPDATE (2 días)

**2.1 Modificar `handlers/state_router.py` - Agregar soporte State Machine:**

```python
"""Router dinámico para estados de flujo (Open/Closed Principle)."""
import logging
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)

# Feature flag para State Machine
USE_STATE_MACHINE = False


class StateRouter:
    """Router dinámico para estados de flujo."""

    def __init__(self, use_state_machine: bool = USE_STATE_MACHINE):
        """
        Inicializa el router.

        Args:
            use_state_machine: Si True, usa ProviderStateMachine
        """
        self._handlers: Dict[str, Callable] = {}
        self._use_state_machine = use_state_machine

        # Importar y configurar State Machine si está habilitado
        if self._use_state_machine:
            from core.state_machine import ProviderStateMachine, ProviderState
            self._state_machine = ProviderStateMachine(enable_validation=True)
            self._ProviderState = ProviderState
            logger.info("✅ StateRouter initialized with State Machine")
        else:
            self._state_machine = None
            logger.info("ℹ️ StateRouter initialized without State Machine (legacy mode)")

    def register(self, state_name: str, handler: Callable) -> None:
        """Registra un manejador para un estado."""
        self._handlers[state_name] = handler

        # Si usamos State Machine, registrar también allí
        if self._state_machine:
            try:
                state_enum = self._ProviderState(state_name)
                self._state_machine.register_handler(state_enum, handler)
            except ValueError:
                logger.warning(f"⚠️ State {state_name} not in ProviderState enum")

    def route(self, state: str, flow: Dict[str, Any], message_text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Enrutar al manejador apropiado según el estado.

        Si use_state_machine=True, valida transiciones.
        """
        if self._state_machine:
            # Usar State Machine con validación de transiciones
            try:
                current_state = self._ProviderState(state)
                next_state = self._ProviderState(flow.get("state", state))

                return self._state_machine.transition(
                    current_state, next_state, flow, message_text, **kwargs
                )
            except Exception as e:
                logger.error(f"❌ State Machine error: {e}")
                # Fallback a modo legado
                logger.warning("⚠️ Falling back to legacy routing")
                return self._legacy_route(state, flow, message_text, **kwargs)
        else:
            # Modo legado original (sin cambios)
            return self._legacy_route(state, flow, message_text, **kwargs)

    def _legacy_route(self, state: str, flow: Dict[str, Any], message_text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Routing original sin validaciones (código existente)."""
        handler = self._handlers.get(state)
        if not handler:
            raise ValueError(f"Estado desconocido: '{state}'")
        return handler(flow, message_text, **kwargs)
```

**2.2 Modificar `flows/provider_flow.py` - NO CAMBIAR**

**NO MODIFICAMOS provider_flow.py aún** - mantenemos todos los handlers como están.

#### 📋 Paso 3: CLEANUP (0.5 días)

No aplica - mantenemos ambos modos.

#### 📋 Paso 4: RECONSTRUIR CONTENEDORES (0.5 días)

```bash
docker compose build ai-proveedores
docker compose up -d ai-proveedores
docker compose logs -f ai-proveedores --tail=50
```

#### 📋 Paso 5: PROBAR (1 día)

**5.1 Test modo legado (USE_STATE_MACHINE = False):**
- Iniciar registro por WhatsApp
- Verificar que funciona como antes
- Verificar logs: "StateRouter initialized without State Machine (legacy mode)"

**5.2 Test con State Machine (USE_STATE_MACHINE = True):**
- Cambiar feature flag
- Reconstruir contenedor
- Iniciar registro
- Verificar que las transiciones funcionan
- Intentar transición inválida (forzar en test)
- Verificar que se rechaza

**5.3 Verificar logs:**
```bash
docker compose logs ai-proveedores | grep "State Machine"
docker compose logs ai-proveedores | grep "Invalid transition"
```

#### 📋 Paso 6: PUSH MAIN GITHUB (0.5 días)

```bash
git add python-services/ai-proveedores/core/state_machine.py
git add python-services/ai-proveedores/handlers/state_router.py
git commit -m "feat(ai-proveedores): add State Machine for flow control

- Add ProviderState enum with all 13 states
- Add ProviderStateMachine with transition validation
- Update StateRouter to support both legacy and SM modes
- Add feature flag USE_STATE_MACHINE (disabled by default)
- Maintain backward compatibility

BREAKING CHANGES: None (feature flag disabled)"
git push origin main
```

#### ✅ Entregable Fase 2
- ✅ State Machine implementado
- ✅ Validación de transiciones lista
- ✅ **NO BREAKING CHANGES** - modo legado funciona idéntico
- ✅ Feature flag permite activar gradualmente
- ✅ Testeado y en producción

---

### Fase 3: Saga con Rollback Automático para Imágenes

#### 🎯 Objetivo
Implementar rollback automático cuando falla upload de imágenes, **solucionando el bug crítico sin romper funcionalidad existente**.

#### 📋 Paso 1: EXTRACT (2 días)

**1.1 Extender `core/commands.py` - Agregar comandos de imágenes:**

```python
# Agregar al final del archivo existente

class UploadDniFrontCommand(Command):
    """Comando para subir foto frontal de DNI."""

    def __init__(self, image_service, provider_id: str, image_base64: str):
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Sube la imagen a Supabase Storage."""
        # Usar función existente de image_service
        self.image_url = await self.image_service.upload_dni_front(
            self.provider_id, self.image_base64
        )
        return {"dni_front_url": self.image_url}

    async def undo(self) -> None:
        """Elimina la imagen de Supabase Storage."""
        if self.image_url:
            # Implementar delete si no existe en image_service
            try:
                await self.image_service.delete_image(self.image_url)
                logger.info(f"↩️ DNI front image deleted: {self.image_url}")
            except AttributeError:
                # Si delete_image no existe, crear método helper
                logger.warning(f"⚠️ delete_image not implemented, URL orphaned: {self.image_url}")


class UploadDniBackCommand(Command):
    """Comando para subir foto reverso de DNI."""

    def __init__(self, image_service, provider_id: str, image_base64: str):
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Sube la imagen a Supabase Storage."""
        self.image_url = await self.image_service.upload_dni_back(
            self.provider_id, self.image_base64
        )
        return {"dni_back_url": self.image_url}

    async def undo(self) -> None:
        """Elimina la imagen de Supabase Storage."""
        if self.image_url:
            try:
                await self.image_service.delete_image(self.image_url)
                logger.info(f"↩️ DNI back image deleted: {self.image_url}")
            except AttributeError:
                logger.warning(f"⚠️ delete_image not implemented, URL orphaned: {self.image_url}")


class UploadFacePhotoCommand(Command):
    """Comando para subir selfie."""

    def __init__(self, image_service, provider_id: str, image_base64: str):
        self.image_service = image_service
        self.provider_id = provider_id
        self.image_base64 = image_base64
        self.image_url: Optional[str] = None

    async def execute(self) -> Dict[str, Any]:
        """Sube la imagen a Supabase Storage."""
        self.image_url = await self.image_service.upload_face_photo(
            self.provider_id, self.image_base64
        )
        return {"face_photo_url": self.image_url}

    async def undo(self) -> None:
        """Elimina la imagen de Supabase Storage."""
        if self.image_url:
            try:
                await self.image_service.delete_image(self.image_url)
                logger.info(f"↩️ Face photo deleted: {self.image_url}")
            except AttributeError:
                logger.warning(f"⚠️ delete_image not implemented, URL orphaned: {self.image_url}")
```

**1.2 Modificar `services/image_service.py` - Agregar delete_image:**

```python
# Agregar método a la clase ImageService

async def delete_image(self, image_url: str) -> None:
    """
    Elimina una imagen de Supabase Storage.

    Args:
        image_url: URL completa de la imagen en Storage
    """
    try:
        # Extraer path del storage de la URL
        # URL format: https://xxx.supabase.co/storage/v1/object/public/bucket/path
        parsed = urlparse(image_url)
        path_parts = parsed.path.split('/storage/v1/object/public/')
        if len(path_parts) < 2:
            logger.error(f"Invalid storage URL: {image_url}")
            return

        storage_path = path_parts[1]

        # Eliminar del storage
        result = await run_supabase(
            lambda: self._supabase.storage.from_(self._bucket).remove(storage_path),
            timeout=5.0,
            label=f"storage.delete.{storage_path}"
        )

        logger.info(f"🗑️ Image deleted from storage: {storage_path}")
    except Exception as e:
        logger.error(f"❌ Error deleting image {image_url}: {e}")
        raise
```

#### 📋 Paso 2: UPDATE (2 días)

**2.1 Modificar `flows/provider_flow.py` - Agregar feature flag a handle_confirm:**

```python
# Feature flag para Saga rollback
USE_SAGA_ROLLBACK = False

@staticmethod
async def handle_confirm(
    flow: Dict[str, Any],
    message_text: Optional[str],
    phone: str,
    register_provider_fn: Callable[[ProviderCreate], Awaitable[Optional[Dict[str, Any]]]],
    upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
    reset_flow_fn: Callable[[], Awaitable[None]],
    logger: Any,
) -> Dict[str, Any]:
    """Maneja la confirmación del registro."""

    # ... [validación existente保持不变] ...

    if (
        text.startswith("1")
        or text.startswith("confirm")
        or text in {"si", "ok", "listo", "confirmar"}
    ):
        is_valid, result = validate_provider_payload(flow, phone)
        if not is_valid:
            return result

        provider_payload = result

        # ELEGIR MODO: Saga o Original
        if USE_SAGA_ROLLBACK:
            # NUEVO MODO con rollback automático
            return await _handle_confirm_with_saga(
                flow, phone, provider_payload, register_provider_fn, upload_media_fn, reset_flow_fn, logger
            )
        else:
            # MODO ORIGINAL (sin cambios)
            return await _handle_confirm_original(
                flow, phone, provider_payload, register_provider_fn, upload_media_fn, reset_flow_fn, logger
            )


async def _handle_confirm_with_saga(
    flow: Dict[str, Any],
    phone: str,
    provider_payload: Dict[str, Any],
    register_provider_fn: Callable,
    upload_media_fn: Callable,
    reset_flow_fn: Callable,
    logger: Any,
) -> Dict[str, Any]:
    """Handle confirm con Saga rollback (NUEVA implementación)."""
    from core.saga import ProviderRegistrationSaga
    from core.commands import (
        RegisterProviderCommand,
        UploadDniFrontCommand,
        UploadDniBackCommand,
        UploadFacePhotoCommand,
    )
    from app.dependencies import get_provider_repository
    from services.image_service import ImageService

    # Obtener servicios
    supabase = get_supabase_client()  # Implementar getter
    provider_repo = get_provider_repository(supabase)
    image_service = ImageService(supabase)

    try:
        # Crear saga con todos los pasos
        saga = ProviderRegistrationSaga()
        saga.add_command(RegisterProviderCommand(provider_repo, provider_payload))

        # Primero registrar para obtener provider_id
        result = await saga.execute()
        provider_id = result.get("provider_id")

        # Luego agregar comandos de imagen
        if flow.get("dni_front_image"):
            saga.add_command(UploadDniFrontCommand(image_service, provider_id, flow["dni_front_image"]))
        if flow.get("dni_back_image"):
            saga.add_command(UploadDniBackCommand(image_service, provider_id, flow["dni_back_image"]))
        if flow.get("face_image"):
            saga.add_command(UploadFacePhotoCommand(image_service, provider_id, flow["face_image"]))

        # Ejecutar saga completa
        await saga.execute()

        # Resto del flujo original...
        await reset_flow_fn()
        return {
            "success": True,
            "messages": [{"response": provider_under_review_message()}],
            "reset_flow": True,
            "new_flow": {
                "state": "pending_verification",
                "has_consent": True,
                "registration_allowed": False,
                "provider_id": provider_id,
                "services": flow.get("services", []),
                "awaiting_verification": True,
            },
        }

    except Exception as e:
        logger.error(f"❌ Saga failed: {e}")
        # Saga ya hizo rollback automáticamente
        return {
            "success": False,
            "response": "*Hubo un error al guardar tu información. Por favor intenta de nuevo.*"
        }


async def _handle_confirm_original(
    flow: Dict[str, Any],
    phone: str,
    provider_payload: Dict[str, Any],
    register_provider_fn: Callable,
    upload_media_fn: Callable,
    reset_flow_fn: Callable,
    logger: Any,
) -> Dict[str, Any]:
    """Handle confirm original (CÓDIGO EXISTENTE sin cambios)."""
    # ... [mantener código original exactamente como está] ...
    registered_provider = await register_provider_fn(provider_payload)
    if registered_provider:
        logger.info(
            "Proveedor registrado exitosamente: %s",
            registered_provider.get("id"),
        )
        provider_id = registered_provider.get("id")
        servicios_registrados = parse_services_string(
            registered_provider.get("services")
        )
        flow["services"] = servicios_registrados
        if provider_id:
            await upload_media_fn(provider_id, flow)
        await reset_flow_fn()
        return {
            "success": True,
            "messages": [{"response": provider_under_review_message()}],
            "reset_flow": True,
            "new_flow": {
                "state": "pending_verification",
                "has_consent": True,
                "registration_allowed": False,
                "provider_id": provider_id,
                "services": servicios_registrados,
                "awaiting_verification": True,
            },
        }

    logger.error("No se pudo registrar el proveedor")
    return {
        "success": False,
        "response": (
            "*Hubo un error al guardar tu informacion. Por favor intenta de nuevo.*"
        ),
    }
```

#### 📋 Paso 3: CLEANUP (0.5 días)

No aplica - mantenemos ambos modos.

#### 📋 Paso 4: RECONSTRUIR CONTENEDORES (0.5 días)

```bash
docker compose build ai-proveedores
docker compose up -d ai-proveedores
docker compose logs -f ai-proveedores --tail=50
```

#### 📋 Paso 5: PROBAR (1.5 días)

**5.1 Test modo original (USE_SAGA_ROLLBACK = False):**
- Completar registro exitoso
- Verificar que funciona como antes

**5.2 Test rollback con Saga (USE_SAGA_ROLLBACK = True):**

**5.2.1 Test registro exitoso:**
- Completar registro completo
- Verificar que se registró en BD
- Verificar que las imágenes están en Storage

**5.2.2 Test rollback cuando falla Storage:**
- Simular fallo en upload de imagen (ej: Storage bucket lleno)
- Verificar que se hizo rollback:
  - Proveedor NO está en BD
  - Imágenes NO están en Storage
- Verificar logs: "Rolling back saga..."

**5.2.3 Test rollback cuando falla BD:**
- Simular fallo en BD (ej: constraint violation)
- Verificar que no hay datos huérfanos

**5.3 Verificar logs:**
```bash
docker compose logs ai-proveedores | grep "Saga"
docker compose logs ai-proveedores | grep "Rolling back"
```

#### 📋 Paso 6: PUSH MAIN GITHUB (0.5 días)

```bash
git add python-services/ai-proveedores/core/commands.py
git add python-services/ai-proveedores/core/saga.py
git add python-services/ai-proveedores/flows/provider_flow.py
git add python-services/ai-proveedores/services/image_service.py
git commit -m "feat(ai-proveedores): add Saga rollback for image uploads

- Add UploadDniFrontCommand, UploadDniBackCommand, UploadFacePhotoCommand
- Add delete_image method to ImageService
- Update handle_confirm to support both original and Saga modes
- Add feature flag USE_SAGA_ROLLBACK (disabled by default)
- Fix critical bug: orphaned images when upload fails after DB registration

BREAKING CHANGES: None (feature flag disabled)"
git push origin main
```

#### ✅ Entregable Fase 3
- ✅ Saga Pattern implementado con rollback automático
- ✅ **BUG CRÍTICO SOLUCIONADO**: Imágenes huérfanas eliminadas
- ✅ Comandos de reversión implementados
- ✅ **NO BREAKING CHANGES** - modo original intacto
- ✅ Testeado rollback exitoso y fallo
- ✅ En producción

---

### Fase 4: Validaciones y Optimizaciones

#### 🎯 Objetivo
Implementar validaciones faltantes y optimizaciones de performance, **mejorando robustez sin romper funcionalidad**.

#### 📋 Paso 1: EXTRACT (2 días)

**1.1 Crear `validators/image_validator.py`:**
```python
"""Validaciones para imágenes subidas."""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Constantes
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_FORMATS = ['image/jpeg', 'image/png', 'image/jpg']


class ImageValidationError(Exception):
    """Error en validación de imagen."""
    pass


def validate_image_size(size_bytes: int) -> Tuple[bool, Optional[str]]:
    """
    Valida el tamaño de la imagen.

    Args:
        size_bytes: Tamaño en bytes

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if size_bytes > MAX_IMAGE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, (
            f"*La imagen es muy grande ({size_mb:.1f}MB). "
            f"El máximo permitido es {MAX_IMAGE_SIZE_MB}MB.*"
        )

    if size_bytes == 0:
        return False, "*La imagen está vacía. Por favor envía una imagen válida.*"

    return True, None


def validate_image_format(mime_type: str) -> Tuple[bool, Optional[str]]:
    """
    Valida el formato de la imagen.

    Args:
        mime_type: Tipo MIME de la imagen

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if not mime_type or mime_type not in ALLOWED_FORMATS:
        return False, (
            f"*Formato no válido. Solo se permite JPG y PNG.*"
        )

    return True, None


def validate_image_content(image_base64: str) -> Tuple[bool, Optional[str]]:
    """
    Valida que el contenido base64 sea una imagen válida.

    Args:
        image_base64: Imagen en formato base64

    Returns:
        Tupla (es_válido, mensaje_error)
    """
    if not image_base64:
        return False, "*No se recibió ninguna imagen.*"

    # Verificar que es base64 válido
    try:
        import base64
        decoded = base64.b64decode(image_base64, validate=True)

        # Verificar que es una imagen (magic bytes)
        if len(decoded) < 10:
            return False, "*La imagen es muy pequeña o corrupta.*"

        # JPEG: FF D8 FF
        if decoded[0:2] == b'\xFF\xD8':
            return True, None

        # PNG: 89 50 4E 47
        if decoded[0:4] == b'\x89PNG':
            return True, None

        return False, "*El archivo no parece ser una imagen válida (JPG/PNG).*"

    except Exception as e:
        logger.error(f"Error validando imagen: {e}")
        return False, "*La imagen tiene un formato inválido.*"
```

**1.2 Modificar `services/image_service.py` - Agregar validaciones:**

```python
# Agregar al inicio
from validators.image_validator import (
    validate_image_size,
    validate_image_format,
    validate_image_content,
    ImageValidationError,
)

# Feature flag para validaciones
ENABLE_IMAGE_VALIDATION = False


async def upload_dni_front(self, provider_id: str, image_base64: str) -> str:
    """Sube foto frontal de DNI."""

    if ENABLE_IMAGE_VALIDATION:
        # Validar tamaño
        size_bytes = len(base64.b64decode(image_base64))
        is_valid, error_msg = validate_image_size(size_bytes)
        if not is_valid:
            raise ImageValidationError(error_msg)

        # Validar formato
        # (necesitamos pasar mime_type, ajustar firma del método)

        # Validar contenido
        is_valid, error_msg = validate_image_content(image_base64)
        if not is_valid:
            raise ImageValidationError(error_msg)

    # Resto del código existente...
```

**1.3 Crear `utils/performance_utils.py`:**
```python
"""Utilidades de optimización de performance."""
import asyncio
from typing import List, Callable, Any, Coroutine
import logging

logger = logging.getLogger(__name__)


async def execute_parallel(
    tasks: List[Coroutine],
    max_concurrency: int = 3,
) -> List[Any]:
    """
    Ejecuta tareas en paralelo con límite de concurrencia.

    Útil para upload de imágenes en paralelo.

    Args:
        tasks: Lista de corutinas a ejecutar
        max_concurrency: Máximo número de tareas simultáneas

    Returns:
        Lista de resultados en el mismo orden
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded_task(task):
        async with semaphore:
            return await task

    results = await asyncio.gather(
        *[bounded_task(task) for task in tasks],
        return_exceptions=True
    )

    # Verificar si hubo errores
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        logger.error(f"❌ {len(errors)} tasks failed in parallel execution")
        raise errors[0]  # Lanzar primer error

    return results
```

#### 📋 Paso 2: UPDATE (1.5 días)

**2.1 Modificar `services/business_logic.py` - Agregar validaciones:**

```python
# Feature flags para mejoras
USE_REPOSITORY_PATTERN = False
ENABLE_IMAGE_VALIDATION = False
ENABLE_PARALLEL_UPLOAD = False


async def registrar_proveedor(
    supabase: Client,
    datos_proveedor: Dict[str, Any],
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.

    Feature Flags:
    - USE_REPOSITORY_PATTERN: Usa nuevo Repository Pattern
    - ENABLE_IMAGE_VALIDATION: Valida imágenes antes de subir
    - ENABLE_PARALLEL_UPLOAD: Sube imágenes en paralelo
    """
    # ... [código existente保持不变] ...
```

**2.2 Modificar flows para usar parallel upload (feature flag):**

```python
# En flows/provider_flow.py o services/provider_flow_delegate_service.py

async def upload_media_parallel(provider_id: str, flow: Dict[str, Any]) -> None:
    """Sube imágenes en paralelo si ENABLE_PARALLEL_UPLOAD=True."""
    if not ENABLE_PARALLEL_UPLOAD:
        # Usar método original secuencial
        return await upload_media_fn(provider_id, flow)

    from utils.performance_utils import execute_parallel

    tasks = []

    if flow.get("dni_front_image"):
        tasks.append(image_service.upload_dni_front(provider_id, flow["dni_front_image"]))
    if flow.get("dni_back_image"):
        tasks.append(image_service.upload_dni_back(provider_id, flow["dni_back_image"]))
    if flow.get("face_image"):
        tasks.append(image_service.upload_face_photo(provider_id, flow["face_image"]))

    # Ejecutar en paralelo (máximo 3 simultáneas)
    await execute_parallel(tasks, max_concurrency=3)
```

#### 📋 Paso 3: CLEANUP (0.5 días)

No aplica - feature flags controlan todo.

#### 📋 Paso 4: RECONSTRUIR CONTENEDORES (0.5 días)

```bash
docker compose build ai-proveedores
docker compose up -d ai-proveedores
docker compose logs -f ai-proveedores --tail=50
```

#### 📋 Paso 5: PROBAR (1 día)

**5.1 Test validaciones de imágenes:**
- Habilitar ENABLE_IMAGE_VALIDATION
- Intentar subir imagen > 10MB
- Verificar que rechaza con mensaje claro
- Intentar subir imagen no JPG/PNG
- Verificar que rechaza

**5.2 Test upload paralelo:**
- Habilitar ENABLE_PARALLEL_UPLOAD
- Medir tiempo con 3 imágenes
- Comparar con modo secuencial
- Verificar mejora de performance

**5.3 Test que todo funciona con flags deshabilitados:**
- Deshabilitar todos los flags
- Verificar que funciona como antes

#### 📋 Paso 6: PUSH MAIN GITHUB (0.5 días)

```bash
git add python-services/ai-proveedores/validators/
git add python-services/ai-proveedores/utils/performance_utils.py
git add python-services/ai-proveedores/services/image_service.py
git commit -m "feat(ai-proveedores): add validations and performance optimizations

- Add image size validation (max 10MB)
- Add image format validation (JPG/PNG only)
- Add image content validation (base64, magic bytes)
- Add parallel upload for images (3 concurrent)
- Add feature flags: ENABLE_IMAGE_VALIDATION, ENABLE_PARALLEL_UPLOAD
- Maintain backward compatibility (all flags disabled by default)

BREAKING CHANGES: None (all feature flags disabled)"
git push origin main
```

#### ✅ Entregable Fase 4
- ✅ Validaciones de imágenes implementadas
- ✅ Upload paralelo implementado
- ✅ **NO BREAKING CHANGES** - todas las mejoras son optativas
- ✅ Feature flags permiten habilitar por partes
- ✅ Testeado y en producción

---

### Fase 5: Activación Completa y Limpieza Final

#### 🎯 Objetivo
Habilitar todos los feature flags, eliminar código obsoleto, y consolidar la nueva arquitectura.

#### 📋 Paso 1: EXTRACT (0 días)

No aplica - todo ya está extraído.

#### 📋 Paso 2: UPDATE (2 días)

**2.1 Activar todos los feature flags:**

```python
# services/business_logic.py
USE_REPOSITORY_PATTERN = True  # ✅ Activar
ENABLE_IMAGE_VALIDATION = True  # ✅ Activar
ENABLE_PARALLEL_UPLOAD = True  # ✅ Activar

# handlers/state_router.py
USE_STATE_MACHINE = True  # ✅ Activar

# flows/provider_flow.py
USE_SAGA_ROLLBACK = True  # ✅ Activar
```

**2.2 Monitorear logs después de activar cada flag:**

```bash
# Después de activar USE_REPOSITORY_PATTERN
docker compose logs ai-proveedores | grep "Provider registered" | tail -20

# Después de activar USE_STATE_MACHINE
docker compose logs ai-proveedores | grep "State Machine" | tail -20

# Después de activar USE_SAGA_ROLLBACK
docker compose logs ai-proveedores | grep "Saga" | tail -20

# Después de activar ENABLE_IMAGE_VALIDATION
docker compose logs ai-proveedores | grep "Image validation" | tail -20

# Después de activar ENABLE_PARALLEL_UPLOAD
docker compose logs ai-proveedores | grep "parallel" | tail -20
```

#### 📋 Paso 3: CLEANUP (2 días)

**3.1 Eliminar código legado:**

```python
# services/business_logic.py - Eliminar implementación original
async def registrar_proveedor(
    supabase: Client,
    datos_proveedor: Dict[str, Any],
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando Repository Pattern.

    Feature Flags (ALL ENABLED):
    - Repository Pattern: ✅
    - Saga Rollback: ✅
    - Image Validation: ✅
    - Parallel Upload: ✅
    """
    # Eliminar if USE_REPOSITORY_PATTERN - ya siempre True
    from repositories.provider_repository import SupabaseProviderRepository
    from core.commands import RegisterProviderCommand
    from core.saga import ProviderRegistrationSaga

    repo = SupabaseProviderRepository(supabase)
    saga = ProviderRegistrationSaga()
    saga.add_command(RegisterProviderCommand(repo, datos_proveedor))

    try:
        result = await saga.execute()
        provider = await repo.find_by_phone(datos_proveedor.get("phone", ""))
        return provider
    except Exception as e:
        logger.error(f"❌ Registration failed: {e}")
        raise
```

**3.2 Eliminar feature flags:**

```python
# Remover constantes de feature flags
# USE_REPOSITORY_PATTERN ❌ Eliminar
# USE_STATE_MACHINE ❌ Eliminar
# USE_SAGA_ROLLBACK ❌ Eliminar
# ENABLE_IMAGE_VALIDATION ❌ Eliminar
# ENABLE_PARALLEL_UPLOAD ❌ Eliminar
```

**3.3 Eliminar código de fallback legado:**

```python
# handlers/state_router.py - Eliminar _legacy_route
# flows/provider_flow.py - Eliminar _handle_confirm_original
# core/state_machine.py - Eliminar enable_validation parameter
```

**3.4 Eliminar imports no usados:**

```bash
# Buscar imports no usados
cd python-services/ai-proveedores
python -m pylint --disable=all --enable=unused-import */*.py
```

#### 📋 Paso 4: RECONSTRUIR CONTENEDORES (0.5 días)

```bash
docker compose build ai-proveedores
docker compose up -d ai-proveedores
docker compose logs -f ai-proveedores --tail=100
```

#### 📋 Paso 5: PROBAR (2 días)

**5.1 Test E2E completo:**
- Registrar 3 proveedores nuevos
- Verificar que todo funciona
- Medir tiempos de registro
- Verificar que no hay errores en logs

**5.2 Test de rollback:**
- Simular fallo en Storage
- Verificar rollback automático funciona
- Verificar que no hay datos huérfanos

**5.3 Test de carga (opcional):**
- Registrar 10 proveedores simultáneos
- Verificar que no hay race conditions
- Verificar performance

**5.4 Verificar logs detallados:**
```bash
# Verificar que no hay errores
docker compose logs ai-proveedores | grep -i error | tail -50

# Verificar que State Machine está activo
docker compose logs ai-proveedores | grep "State Machine"

# Verificar que Saga está activo
docker compose logs ai-proveedores | grep "Saga"

# Verificar que Repository está activo
docker compose logs ai-proveedores | grep "Repository"
```

#### 📋 Paso 6: PUSH MAIN GITHUB (0.5 días)

```bash
git add python-services/ai-proveedores/
git commit -m "feat(ai-proveedores): enable new architecture and remove legacy code

✅ ACTIVATED:
- Repository Pattern (DIP compliance)
- State Machine (transition validation)
- Saga Pattern (automatic rollback)
- Image Validation (size, format, content)
- Parallel Upload (3 concurrent uploads)

🗑️ REMOVED:
- Legacy registration code
- Feature flags
- Fallback implementations
- Unused imports

📊 IMPACT:
- Bug fix: Orphaned images eliminated
- Performance: 3x faster image uploads
- Maintainability: SOLID principles applied
- Testability: Mockable repositories and commands

BREAKING CHANGES: None (legacy behavior maintained, just better)"
git push origin main
```

#### ✅ Entregable Fase 5
- ✅ Toda la nueva arquitectura activa
- ✅ Código legado eliminado
- ✅ Feature flags eliminados
- ✅ Limpieza completa
- ✅ Testeado exhaustivamente
- ✅ En producción

---

## Estimación de Esfuerzo Actualizada

| Fase | Duración | Complejidad | Riesgo | Breaking Changes |
|------|----------|-------------|-------|-----------------|
| Fase 1: Repository + Command | 1 semana | Media | Bajo | ❌ Ninguno |
| Fase 2: State Machine | 1 semana | Media | Bajo | ❌ Ninguno |
| Fase 3: Saga + Rollback | 1.5 semanas | Alta | Medio | ❌ Ninguno |
| Fase 4: Validaciones + Performance | 1 semana | Media | Bajo | ❌ Ninguno |
| Fase 5: Activación + Cleanup | 1 semana | Media | Medio | ❌ Ninguno |
| **Total** | **5.5 semanas** | | | |

**Recomendación:** Implementar en fases con feature flags. Cada fase agrega valor independiente y **no rompe nada**.

---

## Patrones de Diseño Aplicados

### Principio Single Responsibility (SRP)
- **Antes:** ProviderFlow hacía validación + normalización + routing
- **Después:** Cada clase tiene una responsabilidad única
  - `ProviderStateMachine`: Solo transiciones
  - `ValidationService`: Solo validaciones
  - `NormalizationService`: Solo normalizaciones
  - `ProviderRepository`: Solo acceso a datos

### Principio Open/Closed (OCP)
- **Antes:** Agregar estado requería modificar múltiples archivos
- **Después:** Agregar estado solo requiere:
  - Agregar enum a `ProviderState`
  - Agregar transición a `TRANSITIONS`
  - Registrar handler en StateMachine

### Principio Liskov Substitution (LSP)
- **Antes:** No había interfaces comunes
- **Después:** Todos los comandos son intercambiables (Command interface)

### Principio Interface Segregation (ISP)
- **Antes:** Handlers recibían parámetros que no usaban
- **Después:** Cada comando recibe solo lo que necesita

### Principio Dependency Inversion (DIP)
- **Antes:** Dependía de implementaciones concretas (Supabase)
- **Después:** Depende de interfaces (`IProviderRepository`)

---

## Verificación y Testing

### Tests Unitarios

```python
# tests/test_state_machine.py
def test_valid_transition():
    sm = ProviderStateMachine()
    assert sm.can_transition(ProviderState.AWAITING_CITY, ProviderState.AWAITING_NAME)

def test_invalid_transition():
    sm = ProviderStateMachine()
    assert not sm.can_transition(ProviderState.AWAITING_CITY, ProviderState.CONFIRM)

# tests/test_commands.py
async def test_register_provider_command():
    repo = MockProviderRepository()
    command = RegisterProviderCommand(repo, provider_data)
    result = await command.execute()
    assert result["id"]
    await command.undo()
    assert await repo.find_by_phone("0991234567") is None

# tests/test_saga.py
async def test_saga_rollback_on_failure():
    saga = ProviderRegistrationSaga()
    saga.add_command(FailingCommand())  # Falla a propósito
    with pytest.raises(SagaExecutionError):
        await saga.execute()
    # Verificar que se hizo rollback
    assert len(saga.executed_commands) == 0
```

### Tests de Integración

```python
# tests/integration/test_registration_flow.py
async def test_complete_registration_flow():
    # Simular flujo completo de registro
    flow = {}
    flow = await handle_awaiting_city(flow, "Cuenca")
    assert flow["city"] == "Cuenca"
    assert flow["state"] == "awaiting_name"

    flow = await handle_awaiting_name(flow, "Juan Pérez")
    assert flow["name"] == "Juan Pérez"

    # ... continuar hasta confirm

    # Verificar que se registró en BD
    provider = await provider_repo.find_by_phone("0991234567")
    assert provider is not None

    # Verificar que se subieron imágenes
    assert provider["dni_front_url"] is not None
```

### End-to-End Testing

1. **Flujo completo exitoso:**
   - Registrar proveedor desde WhatsApp
   - Verificar datos en BD
   - Verificar imágenes en Storage
   - Verificar que aparece en frontend

2. **Rollback en fallo de Storage:**
   - Simular fallo en upload de imágenes
   - Verificar que NO se registró en BD
   - Verificar logging de rollback

3. **Desconexión y reconexión:**
   - Simular desconexión a mitad de registro
   - Reconectar y continuar
   - Verificar que el flujo se mantiene

---

## Conclusión

El sistema actual **funciona para casos básicos** pero tiene **deudas técnicas significativas**:

1. **Bug crítico de rollback** (imágenes huérfanas si falla BD)
2. **Alto acoplamiento** (difícil de mantener y testear)
3. **Violaciones SOLID** (SRP, ISP, DIP)
4. **Edge cases no manejados** (desconexiones, timeouts, race conditions)

La arquitectura propuesta **State Machine + Command/Saga + Repository**:
- ✅ Soluciona problemas reales (rollback, acoplamiento, testabilidad)
- ✅ Aplica principios SOLID consistentemente
- ✅ Es proporcional al problema (no over-engineering)
- ✅ Se implementa en **5 fases con evitación de Breaking Changes**
- ✅ Cada fase agrega valor independiente y **puede revertirse fácilmente**

### Estrategia de Evitación de Breaking Changes

**Cada fase sigue 6 pasos rigurosos:**

1. **EXTRACT**: Crear nuevo código sin modificar existente
2. **UPDATE**: Agregar feature flags y migrar gradualmente
3. **CLEANUP**: Eliminar código obsoleto solo en Fase 5
4. **RECONSTRUIR CONTENEDORES**: `docker compose build && up`
5. **PROBAR**: Testing exhaustivo antes de continuar
6. **PUSH MAIN GITHUB**: Commit con mensaje claro

**Garantías:**
- ✅ **0 Breaking Changes** durante Fases 1-4
- ✅ Feature flags permiten rollback instantáneo
- ✅ Código original intacto hasta Fase 5
- ✅ Cada commit es production-ready
- ✅ Fase 5 solo limpia código ya validado

**Es la inversión correcta para la base de tu aplicación.**
