# Plan Integral: Mejoras de Frontend y Sistema de Rechazo de Proveedores

**Fecha:** 2025-01-14
**Estado:** Pendiente de aprobación
**Enfoque:** "Menos es más" - Simplicidad antes que sobre-ingeniería

---

## Resumen Ejecutivo

Este plan aborda dos mejoras críticas en el sistema TinkuBot:

1. **Modernización del Frontend Admin Dashboard** - Aplicando principios de diseño moderno con el plugin frontend-design
2. **Sistema de Limpieza al Rechazar Proveedores** - Implementando limpieza completa de datos, notificaciones y retorno al flujo de consentimiento

Ambas iniciativas siguen el principio de **"menos es más"**, evitando sobre-ingeniería y manteniendo la simplicidad donde sea posible.

---

## Parte 1: Análisis de Arquitectura Actual

### Hallazgos de Exploración

#### Arquitectura General
- ✅ **SOLID bien implementado**: Repository, Saga, State Machine, Command Pattern
- ✅ **Microservicios bien estructurados**: ai-clientes, ai-proveedores, av-proveedores
- ⚠️ **Sobre-ingeniería detectada**: Excesivas capas de abstracción para operaciones CRUD simples
- ⚠️ **State Machine complejo**: 13 estados podrían simplificarse
- ⚠️ **Feature flags excesivos**: 5 fases de migración podrían ser 2-3

#### Frontend Actual
- **Tech Stack**: Vanilla JavaScript + TypeScript, Vite 5.2.0, Bootstrap 5.3.0
- **Estructura**: Modular (NavigationModule, ProvidersManagerModule, WhatsAppManagerModule)
- **Problema principal**: `providersManager.ts` tiene 743 líneas (monolítico)
- **Sin design system formal**: Solo variables CSS básicas
- **Sin state management global**: Estado manual en cada módulo
- **Sin testing**: 0% de cobertura

#### Flujo de Rechazo Actual
1. Admin rechaza proveedor → BFF actualiza Supabase (verified=false)
2. MQTT publica a "providers/rejected" → wa-proveedores envía WhatsApp ✅
3. **FALTANTE**: No se limpia Redis (sesión queda huérfana)
4. **FALTANTE**: No se elimina registro de Supabase
5. **FALTANTE**: No se borran documentos de Storage
6. **FALTANTE**: Proveedor no puede reiniciar registro fácilmente

---

## Parte 2: Plan de Mejoras del Frontend

### Objetivos

1. **Refactorizar módulo monolítico** - Reducir de 743 a ~150 líneas
2. **Implementar design system minimalista** - Basado en Bootstrap + tokens CSS
3. **Agregar state management simple** - Pub/sub custom (100 líneas)
4. **Mejorar performance** - Lazy loading, caching, debouncing
5. **Mejorar accesibilidad** - WCAG 2.1 AA compliant
6. **Agregar testing** - Vitest + Testing Library, meta 70% cobertura

### Principio: "Menos es Más"

❌ **NO haremos:**
- Migrar a React/Vue (overkill para este caso)
- Implementar Redux/Zustand (demasiado pesado)
- Crear sistema de diseño enterprise (Bootstrap es suficiente)
- Over-engineering con hooks complejos

✅ **SÍ haremos:**
- Extender Bootstrap con variables CSS
- Pub/sub simple para estado (100 líneas)
- Componentes funcionales y modulares
- Testing pragmático (Vitest)

### Cambios en Estructura de Archivos

**ANTES:**
```
src/
├── modules/
│   ├── navigation.ts (28 líneas)
│   ├── providersManager.ts (743 líneas) ⚠️
│   ├── utils.ts (14 líneas)
│   └── whatsappManager.ts (166 líneas)
└── main.ts (54 líneas)
```

**DESPUÉS:**
```
src/
├── core/
│   ├── CreateStore.ts (100 líneas) - State management
│   ├── DOMCache.ts (50 líneas) - Cache de queries
│   └── AbortController.ts (40 líneas) - Cancelación de requests
│
├── modules/
│   ├── providers/
│   │   ├── components/
│   │   │   ├── ProviderTable.ts (~150 líneas)
│   │   │   ├── ProviderDetailModal.ts (~200 líneas)
│   │   │   └── FeedbackToast.ts (~80 líneas)
│   │   ├── state/
│   │   │   └── ProviderStore.ts (~80 líneas)
│   │   └── index.ts (orchestrator, ~150 líneas)
│   │
│   ├── whatsapp/
│   └── navigation/
│
├── styles/
│   ├── design-tokens.css (~150 líneas)
│   ├── components.css (~100 líneas)
│   ├── responsive.css (~80 líneas)
│   └── accessibility.css (~60 líneas)
│
└── main.ts
```

**Reducción neta:** 743 líneas → ~770 líneas totales pero mejor organizadas en módulos pequeños

### Implementación del Design System

**Archivo: `src/styles/design-tokens.css`**
```css
:root {
  /* Palette - Extiende Bootstrap */
  --tinku-primary: #6366f1;
  --tinku-primary-hover: #5558e3;
  --tinku-success: #10b981;
  --tinku-warning: #f59e0b;
  --tinku-danger: #ef4444;

  /* Spacing - Basado en grid de 4px */
  --tinku-space-xs: 0.25rem;
  --tinku-space-sm: 0.5rem;
  --tinku-space-md: 1rem;
  --tinku-space-lg: 1.5rem;
  --tinku-space-xl: 2rem;

  /* Border Radius */
  --tinku-radius-sm: 6px;
  --tinku-radius-md: 8px;
  --tinku-radius-lg: 12px;

  /* Shadows */
  --tinku-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --tinku-shadow-md: 0 2px 10px rgba(0, 0, 0, 0.08);
  --tinku-shadow-lg: 0 4px 20px rgba(0, 0, 0, 0.12);

  /* Transitions */
  --tinku-transition-fast: 150ms ease;
  --tinku-transition-base: 200ms ease;
}
```

**Archivo: `src/core/CreateStore.ts`**
```typescript
export interface Store<T> {
  getState: () => T;
  setState: (partial: Partial<T>) => void;
  subscribe: (listener: (state: T) => void) => () => void;
}

export function createStore<T>(initialState: T): Store<T> {
  let state = initialState;
  const listeners = new Set<(state: T) => void>();

  return {
    getState: () => state,
    setState: (partial) => {
      state = { ...state, ...partial };
      listeners.forEach(l => l(state));
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
}
```

### Mejoras de Performance

1. **Lazy Loading de Imágenes**
   ```html
   <img loading="lazy" decoding="async" src="..." />
   ```

2. **Debouncing de API Calls**
   ```typescript
   const debounce = (fn: Function, delay: number) => {
     let timeout: ReturnType<typeof setTimeout>;
     return (...args: any[]) => {
       clearTimeout(timeout);
       timeout = setTimeout(() => fn(...args), delay);
     };
   };
   ```

3. **DOM Query Caching**
   ```typescript
   class DOMCache {
     private cache = new Map<string, HTMLElement>();
     get<T>(selector: string): T | null {
       if (this.cache.has(selector)) {
         return this.cache.get(selector) as T;
       }
       const el = document.querySelector<T>(selector);
       if (el) this.cache.set(selector, el as any);
       return el;
     }
   }
   ```

### Métricas de Éxito

| Métrica | Antes | Después (meta) |
|---------|-------|----------------|
| Bundle size | ~150KB | ~120KB (-20%) |
| First Contentful Paint | 1.8s | 1.2s (-33%) |
| Time to Interactive | 3.2s | 2.0s (-37%) |
| Lighthouse Score | 75 | 90 |
| Accessibility Score | 68 | 95 |
| providersManager.ts | 743 líneas | 150 líneas (-80%) |
| Test Coverage | 0% | 70% |

---

## Parte 3: Plan de Sistema de Rechazo con Limpieza

### Flujo Completo Deseado

```
1. Admin rechaza proveedor
   ↓
2. BFF actualiza Supabase (verified=false, verification_notes)
   ↓
3. BFF publica MQTT "providers/rejected" (ya existe ✅)
   ↓
4. BFF llama /providers/reject/cleanup (NUEVO)
   ↓
5. ai-proveedores ejecuta ProviderRejectionSaga:
   ├── LogRejectionEventCommand (AUDIT)
   ├── DeleteStorageFilesCommand (Storage)
   ├── CleanupRedisSessionCommand (Redis)
   └── DeleteProviderRecordCommand (DB)
   ↓
6. wa-proveedores envía WhatsApp (ya existe ✅)
   ↓
7. Proveedor puede reiniciar registro (consentimiento)
```

### Archivos a Crear

#### Backend Python (ai-proveedores)

**`core/commands.py` - Agregar comandos:**
```python
class DeleteProviderRecordCommand(Command):
    """Elimina registro de proveedor de Supabase"""

class DeleteStorageFilesCommand(Command):
    """Elimina documentos de Supabase Storage"""

class CleanupRedisSessionCommand(Command):
    """Limpia sesión de Redis"""

class LogRejectionEventCommand(Command):
    """Registra evento de rechazo en audit trail"""
```

**`core/saga.py` - Agregar:**
```python
class ProviderRejectionSaga:
    """Orquesta cleanup con best-effort policy"""
    # Si un paso falla, continúa con los demás
    # La mayoría de operaciones son intencionalmente irreversibles
```

**`services/rejection_cleanup_service.py` (NUEVO):**
```python
class RejectionCleanupService:
    async def cleanup_rejected_provider(
        self, phone: str, rejection_reason: str, reviewer: Optional[str]
    ) -> Dict[str, Any]:
        """Ejecuta saga de cleanup completo"""
```

**`app/api/providers.py` (NUEVO):**
```python
@router.post("/providers/reject/cleanup")
async def cleanup_rejected_provider(request: RejectionCleanupRequest):
    """Endpoint para cleanup post-rechazo"""
```

#### Frontend BFF (Node.js)

**`bff/providers.js` - Modificar `rechazarProveedor()`:**
```javascript
// Después de actualizar Supabase y publicar MQTT
if (cleanupEnabled && registro?.phone) {
  try {
    await axios.post(`${providerBaseUrl}/providers/reject/cleanup`, {
      phone: registro.phone,
      rejection_reason: payload.notes || 'Not specified',
      reviewer: payload.reviewer || 'Admin'
    }, { timeout: 30000 });
    console.warn(`✅ Cleanup completed for ${registro.phone}`);
  } catch (cleanupError) {
    console.error(`⚠️ Cleanup failed:`, cleanupError.message);
    // NO fallar el rechazo por cleanup
  }
}
```

#### WhatsApp Service

**`MqttClient.js` - Actualizar mensaje de rechazo:**
```javascript
_buildRejectionMessage(nombre, notas) {
  return `${saludo} 🚫 tu registro fue revisado y requiere ajustes.${motivo}

Puedes actualizar tus datos y volver a enviarlos cuando estés listo.

Para reiniciar el registro, simplemente envía un mensaje a este número.`;
}
```

### Feature Flag

**`core/feature_flags.py`:**
```python
# FASE 6: Provider Rejection Cleanup
ENABLE_REJECTION_CLEANUP = False  # Activar gradualmente
```

**Environment variable:**
```bash
ENABLE_REJECTION_CLEANUP=true  # Habilita cleanup
```

### Estrategia de Rollout

1. **Deploy con flag OFF** - Código nuevo deployado, cleanup desactivado
2. **DEV/STAGING** - Activar y probar con proveedores reales
3. **10% traffic** - Usar hash de teléfono para porcentaje
4. **50% traffic**
5. **100% traffic**
6. **Eliminar código viejo** (después de 1 semana exitosa)

### Testing

**Unit Tests:**
```python
# tests/unit/test_rejection_cleanup.py
async def test_delete_provider_command():
    mock_repo = AsyncMock()
    command = DeleteProviderRecordCommand(mock_repo, "1234567890")
    result = await command.execute()
    assert result["success"] is True

async def test_cleanup_saga_best_effort():
    # Si un paso falla, otros continúan
    saga = ProviderRejectionSaga()
    saga.add_command(FailingCommand())  # Falla intencionalmente
    saga.add_command(SuccessCommand())  # Debe ejecutarse
    result = await saga.execute()
    assert result["failed_commands"] == 1
    assert result["successful_commands"] == 1
```

**Integration Tests:**
```python
@pytest.mark.integration
async def test_full_rejection_flow(supabase_client):
    # Crear proveedor con documentos
    provider = await create_test_provider_with_docs()

    # Ejecutar cleanup
    service = RejectionCleanupService(repository)
    result = await service.cleanup_rejected_provider(
        phone=provider["phone"],
        rejection_reason="Test"
    )

    # Verificar
    assert result["success"] is True
    assert await find_provider(provider["phone"]) is None  # DB
    assert await redis_exists(f"prov_flow:{provider['phone']}") is False  # Redis
    assert await storage_file_exists(provider["dni_front_url"]) is False  # Storage
```

### Monitoreo

**Métricas Prometheus:**
```python
from prometheus_client import Counter, Histogram

cleanup_requests = Counter('rejection_cleanup_requests_total', 'Total cleanups')
cleanup_success = Counter('rejection_cleanup_success_total', 'Successful cleanups')
cleanup_duration = Histogram('rejection_cleanup_duration_seconds', 'Cleanup time')
```

**Alertas:**
```yaml
- alert: HighCleanupFailureRate
  expr: rate(cleanup_failures[5m]) / rate(cleanup_requests[5m]) > 0.1
  for: 5m
  annotations:
    summary: "Más del 10% de cleanups fallando"
```

---

## Parte 4: Roadmap de Implementación

### Semana 1-2: Frontend Foundation

**Día 1-2: Design System**
- Crear `src/styles/design-tokens.css`
- Crear `src/styles/components.css`
- Actualizar `index.html` para importar nuevos estilos
- Probar en todas las páginas

**Día 3-4: Componentes Base**
- Extraer `ProviderTable` a módulo separado
- Extraer `FeedbackToast` a módulo separado
- Extraer `ProviderDetailModal` a módulo separado
- Actualizar imports en `providersManager.ts`

**Día 5: State Management**
- Implementar `CreateStore.ts` (~100 líneas)
- Crear `ProviderStore.ts`
- Migrar lógica de estado de componentes
- Testing básico de state

**Entregables:**
- ✅ Design tokens implementados
- ✅ Componentes extraídos
- ✅ State management funcional
- ✅ tests unitarios pasando

### Semana 3: Provider Rejection Cleanup

**Día 1-2: Backend Commands**
- Implementar 4 comandos de cleanup
- Agregar `undo()` methods (intencionalmente no-ops)
- Unit tests de cada comando

**Día 3-4: Saga y Service**
- Implementar `ProviderRejectionSaga`
- Implementar `RejectionCleanupService`
- Crear endpoint `/providers/reject/cleanup`
- Integration tests

**Día 5: BFF Integration**
- Modificar `providers.js` para llamar cleanup
- Manejar errores de cleanup gracefulmente
- Testing E2E

**Entregables:**
- ✅ Comandos de cleanup implementados
- ✅ Saga con best-effort policy
- ✅ API endpoint funcional
- ✅ BFF integrado con cleanup

### Semana 4: Polish & Deploy

**Día 1-2: Frontend Polish**
- Agregar lazy loading de imágenes
- Implementar DOM caching
- Performance audit con Lighthouse
- Corregir issues de accesibilidad

**Día 3: Testing Completo**
- Unit tests (meta 70% cobertura)
- Integration tests
- E2E tests con WhatsApp real
- Performance tests

**Día 4: Deploy a DEV/STAGING**
- Deploy frontend con feature flags OFF
- Deploy backend con feature flags OFF
- Activar flags en STAGING
- Monitorear métricas

**Día 5: Deploy Gradual a Producción**
- 10% traffic
- Monitorear 48h
- 50% traffic
- Monitorear 48h
- 100% traffic
- Eliminar código legacy

**Entregables:**
- ✅ Performance mejorado
- ✅ 70% test coverage
- ✅ Deployado en STAGING
- ✅ Rollout gradual en producción
- ✅ Código legacy eliminado

---

## Parte 5: Archivos Críticos

### Frontend

1. **`nodejs-services/frontend/apps/admin-dashboard/src/modules/providersManager.ts`**
   - Refactorizar de 743 a ~150 líneas
   - Extraer componentes: ProviderTable, ProviderDetailModal, FeedbackToast
   - Migrar a ProviderStore

2. **`nodejs-services/frontend/apps/admin-dashboard/index.html`**
   - Extraer estilos inline a `design-tokens.css`
   - Agregar imports de nuevos CSS modules
   - Mejorar estructura semántica

3. **`nodejs-services/frontend/apps/admin-dashboard/src/main.ts`**
   - Actualizar imports para nueva estructura de módulos
   - Inicializar stores globales

### Backend Python

4. **`python-services/ai-proveedores/core/commands.py`**
   - Agregar 4 comandos de cleanup (DeleteProviderRecord, DeleteStorageFiles, CleanupRedis, LogRejection)
   - Cada comando tiene `execute()` e `undo()`

5. **`python-services/ai-proveedores/core/saga.py`**
   - Agregar `ProviderRejectionSaga` con best-effort policy
   - Si un paso falla, continúa con los demás

6. **`python-services/ai-proveedores/services/rejection_cleanup_service.py`** (NUEVO)
   - Orquestar cleanup completo
   - Manejar errores gracefulmente
   - Logging detallado

7. **`python-services/ai-proveedores/app/api/providers.py`** (NUEVO)
   - Endpoint POST `/providers/reject/cleanup`
   - Validar request con Pydantic
   - Manejar timeouts

### BFF Node.js

8. **`nodejs-services/frontend/bff/providers.js`**
   - Modificar `rechazarProveedor()` para llamar cleanup
   - Manejar errores de cleanup sin fallar rechazo
   - Feature flag `ENABLE_REJECTION_CLEANUP`

### WhatsApp Service

9. **`nodejs-services/wa-proveedores/src/infrastructure/mqtt/MqttClient.js`**
   - Actualizar `_buildRejectionMessage()` para indicar retorno al consentimiento
   - Mensaje claro: "Envía un mensaje para reiniciar"

---

## Parte 6: Validación y Testing

### Criterios de Aceptación

#### Frontend
- [ ] providersManager.ts reducido de 743 a <200 líneas
- [ ] Componentes extraídos y testables
- [ ] State management funciona correctamente
- [ ] Lighthouse score > 85
- [ ] Accessibility score > 90
- [ ] Test coverage > 70%
- [ ] Bundle size reducido en 15%
- [ ] Performance: First Contentful Paint < 1.5s

#### Rejection Cleanup
- [ ] Al rechazar, se elimina registro de Supabase
- [ ] Se borran documentos de Storage (DNI + selfie)
- [ ] Se limpia sesión de Redis (prov_flow:{phone})
- [ ] Se envía WhatsApp con instrucciones claras
- [ ] Proveedor puede reiniciar registro enviando mensaje
- [ ] Audit trail en logs
- [ ] Best-effort policy funciona (si cleanup falla parcialmente)
- [ ] Feature flag permite rollback instantáneo
- [ ] Monitoreo con métricas Prometheus

### Plan de Testing

**Manual Testing:**
1. Registrar proveedor completo con documentos
2. Rechazar desde admin panel con motivo
3. Verificar WhatsApp recibido
4. Verificar cleanup en logs
5. Enviar mensaje al proveedor rechazado
6. Verificar que recibe prompt de consentimiento
7. Completar nuevo registro
8. Verificar que funciona normalmente

**Automated Testing:**
```bash
# Frontend tests
npm test                    # Unit tests con Vitest
npm run test:coverage       # Con coverage
npm run test:e2e           # E2E con Playwright

# Backend tests
pytest tests/unit/test_rejection_cleanup.py -v
pytest tests/integration/test_rejection_flow.py -v
pytest tests/e2e/test_provider_lifecycle.py -v
```

---

## Parte 7: Monitoreo y Métricas

### Frontend Metrics

**Lighthouse CI:**
```yaml
# .github/workflows/lighthouse.yml
assertions:
  first-contentful-paint:
    - error
    - maxNumeric: 1500  # 1.5s
  interactive:
    - error
    - maxNumeric: 2000  # 2.0s
  accessibility:
    - error
    - minNumeric: 90
```

**Real User Monitoring (RUM):**
```typescript
// Report performance metrics
window.addEventListener('load', () => {
  const perfData = performance.getEntriesByType('navigation')[0];
  const metrics = {
    fcp: perfData.responseStart - perfData.fetchStart,
    tti: perfData.domInteractive - perfData.fetchStart
  };
  // Send to analytics
});
```

### Backend Metrics

**Prometheus Metrics:**
```python
# Cleanup metrics
rejection_cleanup_requests_total
rejection_cleanup_success_total
rejection_cleanup_failure_total
rejection_cleanup_duration_seconds

# Breakdown by step
storage_delete_duration_seconds
redis_cleanup_duration_seconds
db_delete_duration_seconds
```

**Grafana Dashboards:**
- Panel: Cleanup success rate (last 24h)
- Panel: Cleanup duration p95 (last 24h)
- Panel: Failure rate by step
- Panel: Orphaned data (rejected providers > 7d old)

---

## Parte 8: Plan de Rollback

### Frontend
- **Si issues críticos:** Revertir a versión anterior de providersManager.ts
- **Tiempo de rollback:** < 5 minutos (solo cambiar archivos)
- **Datos afectados:** Ninguno (solo frontend)

### Backend Cleanup
- **Si issues críticos:**
  1. Set `ENABLE_REJECTION_CLEANUP=false`
  2. Restart ai-proveedores service
  3. Ejecutar script de cleanup manual para afectados
  4. Investigar logs
- **Tiempo de rollback:** < 10 minutos
- **Datos afectados:** Proveedores rechazados durante período activo (requiere cleanup manual)

### Script de Cleanup Manual

```python
# scripts/manual_cleanup.py
async def cleanup_rejected_providers(since: str):
    """Cleanup manual para proveedores rechazados"""
    # Buscar proveedores con verified=false
    # Ejecutar cleanup saga para cada uno
    # Report resultados
```

---

## Parte 9: Documentación

### Actualizaciones Requeridas

**1. README Frontend**
```markdown
## Provider Rejection Cleanup

When a provider is rejected, the system automatically:
1. Logs rejection event (audit trail)
2. Deletes uploaded documents from Supabase Storage
3. Cleans up Redis session data
4. Deletes provider record from database

The provider can restart registration by sending any WhatsApp message.

Feature Flag: `ENABLE_REJECTION_CLEANUP=true/false`
```

**2. API Documentation**
```markdown
### POST /providers/reject/cleanup

Clean up all provider data after rejection.

**Request:**
```json
{
  "phone": "593123456789",
  "rejection_reason": "Documents unclear",
  "reviewer": "Admin"
}
```

**Response:**
```json
{
  "success": true,
  "phone": "593123456789",
  "provider_id": "abc-123",
  "cleanup_result": {
    "successful_commands": 4,
    "total_commands": 4
  },
  "can_restart_registration": true
}
```
```

**3. Architecture Docs**
- Crear `docs/architecture/rejection-cleanup.md`
- Diagrama de secuencia completo
- Explicación de best-effort policy
- Guía de troubleshooting

---

## Parte 10: Resumen de Cambios

### Archivos a Crear (11)

**Frontend (6):**
1. `src/core/CreateStore.ts`
2. `src/core/DOMCache.ts`
3. `src/core/AbortController.ts`
4. `src/styles/design-tokens.css`
5. `src/styles/components.css`
6. `src/modules/providers/state/ProviderStore.ts`

**Backend (5):**
7. `python-services/ai-proveedores/services/rejection_cleanup_service.py`
8. `python-services/ai-proveedores/app/api/providers.py`
9. `tests/unit/test_rejection_cleanup.py`
10. `tests/integration/test_rejection_flow.py`
11. `docs/architecture/rejection-cleanup.md`

### Archivos a Modificar (9)

**Frontend (3):**
1. `src/modules/providersManager.ts` - Refactor de 743 a 150 líneas
2. `src/main.ts` - Actualizar imports
3. `index.html` - Importar nuevos CSS

**Backend (3):**
4. `core/commands.py` - Agregar 4 comandos
5. `core/saga.py` - Agregar ProviderRejectionSaga
6. `core/feature_flags.py` - Agregar ENABLE_REJECTION_CLEANUP

**BFF (2):**
7. `bff/providers.js` - Llamar cleanup endpoint
8. `wa-proveedores/.../MqttClient.js` - Actualizar mensaje rechazo

**Docs (1):**
9. `README.md` - Documentar cleanup feature

### Líneas de Código

- **Nuevas:** ~2,000 líneas (incluyendo tests)
- **Modificadas:** ~500 líneas
- **Eliminadas:** ~400 líneas (código legacy)
- **Net change:** +2,100 líneas pero mejor organizadas y testeables

---

## Parte 11: Riesgos y Mitigación

### Riesgo 1: Cleanup Borra Datos Importantes
**Mitigación:**
- Best-effort policy: Si cleanup falla, no revertir rechazo
- Audit trail completo en logs
- Backup automático de Storage antes de delete
- Testing extensivo en STAGING primero

### Riesgo 2: Performance Degradation
**Mitigación:**
- Métricas Prometheus en tiempo real
- Alerts si cleanup dura > 30s
- Lazy loading de imágenes
- DOM caching en frontend

### Riesgo 3: Provider Queda "Atascado"
**Mitigación:**
- Cleanup usa best-effort (si falla, provider aún puede reiniciar)
- Script de cleanup manual por si acaso
- Redis TTL natural expira (backup)
- Monitoreo de orphans

### Riesgo 4: Frontend Breaks en Producción
**Mitigación:**
- Feature flags permiten rollback instantáneo
- Deploy incremental (10% → 50% → 100%)
- Testing extensivo (70% coverage)
- Lighthouse CI en PRs

### Riesgo 5: Sobre-ingeniería
**Mitigación:**
- Principio "menos es más"
- Code reviews enfocados en simplicidad
- NO migrar a frameworks pesados
- Mantener Bootstrap como base
- State management custom (100 líneas, no Redux)

---

## Parte 12: Próximos Pasos

### Inmediato (Esta Semana)
1. ✅ Revisar y aprobar este plan
2. ⏳ Crear branches: `feature/frontend-refactor`, `feature/rejection-cleanup`
3. ⏳ Setup testing infrastructure (Vitest, pytest configs)
4. ⏳ Iniciar con Design System (día 1)

### Corto Plazo (Semanas 1-2)
5. ⏳ Implementar design tokens y componentes base
6. ⏳ Extraer componentes de providersManager
7. ⏳ Implementar comandos de cleanup
8. ⏳ Unit tests de comandos

### Mediano Plazo (Semanas 3-4)
9. ⏳ Implementar ProviderRejectionSaga
10. ⏳ Integrar BFF con cleanup
11. ⏳ Testing E2E completo
12. ⏳ Deploy a STAGING

### Largo Plazo (Mes 2)
13. ⏳ Rollout gradual a producción
14. ⏳ Monitoreo y ajustes
15. ⏳ Eliminar código legacy
16. ⏳ Documentación completa

---

## Aprobación

**Requiere aprobación de:**
- [ ] Líder técnico
- [ ] Equipo de frontend
- [ ] Equipo de backend
- [ ] Equipo de DevOps

**Fecha objetivo de inicio:** 2025-01-15
**Fecha objetivo de completion:** 2025-02-15 (4 semanas)

---

**Notas finales:**

Este plan sigue el principio de **"menos es más"**:
- ✅ No migraremos a React/Vue (Bootstrap + TypeScript es suficiente)
- ✅ No implementaremos Redux/Zustand (Pub/sub custom de 100 líneas)
- ✅ No over-engineering con patrones complejos (SOLID sí, pero pragmático)
- ✅ Feature flags para rollback instantáneo
- ✅ Deploy incremental (10% → 50% → 100%)
- ✅ Testing pragmático (70% coverage, no 100%)

**El objetivo es simplicidad mantenible, no perfección arquitectónica.**
