# 📋 Análisis de Código Muerto en ai-proveedores

**Fecha:** 17 de enero de 2026
**Alcance:** python-services/ai-proveedores
**Archivos analizados:** ~50 archivos Python
**Método:** Revisión línea por línea, análisis de dependencias y uso de feature flags

---

## 📊 Resumen Ejecutivo

| Categoría | Cantidad | Líneas aprox. |
|-----------|----------|---------------|
| Archivos Python totales | ~50 | ~8,000 |
| Archivos completamente huérfanos | 1 | 208 |
| Archivos __init__.py vacíos | 7 | ~11 |
| Funciones/clases no usadas | 34 | ~1,190 |
| Importaciones no usadas | 1 | ~22 |
| Bloques de código comentados | 1 | ~11 |
| **Código potencialmente eliminable** | - | **~1,440 líneas (18%)** |

---

## 🔴 Archivos Completamente Huérfanos

### 1. `core/feature_flags.py` (208 líneas) ⚠️

- **Estado:** ARCHIVO HUÉRFANO
- **Descripción:** Módulo centralizado de feature flags para migración arquitectónica
- **Feature flags definidas:**
  - `USE_REPOSITORY_PATTERN = True` ✅
  - `USE_STATE_MACHINE = True` ✅
  - `USE_SAGA_ROLLBACK = True` ✅
  - `ENABLE_IMAGE_VALIDATION = True` ✅
  - `ENABLE_PARALLEL_UPLOAD = True` ✅
  - `ENABLE_LEGACY_CLEANUP = True` ✅

- **Funciones no usadas:**
  - `get_all_flags()` - Retorna diccionario con estado de flags (nunca se llama)
  - `get_phase_status(phase: int)` - Verifica si fase está activada (nunca se llama)
  - `validate_activation_order()` - Valida orden de activación (nunca se llama)
  - `print_status()` - Imprime estado legible (solo en `if __name__ == "__main__"`)

- **Problema principal:**
  - Las flags están **DUPLICADAS** en:
    - `flows/provider_flow.py` (líneas 15-20)
    - `services/provider_flow_delegate_service.py` (líneas 13-14)
  - Las funciones utilitarias nunca se invocan
  - Solo se importan para copiar los valores como constantes locales

- **Recomendación:**
  - **OPCIÓN A:** Eliminar `core/feature_flags.py` completamente (208 líneas)
  - **OPCIÓN B:** Centralizar las flags en este archivo y eliminar duplicados en otros archivos
  - **OPCIÓN C:** Mantener solo las funciones utilitarias y usarlas realmente

---

### 2. Archivos `__init__.py` Vacíos (7 archivos, ~11 líneas)

Los siguientes archivos `__init__.py` están **VACÍOS** o solo contienen docstrings, y **NADIE los importa**:

| Archivo | Contenido | Líneas |
|---------|-----------|--------|
| `handlers/__init__.py` | Solo docstring | 2 |
| `services/__init__.py` | Vacío | 1 |
| `app/__init__.py` | Solo docstring | 2 |
| `models/__init__.py` | Vacío | 1 |
| `templates/__init__.py` | Solo docstring | 2 |
| `utils/__init__.py` | Vacío | 1 |
| `core/__init__.py` | Exporta clases pero nadie las usa | 2 |

**Nota sobre `core/__init__.py`:**
- Exporta: `Command`, `RegisterProviderCommand`, `ProviderRegistrationSaga`, `RepositoryError`, `InvalidTransitionError`, `StateHandlerNotFoundError`, `SagaExecutionError`
- Estas exportaciones **NUNCA se importan** desde `from core import ...`
- Todos los módulos importan directamente: `from core.commands import ...`, `from core.saga import ...`, etc.

**Recomendación:**
- Eliminar los 7 archivos vacíos o agregar exportaciones útiles que realmente se usen
- Mantener solo `__init__.py` que tengan exportaciones o docstrings significativos

---

## 🟡 Archivos con Código Mayormente Inactivo

### 1. `services/image_service.py` (713 líneas, ~465 líneas muertas)

**Estado:** Implementación temprana que fue reemplazada pero no eliminada

**Funciones que SÍ se usan (248 líneas):**
1. `subir_medios_identidad()` - Orquestador principal para subir documentos de identidad
2. `upload_all_images_parallel()` - Sube imágenes en paralelo (si feature flag activado)

**Funciones que NO se usan (11 funciones, ~465 líneas):**

| Función | Líneas | Descripción |
|---------|--------|-------------|
| `upload_dni_front()` | 47 | Sube foto frontal de DNI |
| `upload_dni_back()` | 47 | Sube foto reverso de DNI |
| `upload_face_photo()` | 47 | Sube foto facial |
| `get_dni_front_url()` | 33 | Obtiene URL de foto frontal |
| `get_dni_back_url()` | 33 | Obtiene URL de foto reverso |
| `get_face_photo_url()` | 33 | Obtiene URL de foto facial |
| `update_dni_front_url()` | 43 | Actualiza URL frontal |
| `update_dni_back_url()` | 43 | Actualiza URL reverso |
| `update_face_photo_url()` | 43 | Actualiza URL facial |
| `delete_image()` | 73 | Elimina imagen del almacenamiento |
| `_extract_storage_path_from_url()` | 45 | Extrae path de URL |

**Integración actual:**
- Los validadores de imagen en `validators/` YA SE INTEGRARON
- `services/provider_flow_delegate_service.py` usa validadores directamente
- Las funciones individuales de `image_service.py` siguen ahí sin usarse

**Comentario obsoleto en `validators/__init__.py` (líneas 5-13):**
```python
# TODO: Integrar con services/image_service.py
#   - Los siguientes métodos de image_service.py se modificarán para usar estos validadores:
#     * upload_dni_front() - validar tamaño, formato y contenido
#     * upload_dni_back() - validar tamaño, formato y contenido
#     * upload_provider_photo() - validar tamaño, formato y contenido
```

**Recomendación:**
- **OPCIÓN A:** Eliminar las 11 funciones no usadas (~465 líneas)
- **OPCIÓN B:** Mover las funciones a un archivo `legacy/` si se planea usar en futuro
- **OPCIÓN C:** Eliminar TODO obsoleto en `validators/__init__.py`

---

## 🟠 Funciones y Clases No Usadas

### En `core/saga.py`

| Método | Líneas aprox. | Descripción |
|--------|--------------|-------------|
| `get_status()` | ~25 | Retorna estado de la saga |
| `reset()` | ~20 | Resetea la saga para reutilización |

**Estado:** Implementados pero nunca se llaman
**Uso potencial:** Útiles para debugging y monitoreo
**Recomendación:** Mantener por ahora (pueden ser útiles en producción)

---

### En `core/state_machine.py`

| Método | Líneas aprox. | Descripción |
|--------|--------------|-------------|
| `can_transition()` | ~20 | Valida si transición es válida |
| `transition()` | ~15 | Ejecuta transición entre estados |
| `get_next_states()` | ~20 | Retorna estados posibles desde actual |

**Estado:** Implementados pero nunca se llaman
**Nota:** La máquina de estados solo se usa para ejecutar handlers directos
**Recomendación:** Eliminar si no se planean usar en 3 meses

---

### En `repositories/provider_repository.py`

| Método | Líneas aprox. | Descripción |
|--------|--------------|-------------|
| `toggle_availability(provider_id: str)` | ~28 | Activa/desactiva disponibilidad |

**Estado:** Implementado completo pero nunca se invoca
**Nota:** Funcionalidad útil pero no implementada en el flujo
**Recomendación:** Eliminar si no se va a usar pronto

---

### En `infrastructure/redis.py`

| Método | Líneas aprox. | Descripción |
|--------|--------------|-------------|
| `publish(channel, message)` | ~25 | Publica mensaje en canal MQTT |
| `subscribe(channel, callback)` | ~30 | Se suscribe a canal MQTT |
| `_cleanup_expired_memory()` | ~13 | Limpia memoria expirada (fallback local) |

**Estado:** Implementados pero nunca se invocan
**Nota:** Para Pub/Sub MQTT que parece no usarse
**Recomendación:** Eliminar si no se usa Pub/Sub MQTT

---

### En `app/dependencies.py`

| Método | Líneas aprox. | Descripción |
|--------|--------------|-------------|
| `reset_clients()` | ~5 | Resetea clientes (para testing) |

**Estado:** Implementado pero nunca se llama
**Nota:** Útil para testing pero actualmente no se usa
**Recomendación:** Mantener si hay tests que lo necesitan, de lo contrario eliminar

---

### En `models/schemas.py`

| Clase | Líneas | Descripción |
|--------|--------|-------------|
| `ProviderResponse` | 22 | Modelo de respuesta para proveedor |

**Estado:** Se define pero NUNCA se usa
**Búsqueda:** No hay referencias en todo el proyecto
**Clases SÍ usadas:** `HealthResponse`, `IntelligentSearchRequest`, `WhatsAppMessageReceive`, `ProviderCreate`
**Recomendación:** Eliminar (~22 líneas)

---

## 🟡 Importaciones No Usadas

### En `models/schemas.py`

- **`ProviderResponse` class** (líneas 32-53) - Se define pero NUNCA se usa

**Recomendación:** Eliminar esta clase completamente

---

## ⚪ Bloques de Código Comentados

### En `validators/__init__.py` (líneas 5-13)

Bloque TODO obsoleto (11 líneas):
```python
# TODO: Integrar con services/image_service.py
#   - Los siguientes métodos de image_service.py se modificarán para usar estos validadores:
#     * upload_dni_front() - validar tamaño, formato y contenido
#     * upload_dni_back() - validar tamaño, formato y contenido
#     * upload_provider_photo() - validar tamaño, formato y contenido
```

**Estado:** La integración YA SE HIZO en `services/provider_flow_delegate_service.py`
**Recomendación:** Actualizar o eliminar este comentario obsoleto

---

## 📈 Análisis por Patrón de Diseño

### Patrón 1: Duplicación de Feature Flags

**Archivos afectados:**
- `core/feature_flags.py` - 208 líneas (completo)
- `flows/provider_flow.py` - flags duplicadas
- `services/provider_flow_delegate_service.py` - flags duplicadas

**Estado:**
- Las flags se definen en `core/feature_flags.py` (208 líneas)
- Los MISMOS flags se redefinen en otros archivos como constantes locales
- Las funciones utilitarias de `core/feature_flags.py` nunca se llaman
- Esto hace que el archivo sea casi completamente innecesario

**Recomendación:**
1. **OPCIÓN A:** Eliminar `core/feature_flags.py` completamente
2. **OPCIÓN B:** Centralizar las flags en este archivo y eliminar duplicados
3. **OPCIÓN C:** Mantener solo las funciones utilitarias y hacerlas usar realmente

---

### Patrón 2: Métodos Individuales de Image Service No Usados

**Archivos afectados:**
- `services/image_service.py` - 11 funciones, ~465 líneas

**Estado:**
- Las funciones individuales (upload_dni_front, upload_dni_back, etc.) fueron implementadas temprano
- Luego se hizo una refactorización usando validadores
- Ahora solo se usan 2 de 13 funciones: `subir_medios_identidad()` y `upload_all_images_parallel()`
- Las funciones individuales siguen ahí sin usarse

**Recomendación:**
1. Eliminar las 11 funciones no usadas (~465 líneas)
2. Mantener solo las 2 funciones que sí se usan
3. Actualizar comentarios obsoletos

---

### Patrón 3: Métodos No Usados de State Machine

**Archivos afectados:**
- `core/state_machine.py` - 3 métodos, ~55 líneas

**Estado:**
- `can_transition()`, `transition()`, `get_next_states()` están implementados
- Proporcionan funcionalidad útil pero nunca se invocan
- La máquina de estados solo se usa para ejecutar handlers directos

**Recomendación:**
1. Decidir si se van a usar en 3 meses
2. Si NO → Eliminar los 3 métodos
3. Si SÍ → Implementar su uso en el flujo de proveedores

---

### Patrón 4: Métodos No Usados de Saga

**Archivos afectados:**
- `core/saga.py` - 2 métodos, ~45 líneas

**Estado:**
- `get_status()` y `reset()` están implementados
- Útiles para debugging y monitoreo pero nunca se llaman
- La saga se ejecuta pero nunca se consulta su estado

**Recomendación:**
1. Mantener por ahora (pueden ser útiles para debugging)
2. Considerar agregar endpoints de debug que los usen

---

## 📋 Estado de Feature Flags

| Feature Flag | Estado | Código inactivo |
|-------------|--------|----------------|
| `USE_REPOSITORY_PATTERN` | True ✅ | 0 líneas |
| `USE_STATE_MACHINE` | True ✅ | 0 líneas |
| `USE_SAGA_ROLLBACK` | True ✅ | 0 líneas |
| `ENABLE_IMAGE_VALIDATION` | True ✅ | 0 líneas |
| `ENABLE_PARALLEL_UPLOAD` | True ✅ | 0 líneas |
| `ENABLE_LEGACY_CLEANUP` | True ✅ | 0 líneas |

**NOTA IMPORTANTE:** Todas las feature flags están ACTIVADAS. No hay código inactivo por flags desactivadas.

Sin embargo, `core/feature_flags.py` tiene 208 líneas que son casi completamente innecesarias porque:
1. Las flags están duplicadas en otros archivos
2. Las funciones utilitarias nunca se llaman
3. Solo se importa para copiar valores como constantes locales

---

## 📊 Métricas Finales

| Categoría | Archivos | Líneas |
|-----------|---------|--------|
| Archivo huérfano completo | 1 | 208 |
| Archivos __init__.py vacíos | 7 | ~11 |
| Funciones no usadas en core/feature_flags.py | 4 | ~65 |
| Funciones no usadas en core/saga.py | 2 | ~45 |
| Funciones no usadas en core/state_machine.py | 3 | ~55 |
| Funciones no usadas en repositories/provider_repository.py | 1 | ~28 |
| Funciones no usadas en infrastructure/redis.py | 3 | ~68 |
| Funciones no usadas en services/image_service.py | 11 | ~465 |
| Funciones no usadas en app/dependencies.py | 1 | ~5 |
| Clases no usadas en models/schemas.py | 1 | ~22 |
| Bloques comentados obsoletos | 1 | ~11 |
| **TOTAL** | - | **~984 líneas** |
| **Código activo en producción** | - | **~7,000 líneas** |
| **Porcentaje eliminable** | - | **~12%** |

---

## 🎯 Plan Resumido de Limpieza

### Fase 1: Eliminación Inmediata (Alta Prioridad)

**Archivos a eliminar:**
1. ✅ Eliminar `services/image_service.py` funciones no usadas (11 funciones, ~465 líneas)
2. ✅ Decidir destino de `core/feature_flags.py` (208 líneas)
3. ✅ Eliminar `ProviderResponse` de `models/schemas.py` (22 líneas)

**Importaciones a eliminar:**
1. ✅ Actualizar comentario TODO obsoleto en `validators/__init__.py` (11 líneas)
2. ✅ Eliminar archivos `__init__.py` vacíos (7 archivos, ~11 líneas)

**Impacto esperado:** ~717 líneas eliminadas

---

### Fase 2: Revisión de Patrón de Feature Flags (Media Prioridad)

**Decisión pendiente: `core/feature_flags.py` (208 líneas)**

**Preguntas para el equipo:**
1. ¿Queremos centralizar las feature flags en un solo lugar?
2. ¿Queremos usar las funciones utilitarias (`get_all_flags()`, `validate_activation_order()`)?
3. ¿Es mejor mantener las flags como constantes locales en cada archivo?

**Acciones:**
- **OPCIÓN A (Eliminar):** Eliminar `core/feature_flags.py` completamente (208 líneas)
  - Eliminar duplicados en `flows/provider_flow.py` y `services/provider_flow_delegate_service.py`
  - Perderíamos las funciones utilitarias (que no se usan de todos modos)

- **OPCIÓN B (Centralizar):** Centralizar las flags en `core/feature_flags.py`
  - Eliminar duplicados en otros archivos
  - Importar desde `core.feature_flags` en todos lados
  - Usar realmente las funciones utilitarias (agregar endpoints de debug)

- **OPCIÓN C (Híbrida):** Mantener solo funciones utilitarias
  - Eliminar las flags duplicadas en otros archivos
  - Mantener `core/feature_flags.py` solo con funciones de utilidad
  - Las flags como constantes se quedan en cada archivo

**Timeline:** 2 semanas para decidir

---

### Fase 3: Métodos No Usados de Patrones de Diseño (Media Prioridad)

**Archivos a revisar:**
- `core/state_machine.py` - 3 métodos, ~55 líneas
- `core/saga.py` - 2 métodos, ~45 líneas
- `repositories/provider_repository.py` - 1 método, ~28 líneas
- `infrastructure/redis.py` - 3 métodos, ~68 líneas
- `app/dependencies.py` - 1 método, ~5 líneas

**Acciones:**
1. Decidir si se van a usar en los próximos 3 meses
2. Si NO → Eliminar métodos no usados
3. Si SÍ → Implementar su uso o agregar endpoints de debug

**Timeline:** 1 mes para decidir

---

### Fase 4: Limpieza Final (Baja Prioridad)

**Acciones:**
1. Eliminar archivos `__init__.py` vacíos (7 archivos)
2. Verificar que no hay importaciones rotas después de limpiezas
3. Ejecutar linter y typechecker para verificar errores
4. Correr tests completos para asegurar que nada se rompió

**Impacto esperado:** ~11 líneas eliminadas

---

## ✅ Checklist de Limpieza

### Fase 1 (Inmediata)
- [ ] Eliminar 11 funciones no usadas de `services/image_service.py` (~465 líneas)
- [ ] Decidir destino de `core/feature_flags.py`
- [ ] [ ] Eliminar → 208 líneas
- [ ] [ ] Centralizar → Eliminar duplicados en otros archivos
- [ ] [ ] Híbrida → Mantener solo funciones utilitarias
- [ ] Eliminar `ProviderResponse` de `models/schemas.py` (22 líneas)
- [ ] Actualizar/eliminar comentario TODO en `validators/__init__.py` (11 líneas)

### Fase 2 (2 semanas)
- [ ] Revisar con equipo sobre patrón de feature flags
- [ ] Decidir y ejecutar opción elegida para `core/feature_flags.py`
- [ ] Verificar que imports funcionan correctamente
- [ ] Probar que aplicación inicia sin errores

### Fase 3 (1 mes)
- [ ] Decidir mantener o eliminar métodos no usados de StateMachine (3 métodos, ~55 líneas)
- [ ] Decidir mantener o eliminar métodos no usados de Saga (2 métodos, ~45 líneas)
- [ ] Decidir mantener o eliminar `toggle_availability()` (28 líneas)
- [ ] Decidir mantener o eliminar métodos MQTT de RedisClient (3 métodos, ~68 líneas)
- [ ] Decidir mantener o eliminar `reset_clients()` (5 líneas)

### Fase 4 (1 semana)
- [ ] Eliminar archivos `__init__.py` vacíos (7 archivos)
- [ ] Limpiar cualquier importación rota
- [ ] Ejecutar linter (ruff/pylint)
- [ ] Ejecutar typechecker (pyright/mypy)
- [ ] Correr tests completos
- [ ] Verificar que aplicación funciona en producción

---

## 🚨 Riesgos y Consideraciones

### Riesgo: Romper tests existentes
- **Mitigación:** Ejecutar suite de tests completa después de cada cambio
- **Mitigación:** Hacer cambios incrementales y verificar entre cada cambio

### Riesgo: Eliminar funcionalidad futura planeada
- **Mitigación:** Revisar documentación y tickets del proyecto
- **Mitigación:** Consultar con el equipo antes de eliminar
- **Mitigación:** Todo el código está en git, se puede restaurar

### Riesgo: Eliminar código que otros microservicios usan
- **Mitigación:** Revisar dependencias con ai-clientes y otros servicios
- **Mitigación:** Verificar que no hay imports externos

### Riesgo: Romper la centralización de feature flags
- **Mitigación:** Si se elige centralizar, hacerlo cuidadosamente
- **Mitigación:** Verificar que todos los módulos importan correctamente
- **Mitigación:** Probar en entorno de staging antes de producción

---

## 📝 Recomendaciones Finales

1. **Inmediatamente (esta semana):**
   - Eliminar 11 funciones no usadas de `services/image_service.py` (~465 líneas)
   - Eliminar `ProviderResponse` de `models/schemas.py` (22 líneas)
   - Actualizar/eliminar comentario TODO obsoleto en `validators/__init__.py`

2. **Corto plazo (2 semanas):**
   - Decidir el patrón para feature flags
   - Eliminar `core/feature_flags.py` o centralizar flags
   - Verificar que todo funciona correctamente

3. **Medio plazo (1 mes):**
   - Revisar métodos no usados de patrones de diseño
   - Decidir mantener o eliminar StateMachine, Saga, Repository, Redis métodos
   - Implementar uso real o eliminar completamente

4. **Largo plazo (3 meses):**
   - Eliminar archivos `__init__.py` vacíos
   - Mantener proceso de revisión periódica de código muerto
   - Implementar herramientas automatizadas para detectar código huérfano

---

## 🔗 Referencias

- **Feature Flags:** `python-services/ai-proveedores/core/feature_flags.py`
- **Image Service:** `python-services/ai-proveedores/services/image_service.py`
- **Schemas:** `python-services/ai-proveedores/models/schemas.py`
- **Main App:** `python-services/ai-proveedores/app/main.py`
- **AGENTS.md:** `/home/du/produccion/tinkubot-microservices/AGENTS.md`

---

## 📊 Comparación con ai-clientes

| Categoría | ai-clientes | ai-proveedores |
|-----------|-------------|----------------|
| Archivos Python totales | 68 | ~50 |
| Código eliminable | ~4,900 líneas (33%) | ~984 líneas (12%) |
| Feature flags desactivadas | 8 (3,900 líneas inactivas) | 0 (todas activas) |
| Archivos huérfanos | 2 | 1 |
| Patrón Saga/Command | Implementado pero no usado | Implementado y activo |
| Patrón State Machine | Activo | Activo |
| Feature flags duplicadas | No | Sí (core/feature_flags.py) |

**Observación:** ai-proveedores tiene menos código muerto que ai-clientes porque:
1. No tiene feature flags desactivadas
2. Sus patrones de diseño (Saga, State Machine) están activos
3. El código está más limpio y actualizado

**Problema específico de ai-proveedores:** Duplicación de feature flags en `core/feature_flags.py` que casi no se usa.

---

**Documento generado:** 17 de enero de 2026
**Próxima revisión sugerida:** 17 de julio de 2026 (6 meses)
