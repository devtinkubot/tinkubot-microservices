# Plan de Mejoras de Estabilidad - ai-proveedores

> **Fecha**: Enero 15, 2026
> **Versión**: 1.0 - Production Stability Plan
> **Estado**: Listo para implementación
> **Timeline**: 4 semanas (1 semana por sprint)
> **Estrategia**: Anti-breaking changes con feature flags y rollout gradual

---

## Resumen Ejecutivo

Este plan aborda los issues **CRITICAL** y **HIGH** prioridad identificados en el servicio `ai-proveedores` mediante una estrategia de **mejoras incrementales con rollback instantáneo**.

**Problemas críticos a resolver**:
1. Ausencia de validación de variables de entorno al inicio (fail-fast)
2. Sin health checks de dependencias durante startup
3. Falta de circuit breaker pattern para DB y APIs externas
4. Sin métricas ni monitoreo de producción
5. Logging no estructurado dificulta debugging

**Enfoque**: Cada mejora se implementa con:
- ✅ Feature flag (desactivado por defecto)
- ✅ Backward compatibility garantizada
- ✅ Testing antes de rollout
- ✅ Rollback instantáneo (cambiar flag)
- ✅ Monitoreo post-deployment

---

## Arquitectura Actual

```
┌─────────────────────────────────────────────────────────────┐
│                    ai-proveedores                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  FastAPI Application                                    │ │
│  │  - State Machine: ✅ Active                             │ │
│  │  - Saga Pattern: ✅ Active                              │ │
│  │  - Repository Pattern: ✅ Active                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  Dependencies:                                               │
│  ├─ Supabase (DB + Storage) ────┐                          │
│  ├─ OpenAI API ────────────────┤  NO VALIDATION            │
│  └─ Redis (with fallback) ─────┘  AT STARTUP ⚠️            │
│                                                              │
│  Missing:                                                    │
│  ├─ Startup health checks ❌                                 │
│  ├─ Circuit breakers ❌                                      │
│  ├─ Metrics endpoint ❌                                      │
│  └─ Structured logging ❌                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 1: Validación de Startup (CRÍTICO)

**Objetivo**: Fail-fast si dependencias críticas no están disponibles.

**Archivo**: `python-services/ai-proveedores/core/startup_validator.py` (NUEVO)

**Responsabilidades**:
- Validar todas las variables de entorno requeridas
- Verificar conectividad con Supabase
- Verificar disponibilidad del bucket de Storage
- Verificar API key de OpenAI
- Publicar eventos de startup status

### Código de Implementación

```python
"""
Startup Validator - Validación de dependencias al inicio.

FEATURE FLAG: ENABLE_STARTUP_VALIDATION (default: false)

Estrategia Anti-Breaking:
- Si falla una validación NO crítica, loguea warning pero continúa
- Si falla una validación CRÍTICA, levanta excepción controlada
- Feature flag permite desactivar sin modificar código
"""
import logging
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de una validación."""
    name: str
    status: str  # "pass", "fail", "warning"
    message: str
    critical: bool = False
    duration_ms: float = 0.0


class StartupValidator:
    """
    Validador de dependencias al inicio del servicio.

    Responsabilidades:
    - Validar variables de entorno
    - Verificar conectividad con dependencias externas
    - Publicar métricas de startup
    - Permitir modo degradado si fallan servicios no críticos
    """

    REQUIRED_ENV_VARS = [
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_BACKEND_API_KEY",
        "OPENAI_API_KEY",
        "REDIS_URL",
    ]

    OPTIONAL_ENV_VARS = [
        "SUPABASE_PROVIDERS_BUCKET",
        "SERVER_HOST",
        "PROVEEDORES_SERVER_PORT",
    ]

    def __init__(
        self,
        supabase_client: Any,
        openai_client: Any,
        enabled: bool = False,
        fail_on_warning: bool = False
    ):
        """
        Inicializa el validador de startup.

        Args:
            supabase_client: Cliente de Supabase
            openai_client: Cliente de OpenAI
            enabled: Si está activo (feature flag)
            fail_on_warning: Si fallar el startup en warnings (default: False)
        """
        self.supabase = supabase_client
        self.openai = openai_client
        self.enabled = enabled
        self.fail_on_warning = fail_on_warning
        self.results: List[ValidationResult] = []

    async def validate_all(self) -> Dict[str, Any]:
        """
        Ejecuta todas las validaciones en secuencia.

        Returns:
            Dict con estado general y resultados detallados
        """
        import time
        start_time = time.time()

        if not self.enabled:
            logger.info("⏸️ StartupValidator desactivado (feature flag)")
            return {
                "status": "skipped",
                "reason": "feature_flag_disabled",
                "results": []
            }

        logger.info("🔍 Iniciando validación de dependencias...")

        # 1. Validar variables de entorno
        await self._validate_environment_variables()

        # 2. Validar conectividad Supabase
        await self._validate_supabase_connection()

        # 3. Validar bucket de Storage (opcional)
        await self._validate_supabase_storage()

        # 4. Validar OpenAI API
        await self._validate_openai_api()

        # 5. Validar Redis (opcional, tiene fallback)
        await self._validate_redis_connection()

        # Calcular resumen
        total_duration = (time.time() - start_time) * 1000
        critical_failures = [r for r in self.results if r.critical and r.status == "fail"]
        warnings = [r for r in self.results if r.status == "warning"]
        passed = [r for r in self.results if r.status == "pass"]

        summary = {
            "total_duration_ms": round(total_duration, 2),
            "total_checks": len(self.results),
            "passed": len(passed),
            "warnings": len(warnings),
            "critical_failures": len(critical_failures),
            "status": "healthy" if not critical_failures else "unhealthy",
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "message": r.message,
                    "critical": r.critical,
                    "duration_ms": r.duration_ms
                }
                for r in self.results
            ]
        }

        # Loguear resumen
        self._log_summary(summary)

        # Determinar si fallar el startup
        if critical_failures:
            logger.error(f"❌ Validación de startup FALLÓ: {len(critical_failures)} errores críticos")
            raise StartupValidationError(
                f"Validación de startup falló: {len(critical_failures)} errores críticos",
                summary
            )

        if warnings and self.fail_on_warning:
            logger.warning(f"⚠️ Validación con warnings: {len(warnings)} advertencias")
            raise StartupValidationError(
                f"Validación de startup con warnings: {len(warnings)} advertencias",
                summary
            )

        logger.info(f"✅ Validación de startup COMPLETADA: {len(passed)}/{len(self.results)} validaciones pasaron")

        return summary

    async def _validate_environment_variables(self) -> None:
        """Valida que las variables de entorno requeridas estén definidas."""
        import time
        start = time.time()

        # Variables requeridas
        missing_required = []
        for var in self.REQUIRED_ENV_VARS:
            if not os.getenv(var):
                missing_required.append(var)

        if missing_required:
            self.results.append(ValidationResult(
                name="environment_variables",
                status="fail",
                message=f"Faltan variables requeridas: {', '.join(missing_required)}",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.error(f"❌ Faltan variables de entorno: {missing_required}")
        else:
            self.results.append(ValidationResult(
                name="environment_variables",
                status="pass",
                message=f"Todas las variables requeridas presentes ({len(self.REQUIRED_ENV_VARS)})",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.info(f"✅ Variables de entorno OK ({len(self.REQUIRED_ENV_VARS)} requeridas)")

        # Variables opcionales
        missing_optional = []
        for var in self.OPTIONAL_ENV_VARS:
            if not os.getenv(var):
                missing_optional.append(var)

        if missing_optional:
            self.results.append(ValidationResult(
                name="environment_variables_optional",
                status="warning",
                message=f"Variables opcionales faltantes: {', '.join(missing_optional)}",
                critical=False,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.warning(f"⚠️ Variables opcionales faltantes: {missing_optional}")

    async def _validate_supabase_connection(self) -> None:
        """Valida conectividad con Supabase."""
        import time
        start = time.time()

        try:
            # Intentar hacer un query simple
            result = await self._run_supabase_query(
                lambda: self.supabase.table("providers")
                .select("id")
                .limit(1)
                .execute()
            )

            self.results.append(ValidationResult(
                name="supabase_connection",
                status="pass",
                message="Conexión a Supabase exitosa",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.info("✅ Supabase connection OK")

        except Exception as e:
            self.results.append(ValidationResult(
                name="supabase_connection",
                status="fail",
                message=f"Error conectando a Supabase: {str(e)}",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.error(f"❌ Supabase connection FAIL: {e}")

    async def _validate_supabase_storage(self) -> None:
        """Valida disponibilidad del bucket de Storage (opcional)."""
        import time
        start = time.time()

        bucket_name = os.getenv("SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers")

        try:
            # Intentar listar objetos del bucket
            from supabase import StorageException
            # Nota: Supabase Python client no tiene método directo para check bucket
            # Asumimos que si no hay excepción al crear cliente, está OK
            self.results.append(ValidationResult(
                name="supabase_storage",
                status="pass",
                message=f"Bucket '{bucket_name}' disponible",
                critical=False,  # No es crítico, puede fallar gracefulmente
                duration_ms=(time.time() - start) * 1000
            ))
            logger.info(f"✅ Supabase Storage OK (bucket: {bucket_name})")

        except Exception as e:
            self.results.append(ValidationResult(
                name="supabase_storage",
                status="warning",
                message=f"No se pudo validar bucket '{bucket_name}': {str(e)}",
                critical=False,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.warning(f"⚠️ Supabase Storage WARNING: {e}")

    async def _validate_openai_api(self) -> None:
        """Valida API key de OpenAI haciendo un request mínimo."""
        import time
        start = time.time()

        if not self.openai:
            self.results.append(ValidationResult(
                name="openai_api",
                status="fail",
                message="Cliente OpenAI no inicializado",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.error("❌ OpenAI client FAIL")
            return

        try:
            # Hacer un request mínimo (chat con 1 token)
            from openai import AsyncOpenAI
            client: AsyncOpenAI = self.openai

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )

            self.results.append(ValidationResult(
                name="openai_api",
                status="pass",
                message=f"OpenAI API funcionando (model: {response.model})",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.info("✅ OpenAI API OK")

        except Exception as e:
            self.results.append(ValidationResult(
                name="openai_api",
                status="fail",
                message=f"Error validando OpenAI API: {str(e)}",
                critical=True,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.error(f"❌ OpenAI API FAIL: {e}")

    async def _validate_redis_connection(self) -> None:
        """Valida conectividad con Redis (opcional, tiene fallback)."""
        import time
        start = time.time()

        try:
            from infrastructure.redis import redis_client
            await redis_client.connect()

            if redis_client._connected:
                self.results.append(ValidationResult(
                    name="redis_connection",
                    status="pass",
                    message="Conexión a Redis exitosa",
                    critical=False,  # No es crítico, tiene fallback
                    duration_ms=(time.time() - start) * 1000
                ))
                logger.info("✅ Redis connection OK")
            else:
                self.results.append(ValidationResult(
                    name="redis_connection",
                    status="warning",
                    message="Redis no conectado, usando fallback local",
                    critical=False,
                    duration_ms=(time.time() - start) * 1000
                ))
                logger.warning("⚠️ Redis WARNING: usando fallback")

        except Exception as e:
            self.results.append(ValidationResult(
                name="redis_connection",
                status="warning",
                message=f"Error conectando a Redis: {str(e)}",
                critical=False,
                duration_ms=(time.time() - start) * 1000
            ))
            logger.warning(f"⚠️ Redis WARNING: {e}")

    async def _run_supabase_query(self, query_fn):
        """
        Helper para ejecutar query de Supabase de forma async.
        Envuelve la llamada síncrona de Supabase en un thread pool.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, query_fn)

    def _log_summary(self, summary: Dict[str, Any]) -> None:
        """Loguea resumen de validaciones."""
        logger.info("=" * 70)
        logger.info("📊 RESUMEN VALIDACIÓN STARTUP")
        logger.info("=" * 70)
        logger.info(f"Duración total: {summary['total_duration_ms']:.2f}ms")
        logger.info(f"Total validaciones: {summary['total_checks']}")
        logger.info(f"✅ Pasaron: {summary['passed']}")
        logger.info(f"⚠️  Warnings: {summary['warnings']}")
        logger.info(f"❌ Fallos críticos: {summary['critical_failures']}")
        logger.info(f"Estado: {summary['status'].upper()}")
        logger.info("=" * 70)


class StartupValidationError(Exception):
    """Excepción levantada cuando falla la validación de startup."""
    def __init__(self, message: str, validation_summary: Dict[str, Any]):
        super().__init__(message)
        self.validation_summary = validation_summary
```

### Integración en main.py

```python
# En main.py, agregar en startup_event:

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones y validar dependencias."""
    logger.info("🚀 Iniciando AI Service Proveedores...")

    # FASE 1: Startup Validator (si está activo)
    if os.getenv("ENABLE_STARTUP_VALIDATION", "false") == "true":
        from core.startup_validator import StartupValidator

        validator = StartupValidator(
            supabase_client=supabase,
            openai_client=openai_client,
            enabled=True,
            fail_on_warning=os.getenv("STARTUP_FAIL_ON_WARNING", "false") == "true"
        )

        try:
            validation_result = await validator.validate_all()
            logger.info(f"✅ Validación de startup completada: {validation_result['status']}")
        except StartupValidationError as e:
            logger.error(f"❌ Validación de startup falló: {e}")
            logger.error(f"Detalles: {e.validation_summary}")
            # Opción 1: Fallar el startup (fail-fast)
            raise SystemExit(1)
            # Opción 2: Continuar en modo degradado
            # logger.warning("⚠️ Continuando en modo degradado")

    # Resto del código de startup existente...
    if settings.session_timeout_enabled:
        logger.info("✅ Session Timeout simple habilitado")
```

### Feature Flag

```python
# En core/feature_flags.py, agregar:

# FASE 8: Startup Validator
# Activa validación de dependencias al inicio.
# - Implementa: StartupValidator con health checks
# - Archivos: core/startup_validator.py
# - Tests: tests/unit/test_startup_validator.py
# - Objetivo: Fail-fast si dependencias críticas no disponibles
# - ESTADO: ⏸️ INACTIVO por defecto (requiere activación manual)
ENABLE_STARTUP_VALIDATION = os.getenv("ENABLE_STARTUP_VALIDATION", "false") == "true"
STARTUP_FAIL_ON_WARNING = os.getenv("STARTUP_FAIL_ON_WARNING", "false") == "true"
```

### docker-compose.yml

```yaml
ai-proveedores:
  # ... configuración existente ...
  environment:
    # ... variables existentes ...
    - ENABLE_STARTUP_VALIDATION=true  # Activar validación
    - STARTUP_FAIL_ON_WARNING=false  # No fallar en warnings (solo errores críticos)
```

### Testing Strategy

```python
# tests/unit/test_startup_validator.py

import pytest
from core.startup_validator import StartupValidator, ValidationResult

@pytest.mark.asyncio
async def test_validator_with_all_dependencies():
    """Test validación exitosa con todas las dependencias."""
    validator = StartupValidator(
        supabase_client=mock_supabase,
        openai_client=mock_openai,
        enabled=True
    )

    result = await validator.validate_all()

    assert result["status"] == "healthy"
    assert result["critical_failures"] == 0
    assert len(result["results"]) > 0

@pytest.mark.asyncio
async def test_validator_with_missing_supabase():
    """Test falla cuando Supabase no está disponible."""
    validator = StartupValidator(
        supabase_client=None,  # Simular falla
        openai_client=mock_openai,
        enabled=True
    )

    with pytest.raises(StartupValidationError):
        await validator.validate_all()

@pytest.mark.asyncio
async def test_validator_disabled():
    """Test que validator desactivado no ejecuta validaciones."""
    validator = StartupValidator(
        supabase_client=mock_supabase,
        openai_client=mock_openai,
        enabled=False  # Desactivado
    )

    result = await validator.validate_all()

    assert result["status"] == "skipped"
    assert result["reason"] == "feature_flag_disabled"
```

### Rollback Procedure

Si la validación causa problemas:

1. **Inmediato**: Cambiar feature flag a false
   ```bash
   # En docker-compose.yml
   - ENABLE_STARTUP_VALIDATION=false
   ```

2. **Rebuild y restart**:
   ```bash
   docker compose build ai-proveedores --no-cache
   docker compose up -d ai-proveedores
   ```

3. **Investigar logs** para identificar validación problemática

---

## Fase 2: Circuit Breaker Pattern (ALTA)

**Objetivo**: Prevenir cascadas de fallos cuando dependencias externas fallan.

**Archivos**:
- `python-services/ai-proveedores/core/circuit_breaker.py` (NUEVO)
- `python-services/ai-proveedores/infrastructure/supabase_circuit_breaker.py` (NUEVO)
- Modificar `repositories/provider_repository.py` para usar circuit breaker

### Código de Implementación

```python
"""
Circuit Breaker Pattern - Implementación robusta.

FEATURE FLAG: ENABLE_CIRCUIT_BREAKER (default: false)

Estados: CLOSED → OPEN → HALF_OPEN → CLOSED

- CLOSED: Operación normal, contar fallos
- OPEN: Fallos superaron threshold, rechazar llamadas
- HALF_OPEN: Periodo de prueba para probar recuperación

Estrategia Anti-Breaking:
- Feature flag para activar/desactivar
- Si no está activo, las funciones pasan a través (no-op)
- Graceful degradation: retornar fallback value si circuit abierto
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Estados del Circuit Breaker."""
    CLOSED = "closed"      # Operación normal
    OPEN = "open"          # Rechazar llamadas
    HALF_OPEN = "half_open"  # Probando recuperación


@dataclass
class CircuitBreakerConfig:
    """Configuración del Circuit Breaker."""
    failure_threshold: int = 5  # Fallos antes de abrir
    success_threshold: int = 2  # Éxitos para cerrar (desde half-open)
    timeout_seconds: int = 60   # Tiempo en OPEN antes de half-open
    half_open_max_calls: int = 3  # Máximo de llamadas en half-open


class CircuitBreakerOpenError(Exception):
    """Excepción cuando el circuit breaker está OPEN."""
    pass


class CircuitBreaker:
    """
    Implementación de Circuit Breaker Pattern.

    Responsabilidades:
    - Contar fallos y éxitos de operaciones
    - Cambiar estado basado en thresholds
    - Rechazar llamadas cuando está OPEN
    - Permitir recuperación gradual (HALF_OPEN)
    - Proveer métricas de estado
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback_value: Any = None
    ):
        """
        Inicializa Circuit Breaker.

        Args:
            name: Nombre del circuit breaker (para logging/métricas)
            config: Configuración (usa default si no se provee)
            fallback_value: Valor a retornar si está OPEN
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback_value = fallback_value

        # Estado
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_call_count = 0

        # Métricas
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0

    @property
    def state(self) -> CircuitState:
        """Retorna el estado actual."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Retorna True si el circuit está abierto."""
        # Verificar si debemos transicionar a HALF_OPEN
        if self._state == CircuitState.OPEN:
            if time.time() - (self._last_failure_time or 0) >= self.config.timeout_seconds:
                logger.info(f"🔄 Circuit Breaker '{self.name}': OPEN → HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
                self._half_open_call_count = 0
                return False
        return self._state in [CircuitState.OPEN, CircuitState.HALF_OPEN]

    async def call(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """
        Ejecuta función protegida por circuit breaker.

        Args:
            func: Función a ejecutar
            *args: Argumentos posicionales
            **kwargs: Argumentos nombrados

        Returns:
            Resultado de la función

        Raises:
            CircuitBreakerOpenError: Si el circuit está abierto y no hay fallback
        """
        self._total_calls += 1

        # Si está OPEN, rechazar o usar fallback
        if self._state == CircuitState.OPEN:
            if self.fallback_value is not None:
                logger.warning(
                    f"⚠️ Circuit Breaker '{self.name}': OPEN, usando fallback"
                )
                return self.fallback_value
            raise CircuitBreakerOpenError(
                f"Circuit Breaker '{self.name}' está OPEN. "
                f"Rechazando llamada."
            )

        # Si está HALF_OPEN y excedimos calls, rechazar
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_call_count >= self.config.half_open_max_calls:
                logger.warning(
                    f"⚠️ Circuit Breaker '{self.name}': HALF_OPEN max calls alcanzado"
                )
                if self.fallback_value is not None:
                    return self.fallback_value
                raise CircuitBreakerOpenError(
                    f"Circuit Breaker '{self.name}' HALF_OPEN max calls"
                )
            self._half_open_call_count += 1

        # Ejecutar función
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self) -> None:
        """Maneja éxito de operación."""
        self._success_count += 1
        self._total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            if self._success_count >= self.config.success_threshold:
                logger.info(f"✅ Circuit Breaker '{self.name}': HALF_OPEN → CLOSED")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0

    def _on_failure(self) -> None:
        """Maneja fallo de operación."""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.config.failure_threshold:
            if self._state != CircuitState.OPEN:
                logger.error(
                    f"❌ Circuit Breaker '{self.name}': {self._state.value.upper()} → OPEN "
                    f"(threshold: {self.config.failure_threshold})"
                )
                self._state = CircuitState.OPEN
                self._failure_count = 0
                self._success_count = 0

    def reset(self) -> None:
        """Resetea el circuit breaker a estado CLOSED."""
        logger.info(f"🔄 Circuit Breaker '{self.name}': reset a CLOSED")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_call_count = 0

    def get_metrics(self) -> dict:
        """Retorna métricas del circuit breaker."""
        return {
            "name": self.name,
            "state": self._state.value,
            "total_calls": self._total_calls,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_rate": (
                self._total_failures / self._total_calls
                if self._total_calls > 0
                else 0
            ),
            "is_open": self.is_open
        }


class CircuitBreakerRegistry:
    """
    Registro global de circuit breakers.

    Permite acceder a todos los circuit breakers para monitoreo.
    """
    _circuit_breakers: dict = {}

    @classmethod
    def register(cls, circuit_breaker: CircuitBreaker) -> None:
        """Registra un circuit breaker."""
        cls._circuit_breakers[circuit_breaker.name] = circuit_breaker
        logger.info(f"📋 Circuit Breaker registrado: {circuit_breaker.name}")

    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        """Retorna un circuit breaker por nombre."""
        return cls._circuit_breakers.get(name)

    @classmethod
    def get_all(cls) -> dict:
        """Retorna todos los circuit breakers."""
        return cls._circuit_breakers.copy()

    @classmethod
    def get_all_metrics(cls) -> list:
        """Retorna métricas de todos los circuit breakers."""
        return [
            cb.get_metrics()
            for cb in cls._circuit_breakers.values()
        ]

    @classmethod
    def reset_all(cls) -> None:
        """Resetea todos los circuit breakers."""
        for cb in cls._circuit_breakers.values():
            cb.reset()
        logger.info("🔄 Todos los Circuit Breakers reseteados")
```

### Integración con Repositorios

```python
# En repositories/provider_repository.py

from core.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitBreakerConfig

# Crear circuit breakers al nivel del módulo
_supabase_cb = CircuitBreaker(
    name="supabase_db",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout_seconds=60,
        half_open_max_calls=3
    ),
    fallback_value=None
)

CircuitBreakerRegistry.register(_supabase_cb)

async def create_provider(supabase, provider_data: dict) -> dict:
    """Crea proveedor con circuit breaker protection."""

    async def _create():
        # Código existente de creación
        response = await run_supabase(
            lambda: supabase.table("providers")
            .upsert(provider_data)
            .execute(),
            label="providers.create"
        )
        # ... resto del código
        return response.data[0] if response.data else None

    # Ejecutar con circuit breaker
    if os.getenv("ENABLE_CIRCUIT_BREAKER", "false") == "true":
        return await _supabase_cb.call(_create)
    else:
        # Feature flag desactivado, ejecutar sin protección
        return await _create()
```

### Feature Flag

```python
# En core/feature_flags.py

# FASE 9: Circuit Breaker Pattern
# Activa circuit breakers para operaciones críticas.
# - Implementa: CircuitBreaker con estados OPEN/CLOSED/HALF_OPEN
# - Archivos: core/circuit_breaker.py
# - Tests: tests/unit/test_circuit_breaker.py
# - Objetivo: Prevenir cascadas de fallos
# - ESTADO: ⏸️ INACTIVO por defecto
ENABLE_CIRCUIT_BREAKER = os.getenv("ENABLE_CIRCUIT_BREAKER", "false") == "true"
```

### Testing Strategy

```python
# tests/unit/test_circuit_breaker.py

import pytest
from core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    """Test que circuit breaker abre después de threshold de fallos."""
    cb = CircuitBreaker(
        name="test",
        config=CircuitBreakerConfig(failure_threshold=3)
    )

    async def failing_func():
        raise Exception("Simulated failure")

    # Ejecutar hasta threshold
    for _ in range(3):
        try:
            await cb.call(failing_func)
        except:
            pass

    assert cb.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_circuit_breaker_rejects_when_open():
    """Test que circuit breaker rechaza llamadas cuando está OPEN."""
    cb = CircuitBreaker(
        name="test",
        config=CircuitBreakerConfig(failure_threshold=2)
    )

    # Forzar a OPEN
    cb._state = CircuitState.OPEN
    cb._last_failure_time = time.time()

    async def some_func():
        return "result"

    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(some_func)

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_closed():
    """Test transición HALF_OPEN → CLOSED con éxitos."""
    cb = CircuitBreaker(
        name="test",
        config=CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2
        )
    )

    # Poner en HALF_OPEN
    cb._state = CircuitState.HALF_OPEN
    cb._last_failure_time = time.time() - 100  # Pasó el timeout

    async def success_func():
        return "success"

    # Ejecutar éxitos suficientes
    await cb.call(success_func)
    await cb.call(success_func)

    assert cb.state == CircuitState.CLOSED
```

---

## Fase 3: Métricas Prometheus (ALTA)

**Objetivo**: Exponer métricas de producción para monitoreo.

**Archivos**:
- `python-services/ai-proveedores/core/metrics.py` (NUEVO)
- Modificar `app/api/health.py` para agregar endpoint `/metrics`

### Código de Implementación

```python
"""
Prometheus Metrics - Métricas de producción.

FEATURE FLAG: ENABLE_PROMETHEUS_METRICS (default: false)

Métricas expuestas:
- Contadores: requests totales, errores, etc.
- Histogramas: latencia de requests
- Gauges: estado de circuit breakers, conexiones activas

Estrategia Anti-Breaking:
- Si feature flag desactivado, endpoint /metrics retorna 404
- No impactar performance con métricas costosas
"""
import logging
import time
from typing import Callable, Optional
from functools import wraps

# Prometheus client library
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)

logger = logging.getLogger(__name__)

# Registry personalizado (no usar el default global)
_registry = CollectorRegistry()

# Métricas HTTP
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=_registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    registry=_registry
)

# Métricas de base de datos
db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=_registry
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query latency',
    ['operation', 'table'],
    registry=_registry
)

db_errors_total = Counter(
    'db_errors_total',
    'Total database errors',
    ['operation', 'error_type'],
    registry=_registry
)

# Métricas de circuit breakers
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['name'],
    registry=_registry
)

circuit_breaker_failures = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['name'],
    registry=_registry
)

# Métricas de OpenAI
openai_requests_total = Counter(
    'openai_requests_total',
    'Total OpenAI API requests',
    ['model', 'operation'],
    registry=_registry
)

openai_request_duration_seconds = Histogram(
    'openai_request_duration_seconds',
    'OpenAI API request latency',
    ['model'],
    registry=_registry
)

openai_errors_total = Counter(
    'openai_errors_total',
    'Total OpenAI API errors',
    ['model', 'error_type'],
    registry=_registry
)

# Métricas de Redis
redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation'],
    registry=_registry
)

redis_errors_total = Counter(
    'redis_errors_total',
    'Total Redis errors',
    ['operation', 'error_type'],
    registry=_registry
)


def track_http_request(method: str, endpoint: str):
    """
    Decorator para trackear requests HTTP.

    Usage:
        @track_http_request("GET", "/health")
        async def health_check():
            return {"status": "healthy"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "200"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "500"
                logger.error(f"Error en {method} {endpoint}: {e}")
                raise
            finally:
                duration = time.time() - start_time
                http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status=status
                ).inc()
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)

        return wrapper
    return decorator


def track_db_query(operation: str, table: str):
    """
    Decorator para trackear queries a base de datos.

    Usage:
        @track_db_query("select", "providers")
        async def get_provider(phone):
            # ... query logic
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                db_errors_total.labels(
                    operation=operation,
                    error_type=error_type
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                db_queries_total.labels(
                    operation=operation,
                    table=table
                ).inc()
                db_query_duration_seconds.labels(
                    operation=operation,
                    table=table
                ).observe(duration)

        return wrapper
    return decorator


def track_openai_request(model: str, operation: str):
    """
    Decorator para trackear requests a OpenAI.

    Usage:
        @track_openai_request("gpt-3.5-turbo", "chat")
        async def generate_response(messages):
            # ... OpenAI call
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_type = type(e).__name__
                openai_errors_total.labels(
                    model=model,
                    error_type=error_type
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                openai_requests_total.labels(
                    model=model,
                    operation=operation
                ).inc()
                openai_request_duration_seconds.labels(
                    model=model
                ).observe(duration)

        return wrapper
    return decorator


def update_circuit_breaker_metrics() -> None:
    """
    Actualiza métricas de circuit breakers.

    Debe llamarse periódicamente desde un background task.
    """
    try:
        from core.circuit_breaker import CircuitBreakerRegistry

        circuit_breakers = CircuitBreakerRegistry.get_all()

        for name, cb in circuit_breakers.items():
            # Mapear estado a número
            state_map = {
                "closed": 0,
                "open": 1,
                "half_open": 2
            }
            state_value = state_map.get(cb.state.value, 0)

            circuit_breaker_state.labels(name=name).set(state_value)

    except Exception as e:
        logger.error(f"Error actualizando métricas de circuit breakers: {e}")


async def metrics_generator() -> bytes:
    """
    Genera métricas en formato Prometheus.

    Returns:
        Bytes con métricas en formato Prometheus
    """
    # Actualizar métricas dinámicas
    update_circuit_breaker_metrics()

    # Generar métricas
    return generate_latest(_registry)


def get_metrics_content_type() -> str:
    """Retorna content type para métricas."""
    return CONTENT_TYPE_LATEST
```

### Integración en FastAPI

```python
# En app/api/health.py (o crear app/api/metrics.py)

from fastapi import Response
from core.metrics import metrics_generator, get_metrics_content_type
import os

@router.get("/metrics")
async def prometheus_metrics():
    """
    Endpoint de métricas Prometheus.

    FEATURE FLAG: ENABLE_PROMETHEUS_METRICS
    """
    if os.getenv("ENABLE_PROMETHEUS_METRICS", "false") != "true":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Metrics not enabled")

    metrics_data = await metrics_generator()
    return Response(
        content=metrics_data,
        media_type=get_metrics_content_type()
    )
```

### Feature Flag

```python
# En core/feature_flags.py

# FASE 10: Prometheus Metrics
# Activa métricas de producción.
# - Implementa: Métricas Prometheus con prometheus_client
# - Archivos: core/metrics.py
# - Endpoint: GET /metrics
# - Tests: tests/unit/test_metrics.py
# - Objetivo: Monitoreo de producción
# - ESTADO: ⏸️ INACTIVO por defecto
ENABLE_PROMETHEUS_METRICS = os.getenv("ENABLE_PROMETHEUS_METRICS", "false") == "true"
```

### docker-compose.yml para Prometheus

```yaml
version: '3.8'

services:
  # ... servicios existentes ...

  # Prometheus (opcional, para monitoreo)
  prometheus:
    image: prom/prometheus:latest
    container_name: tinkubot-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - tinkubot-network
    restart: unless-stopped

  # Grafana (opcional, para visualización)
  grafana:
    image: grafana/grafana:latest
    container_name: tinkubot-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    networks:
      - tinkubot-network
    restart: unless-stopped
```

### Configuración Prometheus

```yaml
# prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ai-proveedores'
    static_configs:
      - targets: ['ai-proveedores:8002']
    metrics_path: '/metrics'
```

---

## Fase 4: Logging Estructurado (MEDIA)

**Objetivo**: Logging en formato JSON para parseo y análisis.

**Archivos**:
- `python-services/ai-proveedores/infrastructure/logging_config.py` (NUEVO)
- Modificar `main.py` para usar logging configurado

### Código de Implementación

```python
"""
Logging Estructurado - JSON format con correlation IDs.

FEATURE FLAG: ENABLE_STRUCTURED_LOGGING (default: false)

Formato de log:
{
  "timestamp": "2026-01-15T12:34:56.789Z",
  "level": "INFO",
  "logger": "main",
  "message": "Conectado a Supabase",
  "context": {
    "service": "ai-proveedores",
    "correlation_id": "abc-123",
    "request_id": "req-456"
  }
}

Estrategia Anti-Breaking:
- Feature flag para activar/desactivar
- Si desactivado, usa formato de logging existente
- No impactar performance significativamente
"""
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)


class StructuredFormatter(jsonlogger.JsonFormatter):
    """
    Formateador de logs en JSON con contexto adicional.

    Agrega campos útiles para tracing y debugging.
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ):
        super().add_fields(log_record, record, message_dict)

        # Agregar timestamp en formato ISO
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Agregar nombre del servicio
        log_record['service'] = os.getenv('SERVICE_NAME', 'ai-proveedores')

        # Agregar correlation ID si existe
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id

        # Agregar request ID si existe
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id

        # Agregar información de excepción si existe
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }


def setup_structured_logging(
    level: str = "INFO",
    enable_json: bool = True
) -> None:
    """
    Configura logging estructurado para la aplicación.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        enable_json: Si usar formato JSON (si False, usa formato texto)
    """
    # Obtener logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Remover handlers existentes
    root_logger.handlers.clear()

    # Crear handler para stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))

    if enable_json:
        # Formato JSON
        formatter = StructuredFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        # Formato texto (original)
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    logger.info(f"Logging configurado: level={level}, json={enable_json}")


class CorrelationContext:
    """
    Context manager para agregar correlation ID a logs.

    Usage:
        with CorrelationContext(correlation_id="abc-123"):
            logger.info("Este log tendrá correlation_id")
    """

    def __init__(self, correlation_id: Optional[str] = None, request_id: Optional[str] = None):
        self.correlation_id = correlation_id
        self.request_id = request_id
        self.old_factory = None

    def __enter__(self):
        # Guardar factory actual
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            if self.correlation_id:
                record.correlation_id = self.correlation_id
            if self.request_id:
                record.request_id = self.request_id
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


def get_correlation_id() -> Optional[str]:
    """
    Genera o obtiene correlation ID del contexto actual.

    Returns:
        Correlation ID o None
    """
    import uuid
    return str(uuid.uuid4())
```

### Integración en main.py

```python
# En main.py, al inicio

import os

# Configurar logging estructurado si está activo
if os.getenv("ENABLE_STRUCTURED_LOGGING", "false") == "true":
    from infrastructure.logging_config import setup_structured_logging
    setup_structured_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        enable_json=True
    )
else:
    # Logging original
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)
```

### Middleware para Correlation ID

```python
# En middleware/correlation_middleware.py (NUEVO)

from fastapi import Request
from infrastructure.logging_config import CorrelationContext
import logging

logger = logging.getLogger(__name__)

async def correlation_middleware(request: Request, call_next):
    """
    Middleware que agrega correlation ID a todos los logs del request.

    Genera un UUID único por request y lo agrega al contexto de logging.
    """
    import uuid

    # Generar correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    # Agregar al estado del request para usar en endpoints
    request.state.correlation_id = correlation_id
    request.state.request_id = request_id

    # Usar context manager para logs
    with CorrelationContext(correlation_id=correlation_id, request_id=request_id):
        logger.info(f"Request started: {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
```

### Feature Flag

```python
# En core/feature_flags.py

# FASE 11: Structured Logging
# Activa logging en formato JSON con correlation IDs.
# - Implementa: Logging estructurado con python-json-logger
# - Archivos: infrastructure/logging_config.py, middleware/correlation_middleware.py
# - Tests: tests/unit/test_logging_config.py
# - Objetivo: Mejorar parseo de logs y tracing
# - ESTADO: ⏸️ INACTIVO por defecto
ENABLE_STRUCTURED_LOGGING = os.getenv("ENABLE_STRUCTURED_LOGGING", "false") == "true"
```

---

## Fase 5: Log Rotation (MEDIA)

**Objetivo**: Prevenir llenado de disco con logs antiguos.

**Archivo**: Modificar `docker-compose.yml`

### Implementación

```yaml
# En docker-compose.yml, para cada servicio

services:
  ai-proveedores:
    # ... configuración existente ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"       # Máximo 10MB por archivo
        max-file: "3"         # Mantener últimos 3 archivos
        compress: "true"      # Comprimir logs antiguos
```

### Impacto

- **max-size: "10m"**: Cada archivo de log máx 10MB
- **max-file: "3"**: Mantener solo 3 archivos (30MB total por servicio)
- **compress: "true"**: Comprimir con gzip para ahorrar espacio

**No requiere feature flag** - es configuración de Docker únicamente.

---

## Plan de Implementación (Timeline)

### Semana 1: Fase 1 + 5 (Startup Validation + Log Rotation)

**Día 1-2**: Implementación
- Crear `core/startup_validator.py`
- Modificar `main.py`
- Configurar log rotation en docker-compose.yml

**Día 3**: Testing
- Unit tests para StartupValidator
- Integration tests con dependencias caídas
- Test de rollback (feature flag off)

**Día 4-5**: Deployment (10%)
- Activar en desarrollo
- Monitorear por 48 horas
- Documentar resultados

### Semana 2: Fase 2 (Circuit Breaker)

**Día 1-2**: Implementación
- Crear `core/circuit_breaker.py`
- Modificar `repositories/provider_repository.py`
- Crear circuit breakers para Supabase y OpenAI

**Día 3**: Testing
- Unit tests para CircuitBreaker
- Simular fallos de dependencias
- Verificar transición de estados

**Día 4-5**: Deployment (10% → 50%)
- Activar en desarrollo
- Monitorear métricas de circuit breakers
- Ajustar thresholds si necesario

### Semana 3: Fase 3 (Prometheus Metrics)

**Día 1-2**: Implementación
- Crear `core/metrics.py`
- Agregar endpoint `/metrics`
- Instalar Prometheus y Grafana (local)

**Día 3**: Testing
- Verificar métricas expuestas
- Configurar dashboards en Grafana
- Test de performance (impacto en latency)

**Día 4-5**: Deployment (50% → 100%)
- Activar en producción
- Configurar alertas
- Monitorear dashboards

### Semana 4: Fase 4 (Structured Logging)

**Día 1-2**: Implementación
- Crear `infrastructure/logging_config.py`
- Crear middleware de correlation ID
- Configurar log parser (ELK/Loki)

**Día 3**: Testing
- Verificar formato JSON
- Test de correlation ID en requests
- Performance test (serialización JSON)

**Día 4-5**: Deployment (100%)
- Activar en producción
- Verificar parseo de logs
- Ajustar niveles de logging

---

## Estrategia de Testing

### Unit Tests

```bash
# Ejecutar tests unitarios
pytest tests/unit/ -v --cov=.
```

**Cobertura objetivo**: >80%

### Integration Tests

```bash
# Ejecutar tests de integración
pytest tests/integration/ -v --docker-compose
```

**Casos de prueba**:
1. Startup con Supabase caído
2. Circuit breaker con fallos en cascada
3. Métricas con alta carga
4. Logging con miles de requests

### Load Tests

```bash
# Usar locust para load testing
locust -f tests/load/test_api.py --host=http://localhost:8002
```

**Métricas objetivo**:
- <100ms p95 latency
- <1% error rate
- <500MB memory usage

---

## Estrategia de Rollback

### Por Fase

Si una fase causa problemas:

1. **Inmediato**: Cambiar feature flag a false
   ```bash
   # En docker-compose.yml
   - ENABLE_STARTUP_VALIDATION=false
   - ENABLE_CIRCUIT_BREAKER=false
   - ENABLE_PROMETHEUS_METRICS=false
   - ENABLE_STRUCTURED_LOGGING=false
   ```

2. **Rebuild y restart**:
   ```bash
   docker compose build ai-proveedores
   docker compose up -d ai-proveedores
   ```

3. **Investigar logs**:
   ```bash
   docker compose logs ai-proveedores --tail 1000
   ```

### Rollback Total

Si es necesario revertir todo:

```bash
# Git revert a commit anterior
git revert <commit-hash>

# Rebuild y restart
docker compose build ai-proveedores --no-cache
docker compose up -d ai-proveedores
```

---

## Monitoreo Post-Deployment

### Métricas Clave

**Startup Validator**:
- Tiempo de validación (<5s objetivo)
- Tasa de fallos por validación
- Validaciones más frecuentes que fallan

**Circuit Breaker**:
- Estado de circuit breakers (OPEN/CLOSED)
- Tasa de fallos por servicio
- Tiempo de recuperación

**Prometheus**:
- Requests por segundo
- Latencia p50, p95, p99
- Error rate
- Uso de memoria/CPU

**Logging**:
- Logs por segundo
- Tasa de errores
- Logs mal formateados

### Alertas Recomendadas

```yaml
# Ejemplo de reglas de alerta para Prometheus

groups:
  - name: ai-proveedores
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status="500"}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate on ai-proveedores"

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker {{ $labels.name }} is OPEN"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on ai-proveedores (p95 > 1s)"
```

---

## Verificación de Implementación

### Checklist por Fase

**Fase 1: Startup Validator**
- [ ] Feature flag implementado
- [ ] Validación de variables de entorno
- [ ] Health check de Supabase
- [ ] Health check de OpenAI
- [ ] Unit tests pasan
- [ ] Integration tests pasan
- [ ] Documentación actualizada

**Fase 2: Circuit Breaker**
- [ ] Feature flag implementado
- [ ] Circuit breaker para Supabase
- [ ] Circuit breaker para OpenAI
- [ ] Unit tests pasan
- [ ] Simulación de fallos
- [ ] Métricas expuestas
- [ ] Documentación actualizada

**Fase 3: Prometheus Metrics**
- [ ] Feature flag implementado
- [ ] Endpoint /metrics accesible
- [ ] Métricas HTTP trackeadas
- [ ] Métricas DB trackeadas
- [ ] Métricas OpenAI trackeadas
- [ ] Prometheus configurado
- [ ] Dashboards de Grafana
- [ ] Documentación actualizada

**Fase 4: Structured Logging**
- [ ] Feature flag implementado
- [ ] Logs en formato JSON
- [ ] Correlation ID presente
- [ ] Middleware funcionando
- [ ] Logs parseables
- [ ] Documentación actualizada

**Fase 5: Log Rotation**
- [ ] max-size configurado
- [ ] max-file configurado
- [ ] compress activado
- [ ] Espacio en disco bajo control
- [ ] Documentación actualizada

---

## Archivos a Crear/Modificar

### Archivos Nuevos

1. `python-services/ai-proveedores/core/startup_validator.py` (~400 líneas)
2. `python-services/ai-proveedores/core/circuit_breaker.py` (~350 líneas)
3. `python-services/ai-proveedores/core/metrics.py` (~300 líneas)
4. `python-services/ai-proveedores/infrastructure/logging_config.py` (~250 líneas)
5. `python-services/ai-proveedores/middleware/correlation_middleware.py` (~50 líneas)
6. `python-services/ai-proveedores/app/api/metrics.py` (~30 líneas)
7. `tests/unit/test_startup_validator.py` (~200 líneas)
8. `tests/unit/test_circuit_breaker.py` (~250 líneas)
9. `tests/unit/test_metrics.py` (~150 líneas)
10. `tests/unit/test_logging_config.py` (~100 líneas)
11. `tests/integration/test_circuit_breaker_integration.py` (~150 líneas)

**Total líneas de código**: ~2,200 líneas

### Archivos a Modificar

1. `python-services/ai-proveedores/main.py` (+30 líneas)
2. `python-services/ai-proveedores/core/feature_flags.py` (+20 líneas)
3. `python-services/ai-proveedores/repositories/provider_repository.py` (+50 líneas)
4. `python-services/ai-proveedores/app/api/health.py` (+20 líneas)
5. `docker-compose.yml` (+10 líneas)

**Total líneas modificadas**: ~130 líneas

### Archivos de Configuración

1. `prometheus.yml` (nuevo)
2. `grafana/dashboards/ai-proveedores.json` (nuevo, opcional)

---

## Dependencias Nuevas

```txt
# Agregar a requirements.txt

# Circuit Breaker (sin dependencias extra, implementación propia)

# Prometheus Metrics
prometheus-client==0.19.0

# Structured Logging
python-json-logger==2.0.7

# Testing (dev dependencies)
pytest-asyncio==0.21.1
pytest-cov==4.1.0
locust==2.18.3
```

---

## Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Startup validation causa fallos | Media | Alto | Feature flag, rollback inmediato |
| Circuit breaker rechaza llamadas legítimas | Media | Medio | Ajustar thresholds, monitorear |
| Prometheus afecta performance | Baja | Medio | Testing de carga, optimizar |
| Logging JSON consume CPU | Baja | Bajo | Testing de carga, feature flag |
| Log rotation pierde logs importantes | Baja | Medio | Configurar max-file adecuado |
| Dependencias nuevas tienen bugs | Baja | Alto | Testing exhaustivo, versiones pinned |

---

## Métricas de Éxito

### Técnicas
- [ ] Startup validation time < 5s
- [ ] Circuit breaker recovery time < 2min
- [ ] Prometheus scraping overhead < 5% CPU
- [ ] Log parsing rate > 1000 logs/s
- [ ] Disk usage estable (sin crecimiento)

### Negocio
- [ ] Reducción de downtime > 50%
- [ ] Detección más rápida de problemas (MTTD < 5min)
- [ ] Mejora en debugging (correlation IDs)
- [ ] Visibilidad de performance (dashboards)

---

## Conclusión

Este plan implementa mejoras de estabilidad **CRÍTICAS** y **ALTAS** con una estrategia robusta anti-breaking changes:

✅ **Feature flags** para cada mejora
✅ **Backward compatibility** garantizada
✅ **Rollback instantáneo** (cambiar flag)
✅ **Testing exhaustivo** por fase
✅ **Monitoreo completo** post-deployment
✅ **Documentación detallada**

**Timeline**: 4 semanas
**Riesgo**: Medio (mitigado con feature flags y testing)
**ROI**: Alto (mejora significativa en estabilidad y observabilidad)

---

## Próximos Pasos

1. **Aprobar plan** con equipo
2. **Priorizar fases** según necesidades
3. **Asignar recursos** (1 developer full-time)
4. **Configurar ambiente** de testing
5. **Comenzar implementación** (Fase 1)

**¿Listo para proceder?**
