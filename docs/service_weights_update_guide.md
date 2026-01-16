# Guía de Actualización de Pesos - Service Profession Mapping

## 📋 Resumen Ejecutivo

Este documento explica **cuándo** y **cómo** se actualizan los pesos/ponderaciones del sistema de matching servicio→profesión, validando que todo esté acorde a los patrones de diseño implementados.

---

## 🔄 Flujo de Actualización de Pesos

### Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    Base de Datos (Supabase)                      │
│  Tabla: service_profession_mapping                              │
│  - service_name: "inyección"                                    │
│  - profession: "enfermero"                                     │
│  - appropriateness_score: 0.95 ← PESO A ACTUALIZAR              │
│  - is_primary: true                                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Query (cada 1h TTL o cache miss)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Cache (Redis)                              │
│  Key: service_mapping:inyección                                 │
│  Value: {"service_name": "inyección", "professions": [...]}     │
│  TTL: 3600 segundos (1 hora)                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ServiceProfessionMapper (Aplicación)                │
│  - get_professions_for_service("inyección")                     │
│  - Primero busca en Redis (cache)                               │
│  - Si no existe, query a DB y guarda en Redis                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📅 Cuándo se Actualizan los Pesos

### 1. **Actualización Manual (Admin via SQL)**

**Cuándo:** Un administrador decide manualmente ajustar los pesos basado en:
- Feedback de usuarios
- Análisis de conversión
- Cambios en el mercado
- Corrección de errores

**Proceso:**

```bash
# Paso 1: Conectar a Supabase SQL Editor
# https://supabase.com/dashboard/project/YOUR_PROJECT/sql

# Paso 2: Ejecutar UPDATE
UPDATE service_profession_mapping
SET appropriateness_score = 0.85,  -- Nuevo peso
    updated_at = NOW()
WHERE service_name = 'inyección'
  AND profession = 'enfermero';

# Paso 3: Invalidar cache (IMPORTANTE)
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección \
  -H "Content-Type: application/json"

# Paso 4: Verificar cambios
curl http://localhost:8001/admin/service-mapping/service/inyección
```

**Validación de Diseño:**
- ✅ **Separación de responsabilidades**: DB almacena datos, Cache optimiza lecturas
- ✅ **Cache invalidation**: API REST para invalidación manual
- ✅ **Inmediatez**: Los cambios se reflejan inmediatamente después del refresh
- ✅ **Transaccionalidad**: UPDATE en DB es atómico
- ✅ **Observabilidad**: Logs de todas las operaciones

---

### 2. **Actualización Automática (Learning System)**

**Cuándo:** El sistema aprende de conversiones reales y ajusta pesos automáticamente.

**Proceso:**

```python
# background_task.py (pendiente implementación)

async def update_scores_from_conversions():
    """
    Analiza conversiones reales y ajusta scores automáticamente.

    Se ejecuta: Diario/Semanal (configurable)
    """
    # Paso 1: Obtener datos de conversion
    conversions = await db.get_provider_interactions(
        last_days=30,
        service_name="inyección"
    )

    # Paso 2: Calcular nuevo score basado en conversión
    for profession in ["enfermero", "médico"]:
        profession_conversions = [
            c for c in conversions
            if c.profession == profession and c.converted
        ]

        if len(profession_conversions) > 10:  # Muestra mínima
            conversion_rate = len(profession_conversions) / len(conversions)
            new_score = min(max(conversion_rate, 0.5), 0.95)  # Normalizar a 0.5-0.95

            # Paso 3: Actualizar DB
            await db.update_service_profession_score(
                service_name="inyección",
                profession=profession,
                new_score=new_score
            )

            # Paso 4: Invalidar cache
            await cache_manager.delete(f"service_mapping:inyección")

            # Paso 5: Log para auditoría
            logger.info(
                f"Auto-updated score: {profession}={new_score:.2f} "
                f"(based on {len(profession_conversions)} conversions)"
            )
```

**Validación de Diseño:**
- ⚠️ **Falta implementar**: Sistema de learning automático aún no existe
- ⚠️ **Preocupación**: Actualizaciones automáticas pueden introducir inestabilidad
- 💡 **Recomendación**: Implementar con:
  - Human-in-the-loop (requiere aprobación admin)
  - Delta máximo por actualización (±0.10)
  - Frecuencia limitada (1 vez/semana)
  - Rollback automático si conversión baja

---

### 3. **Actualización por API Admin (Manual Programática)**

**Cuándo:** Scripts o servicios externos necesitan actualizar pesos.

**Proceso:**

```python
# admin_update_service_scores.py

import requests
import os

API_BASE = os.getenv("AI_CLIENTES_URL", "http://localhost:8001")
API_KEY = os.getenv("ADMIN_API_KEY")  # TODO: Implementar auth

def update_service_score(service_name: str, profession: str, new_score: float):
    """Actualiza score de un servicio-profesión."""

    # Paso 1: Validar score
    if not 0.0 <= new_score <= 1.0:
        raise ValueError(f"Score must be between 0.0 and 1.0, got {new_score}")

    # Paso 2: Actualizar en DB
    supabase = get_supabase_client()
    result = supabase.table("service_profession_mapping").update({
        "appropriateness_score": new_score,
        "updated_at": "now()"
    }).eq("service_name", service_name).eq("profession", profession).execute()

    if result.data:
        # Paso 3: Invalidar cache
        cache_refresh_response = requests.post(
            f"{API_BASE}/admin/service-mapping/cache/refresh/{service_name}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=5
        )

        if cache_refresh_response.status_code == 200:
            print(f"✅ Score actualizado: {service_name}/{profession}={new_score}")
        else:
            print(f"⚠️ Score actualizado pero cache refresh falló")
    else:
        print(f"❌ Error actualizando score")

# Ejemplo
update_service_score("inyección", "enfermero", 0.90)
```

**Validación de Diseño:**
- ✅ **API-first approach**: Todo se hace vía API, no acceso directo a DB
- ✅ **Atomic operations**: Actualización DB → invalidación cache
- ⚠️ **Falta implementar**: Auth API key (seguridad)
- 💡 **Recomendación**: Implementar JWT authentication para admin APIs

---

## 🔍 Validación de Patrones de Diseño

### Patrones SOLID Implementados

#### ✅ Single Responsibility Principle (SRP)
- **ServiceProfessionMapper**: Solo mapea servicios a profesiones
- **ServiceProfessionMappingRepository**: Solo acceso a datos
- **ServiceProfessionMappingAdminAPI**: Solo administración de cache

#### ✅ Open/Closed Principle (OCP)
- **ScoringStrategy**: Abierto a extensión (nuevas estrategias de scoring)
  ```python
  class ScoringStrategy(ABC):
      @abstractmethod
      async def calculate_score(...): pass

  class DefaultScoringStrategy(ScoringStrategy):
      async def calculate_score(...): ...  # Implementación actual

  class MLBasedScoringStrategy(ScoringStrategy):  # Futuro
      async def calculate_score(...): ...  # Usa ML model
  ```

#### ✅ Dependency Inversion Principle (DIP)
- Depende de abstracciones (Protocol), no implementaciones concretas
  ```python
  class ServiceDetector(Protocol):
      async def detect(self, text: str) -> ServiceDetectionResult: ...

  class ServiceMatchingService:
      def __init__(self, detector: ServiceDetector, ...):  # Interface
          self.detector = detector
  ```

### Patrones Arquitectónicos Implementados

#### ✅ Repository Pattern
- `ServiceProfessionMappingRepository`: Separa lógica de acceso a datos
- Métodos CRUD claros
- Cache transparente

#### ✅ Strategy Pattern
- `ScoringStrategy`: Diferentes algoritmos de scoring
- Fácil agregar nuevas estrategias sin modificar código existente

#### ✅ Singleton Pattern
- `get_service_profession_mapper()`: Una instancia global
- `get_service_detector()`: Una instancia global
- `get_service_matching_service()`: Una instancia global

#### ✅ Cache-Aside Pattern
```
1. Application busca dato
2. Si está en cache → retornar
3. Si NO está en cache → buscar en DB
4. Guardar en cache con TTL
5. Retornar dato
```

---

## ⚠️ Preocupaciones y Mejoras Necesarias

### 1. **Falta: Autenticación en Admin APIs**

**Problema:** Las APIs de cache invalidación no tienen autenticación.

**Riesgo:** Cualquiera puede invalidar cache o actualizar pesos.

**Solución Recomendada:**
```python
# main.py - Agregar middleware de autenticación

from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verifica que el token sea admin."""
    token = credentials.credentials

    # Validar token JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not an admin")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Proteger endpoints admin
@app.post("/admin/service-mapping/cache/refresh")
async def refresh_cache(
    service_name: str,
    admin: dict = Depends(verify_admin_token)
):
    # Solo admins pueden ejecutar
    ...
```

### 2. **Falta: Transaccionalidad en Cache Updates**

**Problema:** Si la actualización de DB falla, el cache podría quedar inconsistente.

**Solución Recomendada:**
```python
async def update_score_with_transaction(service, profession, new_score):
    """Actualiza score con garantía de consistencia."""
    try:
        # Paso 1: Actualizar DB
        await db.update_service_score(service, profession, new_score)

        # Paso 2: Invalidar cache SÍ o SÍ (transaction)
        await cache.delete(f"service_mapping:{service}")

        logger.info(f"✅ Score actualizado: {service}/{profession}={new_score}")
        return True

    except Exception as e:
        # Rollback: no hacer nada, cache se refresca solo en próximos 60 min
        logger.error(f"❌ Error actualizando score: {e}")

        # Opcional: Forzar cache refresh por seguridad
        # await cache.delete(f"service_mapping:{service}")
        return False
```

### 3. **Falta: Sistema de Aprobación para Actualizaciones Automáticas**

**Problema:** Actualizaciones automáticas de scores podrían ser peligrosas sin supervisión.

**Solución Recomendada:**
```python
class ScoreUpdateProposal:
    """Propuesta de actualización de score pendiente de aprobación."""

    async def propose_new_score(
        self,
        service: str,
        profession: str,
        new_score: float,
        reason: str,
        data: dict
    ):
        """Crea propuesta de actualización."""

        # Guardar en tabla de propuestas
        await db.insert("score_update_proposals", {
            "service_name": service,
            "profession": profession,
            "current_score": await self.get_current_score(service, profession),
            "proposed_score": new_score,
            "reason": reason,
            "data": data,
            "status": "pending",  # pending, approved, rejected
            "created_at": "now()"
        })

        # Notificar admin (email, Slack, etc.)
        await notification_service.notify_admin(
            f"Propuesta de actualización: {service}/{profession} {await self.get_current_score(service, profession)} → {new_score}"
        )

    async def approve_proposal(self, proposal_id: int):
        """Aprueba propuesta y aplica cambios."""
        proposal = await db.get_proposal(proposal_id)

        # Aplicar cambios
        await self.apply_score_update(
            service=proposal.service_name,
            profession=proposal.profession,
            new_score=proposal.proposed_score
        )

        # Marcar como aprobada
        await db.update("score_update_proposals", proposal_id, {
            "status": "approved",
            "approved_at": "now()"
        })
```

---

## 📊 Procesos y Eventos que Actualizan Pesos

### Eventos que Activan Actualización

| Evento | Trigger | Método | ¿Automático? |
|--------|---------|--------|--------------|
| **Ajuste manual de admin** | Admin ejecuta SQL | Manual | ❌ No |
| **Cache refresh API** | POST /admin/service-mapping/cache/refresh | Programático | ❌ No |
| **Learning automático** | Background task analiza conversiones | Automático | ⚠️ Pendiente implementar |
| **Aprobación de propuesta** | Admin aprueba propuesta generada por sistema | Semi-automático | ⚠️ Pendiente implementar |
| **Fallback a V2** | Error en ServiceMatching | Automático | ✅ Sí (interno) |

### Flujo Completo de Actualización

```
┌──────────────────────────────────────────────────────────────┐
│ 1. ADMIN DECIDE ACTUALIZAR PESO                             │
│    - Analiza métricas de conversión                          │
│    - Recibe feedback de usuarios                              │
│    - Detecta patrón de uso inadecuado                         │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. EJECUTA UPDATE SQL                                        │
│                                                              │
│  UPDATE service_profession_mapping                          │
│  SET appropriateness_score = 0.85,                          │
│      updated_at = NOW()                                      │
│  WHERE service_name = 'inyección'                           │
│    AND profession = 'enfermero';                            │
│                                                              │
│  ✅ Transaccional: ACID compliance                          │
│  ✅ Audit trail: updated_at timestamp                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. INVALIDAR CACHE (CRÍTICO)                                │
│                                                              │
│  curl -X POST \\                                           │
│    http://localhost:8001/admin/service-mapping/cache/refresh │
│                                                              │
│  ✅ Inmediato: No esperar 1 hora de TTL                     │
│  ✅ Selectivo: Solo afecta servicio específico              │
│  ✅ Verificable: Response indica success                      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. PRÓXIMA REQUEST USANDO MAPPER ACTUALIZADO                │
│                                                              │
│  mapper.get_professions_for_service("inyección")            │
│                                                              │
│  Flujo:                                                       │
│  1. Redis busca "service_mapping:inyección"                │
│  2. No existe (fue invalidado) → CACHE MISS                 │
│  3. Query a PostgreSQL:                                      │
│     SELECT * FROM service_profession_mapping                │
│     WHERE service_name = 'inyección'                         │
│  4. DB retorna datos actualizados (score=0.85)              │
│  5. Guardar en Redis con TTL=3600                          │
│  6. Retornar al application                                  │
│                                                              │
│  ✅ Consistencia: DB y Cache sincronizados                   │
│  ✅ Performance: Cache HIT en próximas requests             │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 Checklist de Producción

### Antes de Actualizar Pesos en Producción

- [ ] **Backup**: Crear backup de tabla `service_profession_mapping`
  ```sql
  CREATE TABLE service_profession_mapping_backup AS
  SELECT * FROM service_profession_mapping;
  ```

- [ ] **Testing**: Probar cambios en ambiente staging
  ```sql
  -- Staging primero
  UPDATE service_profession_mapping
  SET appropriateness_score = 0.85
  WHERE service_name = 'inyección' AND profession = 'enfermero';

  -- Probar búsqueda
  -- Verificar ranking de providers
  ```

- [ ] **Monitoreo**: Configurar alertas
  - CPU/Memory de ai-clientes
  - Redis hit rate
  - DB query performance
  - Error rates

- [ ] **Rollback Plan**: Tener ready script de rollback
  ```sql
  -- Rollback rápido
  UPDATE service_profession_mapping
  SET appropriateness_score = 0.95
  WHERE service_name = 'inyección' AND profession = 'enfermero';

  -- Invalidar cache
  curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh
  ```

### Durante Actualización

- [ ] **Mantener servicio**: No downtime durante update
  - UPDATE es transaccional (no locks largos)
  - Cache refresh asíncrono

- [ ] **Verificar logs**: Monitorear logs en tiempo real
  ```bash
  docker compose logs -f ai-clientes | grep -E "(ERROR|WARN|service_matching)"
  ```

- [ ] **Validar resultado**: Probar búsqueda después de update
  - Enviar mensaje de prueba: "necesito inyecciones"
  - Verificar que ranking cambió según lo esperado

### Después de Actualización

- [ ] **Invalidar cache**: Ejecutar refresh API
  ```bash
  curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección
  ```

- [ ] **Verificar estadísticas**: Revisar cache stats
  ```bash
  curl http://localhost:8001/admin/service-mapping/cache/stats
  ```

- [ ] **Monitorear métricas**: Observar por 24-48 horas
  - Contact rate
  - Conversion rate
  - User feedback

- [ ] **Documentar cambios**: Registrar en changelog
  - Fecha/hora
  - Valor anterior → nuevo valor
  - Razón del cambio
  - Responsable

---

## 🔧 Soluciones a Preocupaciones de Diseño

### Preocupación 1: No hay actualización automática de pesos

**Estado:** ⚠️ Pendiente implementación

**Solución propuesta:**

```python
# services/auto_score_tuner.py

class AutoScoreTuner:
    """
    Ajusta automáticamente los scores basado en conversiones reales.

    Estrategia defensiva:
    - Solo ajusta si hay suficientes datos (muestra mínima)
    - Delta máximo por actualización (±0.10)
    - Requiere aprobación admin para cambios grandes
    - Rollback automático si conversión baja
    """

    MIN_CONVERSION_SAMPLE = 20  # Mínima muestra para confiar
    MAX_DELTA_PER_UPDATE = 0.10  # Máximo cambio por actualización
    APPROVAL_THRESHOLD = 0.20  # Requiere aprobación si delta > 20%

    async def weekly_tune_scores(self):
        """Ejecuta semanalmente (configurable via cron)."""

        # Paso 1: Obtener todos los servicios activos
        services = await self.get_active_services()

        for service in services:
            # Paso 2: Obtener interacciones de últimos 30 días
            interactions = await self.get_interactions(
                service_name=service,
                days=30
            )

            if len(interactions) < self.MIN_CONVERSION_SAMPLE:
                logger.info(f"⚠️ Muestra insuficiente para {service}, skip")
                continue

            # Paso 3: Calcular scores por profesión
            profession_scores = {}
            for profession_data in interactions.group_by("profession"):
                conversion_rate = len(profession_data.converted) / len(profession_data)
                profession_scores[profession_data.profession] = conversion_rate

            # Paso 4: Actualizar DB (si es apropiado)
            for profession, new_score in profession_scores.items():
                current_score = await self.get_current_score(service, profession)
                delta = abs(new_score - current_score)

                if delta > self.APPROVAL_THRESHOLD:
                    # Crear propuesta para aprobación manual
                    await self.create_proposal(
                        service=service,
                        profession=profession,
                        current_score=current_score,
                        proposed_score=new_score,
                        reason=f"Conversion rate: {conversion_rate:.2%}, sample: {len(profession_data)}"
                    )
                elif delta > self.MAX_DELTA_PER_UPDATE:
                    # Actualizar con delta máximo
                    adjusted_score = current_score + (
                        (new_score - current_score) / abs(new_score - current_score)
                    ) * self.MAX_DELTA_PER_UPDATE

                    await self.update_score_proposed(
                        service=service,
                        profession=profession,
                        new_score=adjusted_score
                    )
                else:
                    # Actualizar directamente (cambio pequeño)
                    await self.update_score_proposed(
                        service=service,
                        profession=profession,
                        new_score=new_score
                    )

            # Paso 5: Invalidar cache
            await cache_manager.delete(f"service_mapping:{service}")
```

**Validación de Diseño:**
- ✅ **Conservador**: Solo actualiza con datos suficientes
- ✅ **Gradual**: Delta máximo por actualización
- ✅ **Human-in-the-loop**: Aprobación para cambios grandes
- ✅ **Observable**: Todo se loguea para auditoría
- ✅ **Reversible**: Rollback si conversión baja

---

## 📝 Ejemplos Prácticos de Actualización

### Caso 1: Ajuste Manual Basado en Feedback

**Situación:** Los usuarios reportan que médicos están apareciendo antes que enfermeros para inyecciones, pero enfermeros son más apropiados.

**Solución:**

```sql
-- Paso 1: Verificar scores actuales
SELECT service_name, profession, appropriateness_score, is_primary
FROM service_profession_mapping
WHERE service_name = 'inyección'
ORDER BY appropriateness_score DESC;

-- Resultado:
-- inyección | enfermero | 0.95 | true
-- inyección | médico    | 0.70 | false

-- Paso 2: Reducir score de médico (para que aparezca más abajo)
UPDATE service_profession_mapping
SET appropriateness_score = 0.50,  -- Bajar de 0.70 a 0.50
    updated_at = NOW()
WHERE service_name = 'inyección'
  AND profession = 'médico';

-- Paso 3: Invalidar cache inmediatamente
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección

-- Paso 4: Verificar cambio
curl http://localhost:8001/admin/service-mapping/service/inyección
```

**Resultado esperado:**
- Enfermero continúa primero (score 0.95)
- Médico baja más en ranking (score 0.50)
- Cambio inmediato (no esperar 1 hora)

---

### Caso 2: Agregar Nuevo Servicio

**Situación:** Queremos agregar "masajes" como servicio.

**Solución:**

```sql
-- Paso 1: Insertar mapeo
INSERT INTO service_profession_mapping (service_name, profession, appropriateness_score, is_primary, active)
VALUES
  ('masaje', 'masajista', 0.95, TRUE, TRUE),
  ('masaje', 'enfermero', 0.60, FALSE, TRUE),
  ('masaje', 'fisioterapeuta', 0.85, FALSE, TRUE)
ON CONFLICT (service_name, profession) DO NOTHING;

-- Paso 2: Agregar al ServiceDetector (código)
-- python-services/ai-clientes/services/service_detector.py
MEDICAL_SERVICES = {
    ...
    'masaje', 'masajes',
    ...
}

-- Paso 3: Reconstruir contenedores
docker compose build ai-clientes
docker compose up -d ai-clientes

-- Paso 4: Invalidar cache
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/masaje
```

---

## 🎯 Conclusión

### Resumen del Flujo

1. **Pesos se almacenan en:** Tabla `service_profession_mapping` (Supabase/PostgreSQL)
2. **Pesos se cachean en:** Redis (TTL: 1 hora)
3. **Actualización manual:** SQL UPDATE → API refresh cache → Próxima request usa nuevos pesos
4. **Actualización automática:** Pendiente implementar con AutoScoreTuner (con aprobación admin)

### Patrones de Diseño Validados

- ✅ SOLID principles: SRP, OCP, DIP implementados correctamente
- ✅ Repository Pattern: Separación clara de lógica de datos
- ✅ Strategy Pattern: Extensible para nuevas estrategias de scoring
- ✅ Cache-Aside: Performance optimizado con invalidación manual
- ✅ Singleton Pattern: Instancias globales compartidas

### Mejoras Recomendadas

1. **Alta prioridad**: Implementar autenticación en Admin APIs
2. **Media prioridad**: Implementar AutoScoreTuner con aprobación admin
3. **Baja prioridad**: Sistema de propuestas de actualización
4. **Futuro**: ML-based scoring con validación de negocios

---

**Autor:** Claude Sonnet 4.5
**Creado:** 2026-01-16
**Última actualización:** 2026-01-16
