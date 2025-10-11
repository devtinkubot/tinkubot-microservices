# Plan de Entregas Parciales - Migración a Arquitectura en Español

## 🎯 Objetivo

Establecer un plan de migración sistemático con entregas graduales para minimizar impacto en el servicio y facilitar reversión si es necesario.

## 📅 Cronograma General

**Duración total estimada**: 3-4 semanas
**Ventana de mantenimiento**: Cada fase en horario de bajo uso (02:00 - 06:00 AM Ecuador)
**Periodo de estabilización**: 2-3 días entre fases

---

## 📋 Fase 0: Preparación y Planificación (3 días)

### Objetivos
- Aprobación final del plan
- Preparación de entorno
- Backup completo

### Entregables
- [ ] Plan de migración aprobado por stakeholders
- [ ] Entorno de staging replicado y funcionando
- [ ] Backup completo de base de datos y código
- [ ] Scripts de migración desarrollados y probados
- [ ] Documentación completa disponible

### Tareas Detalladas

#### Día 1: Aprobación y Entorno
1. **Revisión final del plan**
   - Presentación a stakeholders
   - Aprobación formal
   - Asignación de responsables

2. **Preparación de entorno**
   ```bash
   # Clonar a staging
   git checkout -b migration-staging

   # Configurar variables de entorno
   cp .env .env.staging
   cp docker-compose.yml docker-compose.staging.yml
   ```

3. **Validación de entorno**
   - Scripts de configuración ejecutados
   - Tests de conexión realizados
   - Documentación revisada

#### Día 2: Desarrollo de Scripts
1. **Scripts de migración de datos**
   - `migracion_datos.py` completado
   - Scripts SQL individuales por tabla
   - Scripts de validación

2. **Scripts de rollback**
   - `rollback_migration.py`
   - Procedimientos de emergencia
   - Comandos de restauración

3. **Scripts de testing**
   - `test_migration.py`
   - Casos de prueba automatizados
   - Validación de integridad

#### Día 3: Testing y Validación
1. **Testing en staging**
   - Migración completa en ambiente de prueba
   - Validación de datos migrados
   - Testing de funcionalidades críticas

2. **Validación de rendimiento**
   - Benchmarking pre/post migración
   - Identificación de cuellos de botella
   - Optimización de queries

3. **Preparación de comunicación**
   - Notificación a usuarios
   - Plan de comunicación interna
   - Documentación de soporte

### Criterios de Éxito
- ✅ Plan aprobado por todos los stakeholders
- ✅ Entorno de staging estable y replicado
- ✅ Scripts de migración funcionando correctamente
- ✅ Backup completo verificado
- ✅ Testing exitoso en staging

### Riesgos y Mitigación
- **Riesgo**: Fallo en replicación de entorno
  - **Mitigación**: Documentación detallada + soporte técnico disponible

- **Riesgo**: Scripts con errores
  - **Mitigación**: Testing exhaustivo + revisión por pares

---

## 📋 Fase 1: Creación de Nuevas Tablas (1 noche)

### Objetivos
- Crear nueva estructura de tablas en español
- Validar esquema y relaciones
- Preparar para migración de datos

### Ventana de Mantenimiento
**Fecha**: [Por definir]
**Horario**: 02:00 - 06:00 AM Ecuador
**Duración estimada**: 3-4 horas
**Impacto**: Sin impacto en usuarios (solo cambios en schema)

### Entregables
- [ ] Nuevas tablas creadas en producción
- [ ] Índices configurados y optimizados
- [ ] Restricciones y validaciones implementadas
- [ ] Documentación de schema actualizada

### Tareas Detalladas

#### Pre-Migración (22:00 - 02:00)
1. **Notificación interna**
   ```bash
   # Notificar al equipo sobre maintenance window
   echo "🔔 Maintenance window iniciado - Fase 1: Creación de tablas"
   ```

2. **Verificación de pre-requisitos**
   ```bash
   # Validar conexiones
   python scripts/test-connection.py

   # Verificar backup
   ls -la backups/
   ```

3. **Preparación de scripts**
   ```bash
   # Cargar scripts de creación
   cat migration-scripts/01-create-tables.sql

   # Validar sintaxis
   psql $DATABASE_URL -f migration-scripts/01-create-tables.sql --dry-run
   ```

#### Ejecución (02:00 - 05:00)
1. **Creación de tablas principales**
   ```sql
   -- Tabla clientes
   CREATE TABLE clientes (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       telefono VARCHAR(20) UNIQUE NOT NULL,
       nombre_completo VARCHAR(255) NOT NULL,
       ciudad VARCHAR(100),
       ciudad_confirmada_at TIMESTAMP,
       notas JSONB DEFAULT '{}',
       estado VARCHAR(20) DEFAULT 'activo',
       creado_at TIMESTAMP DEFAULT NOW(),
       actualizado_at TIMESTAMP DEFAULT NOW()
   );

   -- [Continuar con resto de tablas según migracion-datos.md]
   ```

2. **Creación de índices**
   ```sql
   -- Índices para clientes
   CREATE INDEX idx_clientes_telefono ON clientes(telefono);
   CREATE INDEX idx_clientes_ciudad ON clientes(ciudad);
   CREATE INDEX idx_clientes_estado ON clientes(estado);

   -- [Continuar con resto de índices]
   ```

3. **Validación de estructura**
   ```sql
   -- Verificar tablas creadas
   \dt

   -- Validar esquema
   \d clientes
   \d proveedores
   ```

#### Post-Migración (05:00 - 06:00)
1. **Validación completa**
   ```sql
   -- Verificar integridad referencial
   SELECT conname, contype
   FROM pg_constraint
   WHERE conrelid IN (
       SELECT oid FROM pg_class WHERE relname IN (
           'clientes', 'proveedores', 'profesiones'
       )
   );
   ```

2. **Testing de acceso**
   ```bash
   # Probar acceso a nuevas tablas
   python scripts/test-new-tables.py
   ```

3. **Documentación**
   ```bash
   # Actualizar documentación
   echo "Tablas creadas: $(date)" >> logs/migration/fase1-completada.log
   ```

### Criterios de Éxito
- ✅ Todas las nuevas tablas creadas sin errores
- ✅ Índices configurados correctamente
- ✅ Restricciones implementadas
- ✅ Validación de estructura exitosa
- ✅ Sin impacto en tablas existentes

### Monitoreo Durante Fase
- **CPU y memoria**: Monitor de base de datos
- **Conexiones activas**: `SELECT * FROM pg_stat_activity;`
- **Logs de PostgreSQL**: `/var/log/postgresql/postgresql-*.log`
- **Errores**: `tail -f logs/migration/fase1.log`

### Rollback Plan
```bash
# Si algo sale mal, eliminar tablas nuevas
DROP TABLE IF EXISTS tareas_programadas CASCADE;
DROP TABLE IF EXISTS sesiones CASCADE;
DROP TABLE IF EXISTS mensajes CASCADE;
DROP TABLE IF EXISTS solicitudes_servicio CASCADE;
DROP TABLE IF EXISTS servicios_proveedor CASCADE;
DROP TABLE IF EXISTS proveedor_profesiones CASCADE;
DROP TABLE IF EXISTS proveedores CASCADE;
DROP TABLE IF EXISTS profesiones CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
```

---

## 📋 Fase 2: Migración de Datos Críticos (2 noches)

### Objetivos
- Migrar datos de clientes y proveedores
- Validar integridad de datos migrados
- Minimizar impacto en operaciones

### Ventana de Mantenimiento
**Fecha**: [Por definir] + 2 días
**Horario**: 02:00 - 06:00 AM Ecuador
**Duración estimada**: 6-8 horas (2 noches)
**Impacto**: Solo lectura en sistemas afectados

### Entregables
- [ ] Datos de clientes migrados a tabla `clientes`
- [ ] Datos de proveedores migrados a tabla `proveedores`
- [ ] Profesiones y relaciones migradas
- [ ] Validación de integridad completada

### Subfase 2.1: Migración de Clientes y Profesiones (Noche 1)

#### Tareas Detalladas
1. **Backup específico**
   ```bash
   # Backup de tablas a migrar
   pg_dump $DATABASE_URL -t customers -t professions > backup_fase2a_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Migración de profesiones**
   ```sql
   -- Migrar datos de professions a profesiones
   INSERT INTO profesiones (id, nombre, especialidad, categoria, esta_activo, creado_at, actualizado_at)
   SELECT id, name, specialty, category, is_active, created_at, updated_at
   FROM professions
   ON CONFLICT (id) DO NOTHING;
   ```

3. **Migración de clientes**
   ```sql
   -- Migrar datos de customers a clientes
   INSERT INTO clientes (id, telefono, nombre_completo, ciudad, ciudad_confirmada_at, notas, creado_at, actualizado_at)
   SELECT id, phone_number, full_name, city, city_confirmed_at, COALESCE(notes, '{}')::jsonb, created_at, updated_at
   FROM customers
   ON CONFLICT (id) DO NOTHING;
   ```

4. **Validación**
   ```sql
   -- Verificar conteos
   SELECT 'customers' as original, COUNT(*) as count FROM customers
   UNION ALL
   SELECT 'clientes' as migrado, COUNT(*) as count FROM clientes;
   ```

### Subfase 2.2: Migración de Proveedores y Relaciones (Noche 2)

#### Tareas Detalladas
1. **Backup de proveedores**
   ```bash
   pg_dump $DATABASE_URL -t users -t provider_professions -t provider_services > backup_fase2b_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Migración de proveedores**
   ```sql
   -- Migrar usuarios tipo provider a proveedores
   INSERT INTO proveedores (id, telefono, nombre, email, nombre_empresa, descripcion_empresa, direccion, ciudad, pais, latitud, longitud, estado, rating, creado_at, actualizado_at)
   SELECT id, phone_number, name, email, business_name, business_description, address, city, country, latitude, longitude, status, 5.0, created_at, updated_at
   FROM users
   WHERE user_type = 'provider'
   ON CONFLICT (id) DO NOTHING;
   ```

3. **Migración de relaciones**
   ```sql
   -- Migrar provider_professions a proveedor_profesiones
   INSERT INTO proveedor_profesiones (proveedor_id, profesion_id, especialidad, anos_experiencia, certificaciones, es_principal, estado_verificacion, creado_at)
   SELECT provider_id, profession_id, specialty, COALESCE(experience_years, 0), COALESCE(certifications, '[]')::jsonb, COALESCE(is_primary, false), COALESCE(verification_status, 'pendiente'), created_at
   FROM provider_professions
   ON CONFLICT (proveedor_id, profesion_id) DO NOTHING;
   ```

### Criterios de Éxito
- ✅ Todos los datos migrados sin pérdida
- ✅ Integridad referencial mantenida
- ✅ Validación de datos exitosa
- ✅ Rendimiento aceptable
- ✅ Sin duplicación de datos

---

## 📋 Fase 3: Migración de Datos Transaccionales (1 noche)

### Objetivos
- Migrar datos de transacciones y sistemas críticos
- Actualizar configuración de servicios
- Validar funcionamiento del sistema

### Ventana de Mantenimiento
**Fecha**: [Por definir] + 4 días
**Horario**: 02:00 - 06:00 AM Ecuador
**Duración estimada**: 3-4 horas
**Impacto**: Sistema completo en modo mantenimiento

### Entregables
- [ ] Datos de sesiones migrados
- [ ] Mensajes y tareas programadas migradas
- [ ] Servicios actualizados para usar nuevas tablas
- [ ] Sistema validado y funcionando

### Tareas Detalladas

#### 1. Migración de datos transaccionales
```sql
-- Migrar sessions a sesiones
INSERT INTO sesiones (id, telefono, id_sesion, estado, codigo_qr, datos_sesion, expira_at, ultima_actividad, creado_at)
SELECT id, (SELECT phone_number FROM users WHERE id = user_id LIMIT 1), session_id, status, qr_code, COALESCE(session_data, '{}')::jsonb, expires_at, last_activity, created_at
FROM sessions
ON CONFLICT (id) DO NOTHING;

-- Migrar mensajes
INSERT INTO mensajes (id, conversacion_id, telefono, tipo_mensaje, contenido, url_media, tipo_media, respuesta_ia, estado_procesamiento, metadata, creado_at)
SELECT id, conversation_id, CASE WHEN user_id IS NOT NULL THEN (SELECT phone_number FROM users WHERE id = user_id LIMIT 1) ELSE NULL END, COALESCE(message_type, 'texto'), content, media_url, media_type, ai_response, COALESCE(processing_status, 'completado'), COALESCE(metadata, '{}')::jsonb, timestamp
FROM messages
ON CONFLICT (id) DO NOTHING;
```

#### 2. Actualización de configuración
```bash
# Actualizar variables de entorno
sed -i 's/MIGRATION_MODE=true/MIGRATION_MODE=false/' .env

# Reiniciar servicios
docker-compose down
docker-compose up -d
```

#### 3. Validación completa
```bash
# Testing de servicios
python scripts/test-services.py

# Validación de funcionalidades
python scripts/test-functionalities.py
```

### Criterios de Éxito
- ✅ Todos los datos transaccionales migrados
- ✅ Servicios actualizados y funcionando
- ✅ Testing funcional exitoso
- ✅ Sistema estable post-migración

---

## 📋 Fase 4: Actualización de Código (2-3 días)

### Objetivos
- Actualizar todos los servicios para usar nuevas tablas
- Eliminar código legacy
- Optimizar queries nuevos

### Entregables
- [ ] AI Service Clientes actualizado
- [ ] AI Service Proveedores actualizado
- [ ] WhatsApp Services actualizados
- [ ] Código legacy eliminado
- [ ] Testing completo del sistema

### Tareas por Servicio

#### AI Service Clientes
```python
# Cambios principales en main.py
# Antes:
supabase.table("customers").select("*").eq("phone_number", phone)
supabase.table("service_requests").insert({...})

# Después:
supabase.table("clientes").select("*").eq("telefono", telefono)
supabase.table("solicitudes_servicio").insert({...})
```

#### AI Service Proveedores
```python
# Cambios principales en main_proveedores.py
# Antes:
supabase.table("users").select("*").eq("user_type", "provider")
supabase.table("provider_professions").insert({...})

# Después:
supabase.table("proveedores").select("*").eq("estado", "activo")
supabase.table("proveedor_profesiones").insert({...})
```

#### WhatsApp Services
```javascript
// Cambios en SupabaseStore.js
// Actualizar referencias a tablas
const TABLE_MAPPING = {
    clientes: 'clientes',
    proveedores: 'proveedores',
    mensajes: 'mensajes',
    sesiones: 'sesiones'
};
```

### Criterios de Éxito
- ✅ Todos los servicios actualizados
- ✅ Código legacy eliminado
- ✅ Testing funcional completo
- ✅ Performance aceptable
- ✅ Documentación actualizada

---

## 📋 Fase 5: Limpieza y Estabilización (2 días)

### Objetivos
- Eliminar tablas legacy
- Optimizar rendimiento
- Documentar cambios
- Estabilizar sistema

### Entregables
- [ ] Tablas legacy eliminadas
- [ ] Optimización de queries completada
- [ ] Documentación final actualizada
- [ ] Sistema estable y optimizado
- [ ] Equipo entrenado en nueva arquitectura

### Tareas Detalladas

#### 1. Eliminación de tablas legacy
```sql
-- Eliminar solo después de validación completa
DROP TABLE IF EXISTS task_queue CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS service_requests CASCADE;
DROP TABLE IF EXISTS provider_services CASCADE;
DROP TABLE IF EXISTS provider_professions CASCADE;
DROP TABLE IF EXISTS professions CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS users CASCADE;
```

#### 2. Optimización
```sql
-- Analizar y optimizar nuevas tablas
ANALYZE clientes;
ANALYZE proveedores;
ANALYZE profesiones;
REINDEX DATABASE tinkubot;
```

#### 3. Documentación final
```bash
# Actualizar README.md
# Actualizar diagramas de arquitectura
# Crear guías de troubleshooting
# Documentar mejores prácticas
```

### Criterios de Éxito
- ✅ Sistema limpio sin tablas legacy
- ✅ Rendimiento optimizado
- ✅ Documentación completa y actualizada
- ✅ Equipo capacitado
- ✅ Sistema estable por 48 horas

---

## 📊 Métricas de Éxito

### Métricas Técnicas
- **Tiempo de inactividad**: < 4 horas totales
- **Pérdida de datos**: 0%
- **Rendimiento post-migración**: ≤ 110% del tiempo base
- **Errores post-migración**: < 1% del volumen normal

### Métricas de Negocio
- **Impacto en usuarios**: Mínimo (< 5% de quejas)
- **Operaciones afectadas**: Cero
- **Recuperación**: Completa en 24 horas
- **Satisfacción del equipo**: ≥ 90%

---

## 🚨 Plan de Comunicación

### Pre-Migración (7 días antes)
- **Stakeholders**: Presentación del plan
- **Equipo técnico**: Sesión de entrenamiento
- **Usuarios**: Notificación 48 horas antes

### Durante Migración
- **Status updates**: Cada 2 horas
- **Incidentes**: Comunicación inmediata
- **Rollback**: Notificación automática

### Post-Migración
- **Resumen**: 24 horas después
- **Lecciones aprendidas**: 1 semana después
- **Mejoras**: Plan continuo

---

## 📞 Contactos y Soporte

### Equipo de Migración
- **Líder técnico**: [Nombre] - [contacto]
- **DBA**: [Nombre] - [contacto]
- **DevOps**: [Nombre] - [contacto]
- **Testing**: [Nombre] - [contacto]

### Canales de Comunicación
- **Slack**: #migration-channel
- **Email**: migration@tinkubot.com
- **Telegram**: Grupo de emergencia
- **Llamada**: Solo para incidentes críticos

---

## 📋 Checklist General

### Pre-Migración
- [ ] Plan aprobado
- [ ] Equipo asignado
- [ ] Entorno preparado
- [ ] Backup completo
- [ ] Scripts listos
- [ ] Testing completado
- [ ] Comunicación enviada

### Durante Cada Fase
- [ ] Backup específico realizado
- [ ] Fase ejecutada según plan
- [ ] Validación completada
- [ ] Equipo notificado
- [ ] Logs registrados

### Post-Migración
- [ ] Sistema estable
- [ ] Performance aceptable
- [ ] Testing funcional completo
- [ ] Documentación actualizada
- [ ] Equipo capacitado
- [ ] Lecciones documentadas

---

**Nota**: Este plan debe ser adaptado según las condiciones específicas del entorno y los requerimientos del negocio. Cada fase puede ser dividida o combinada según sea necesario para minimizar impacto.