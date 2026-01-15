# Executed Migrations

Esta carpeta contiene scripts SQL que **ya fueron ejecutados** en Supabase.

⚠️ **NO ejecutar estos scripts nuevamente** a menos que sepas lo que haces.

## Scripts Archivados

### 1. create_service_synonyms_table.sql
**Fecha**: Enero 2026
**Propósito**: Crear tabla `service_synonyms` + insertar 130 sinónimos iniciales
**Estado**: ✅ Ejecutado y verificado

**Contenido:**
- Tabla: `service_synonyms` (canonical_profession, synonym, active, timestamps)
- Índices: Para búsquedas rápidas
- Trigger: Para actualizar `updated_at` automáticamente
- Datos iniciales: 130 sinónimos (marketing, plomero, electricista, etc.)

---

### 2. create_learned_synonyms_table.sql
**Fecha**: Enero 2026
**Propósito**: Crear tabla `learned_synonyms` para sistema de aprendizaje automático
**Estado**: ✅ Ejecutado y verificado

**Contenido:**
- Tabla: `learned_synonyms` (id, canonical_profession, learned_synonym, confidence_score, match_count, status, etc.)
- Índices: 5 índices para búsquedas eficientes
- Trigger: Para actualizar `updated_at` automáticamente
- Constraint: UNIQUE(canonical_profession, learned_synonym)

---

### 3. create_search_indexes_simple.sql
**Fecha**: Enero 2026
**Propósito**: Crear 2 índices compuestos para optimizar búsquedas
**Estado**: ✅ Ejecutado y verificado

**Contenido:**
- `idx_providers_city_profession_rating`: (city, profession, rating DESC) WHERE verified=true
- `idx_providers_verified_rating`: (verified, rating DESC) WHERE verified=true

---

### 4. create_search_performance_indexes.sql
**Fecha**: Enero 2026
**Propósito**: Versión completa con documentación de índices de búsqueda
**Estado**: ✅ Ejecutado (redundante con el script simple)

**Contenido:**
- Mismos 2 índices que el script simple
- Documentación extensa
- Queries de verificación
- Tests de performance

**Nota**: Este script es redundante con `create_search_indexes_simple.sql`. Se archiva para referencia histórica.

---

## Cómo Revertir (si es necesario)

Si necesitas volver a ejecutar cualquiera de estos scripts:

1. **Verificar que la tabla/índice NO existe** en Supabase
2. **Mover el script** de vuelta a `migrations/`
3. **Ejecutar** en Supabase SQL Editor
4. **Verificar** que se creó correctamente

---

## Historial de Cambios

- **2026-01-15**: Archivado post-implementación del Enhanced Search V2 + SynonymLearner
