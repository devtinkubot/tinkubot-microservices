# Guía Técnica: Migración de Datos

## 🎯 Objetivo

Proporcionar una guía detallada paso a paso para migrar los datos de las tablas actuales a la nueva arquitectura en español, garantizando la integridad y consistencia de los datos.

## 📋 Requisitos Previos

### 1. Backup Completo
```bash
# Backup de la base de datos completa
pg_dump $DATABASE_URL > backup_pre_migracion_$(date +%Y%m%d_%H%M%S).sql

# Backup específico de tablas críticas
pg_dump $DATABASE_URL -t users -t customers -t professions -t provider_professions -t provider_services -t service_requests -t messages -t sessions -t task_queue > backup_tablas_criticas_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Herramientas Necesarias
- Acceso a Supabase con permisos de administrador
- `psql` cliente instalado
- Python 3.8+ con `psycopg2` para scripts
- Espacio suficiente para backups (2x el tamaño actual)

### 3. Verificación de Pre-Migración
```sql
-- Verificar estado actual de las tablas
SELECT
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

## 🔄 Estrategia de Migración

### Fase 1: Creación de Nuevas Tablas

#### 1.1. Crear Tablas en Español
```sql
-- ============================================
-- TABLA: clientes
-- ============================================
CREATE TABLE clientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telefono VARCHAR(20) UNIQUE NOT NULL,
    nombre_completo VARCHAR(255) NOT NULL,
    ciudad VARCHAR(100),
    ciudad_confirmada_at TIMESTAMP,
    notas JSONB DEFAULT '{}',
    estado VARCHAR(20) DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'suspendido')),
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para clientes
CREATE INDEX idx_clientes_telefono ON clientes(telefono);
CREATE INDEX idx_clientes_ciudad ON clientes(ciudad);
CREATE INDEX idx_clientes_estado ON clientes(estado);
CREATE INDEX idx_clientes_creado_at ON clientes(creado_at);

-- ============================================
-- TABLA: proveedores
-- ============================================
CREATE TABLE proveedores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telefono VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    nombre_empresa VARCHAR(255),
    descripcion_empresa TEXT,
    direccion TEXT,
    ciudad VARCHAR(100),
    pais VARCHAR(100) DEFAULT 'ECUADOR',
    latitud DECIMAL(10, 8),
    longitud DECIMAL(11, 8),
    estado VARCHAR(20) DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'suspendido', 'verificacion_pendiente')),
    nivel_verificacion VARCHAR(20) DEFAULT 'basico' CHECK (nivel_verificacion IN ('basico', 'verificado', 'premium', 'institucional')),
    rating DECIMAL(3, 2) DEFAULT 5.0 CHECK (rating >= 0 AND rating <= 5),
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para proveedores
CREATE INDEX idx_proveedores_telefono ON proveedores(telefono);
CREATE INDEX idx_proveedores_ciudad ON proveedores(ciudad);
CREATE INDEX idx_proveedores_estado ON proveedores(estado);
CREATE INDEX idx_proveedores_rating ON proveedores(rating);
CREATE INDEX idx_proveedores_nivel_verificacion ON proveedores(nivel_verificacion);
CREATE INDEX idx_proveedores_creado_at ON proveedores(creado_at);

-- ============================================
-- TABLA: profesiones
-- ============================================
CREATE TABLE profesiones (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    especialidad VARCHAR(255),
    categoria VARCHAR(100),
    esta_activo BOOLEAN DEFAULT true,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para profesiones
CREATE INDEX idx_profesiones_nombre ON profesiones(nombre);
CREATE INDEX idx_profesiones_categoria ON profesiones(categoria);
CREATE INDEX idx_profesiones_activa ON profesiones(esta_activo);

-- ============================================
-- TABLA: proveedor_profesiones
-- ============================================
CREATE TABLE proveedor_profesiones (
    id SERIAL PRIMARY KEY,
    proveedor_id UUID REFERENCES proveedores(id) ON DELETE CASCADE,
    profesion_id INTEGER REFERENCES profesiones(id) ON DELETE CASCADE,
    especialidad VARCHAR(255),
    anos_experiencia INTEGER DEFAULT 0 CHECK (anos_experiencia >= 0 AND anos_experiencia <= 70),
    certificaciones JSONB DEFAULT '[]',
    es_principal BOOLEAN DEFAULT false,
    estado_verificacion VARCHAR(20) DEFAULT 'pendiente' CHECK (estado_verificacion IN ('pendiente', 'verificada', 'rechazada')),
    creado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para proveedor_profesiones
CREATE INDEX idx_proveedor_profesiones_proveedor ON proveedor_profesiones(proveedor_id);
CREATE INDEX idx_proveedor_profesiones_profesion ON proveedor_profesiones(profesion_id);
CREATE INDEX idx_proveedor_profesiones_verificacion ON proveedor_profesiones(estado_verificacion);

-- ============================================
-- TABLA: servicios_proveedor
-- ============================================
CREATE TABLE servicios_proveedor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proveedor_id UUID REFERENCES proveedores(id) ON DELETE CASCADE,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(100),
    precio DECIMAL(10, 2),
    tipo_precio VARCHAR(20) DEFAULT 'fijo' CHECK (tipo_precio IN ('fijo', 'rango', 'a_convenir', 'hora')),
    disponibilidad JSONB DEFAULT '{}',
    esta_activo BOOLEAN DEFAULT true,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para servicios_proveedor
CREATE INDEX idx_servicios_proveedor_proveedor ON servicios_proveedor(proveedor_id);
CREATE INDEX idx_servicios_proveedor_categoria ON servicios_proveedor(categoria);
CREATE INDEX idx_servicios_proveedor_activo ON servicios_proveedor(esta_activo);

-- ============================================
-- TABLA: solicitudes_servicio
-- ============================================
CREATE TABLE solicitudes_servicio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID REFERENCES clientes(id) ON DELETE SET NULL,
    telefono VARCHAR(20) NOT NULL,
    tipo_solicitud VARCHAR(50) DEFAULT 'servicio' CHECK (tipo_solicitud IN ('servicio', 'consulta', 'queja', 'sugerencia')),
    profesion_solicitada VARCHAR(100),
    ciudad VARCHAR(100),
    latitud DECIMAL(10, 8),
    longitud DECIMAL(11, 8),
    proveedores_sugeridos JSONB DEFAULT '[]',
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_progreso', 'resuelta', 'cancelada')),
    solicitado_at TIMESTAMP DEFAULT NOW(),
    resuelto_at TIMESTAMP
);

-- Índices para solicitudes_servicio
CREATE INDEX idx_solicitudes_servicio_cliente ON solicitudes_servicio(cliente_id);
CREATE INDEX idx_solicitudes_servicio_telefono ON solicitudes_servicio(telefono);
CREATE INDEX idx_solicitudes_servicio_estado ON solicitudes_servicio(estado);
CREATE INDEX idx_solicitudes_servicio_ciudad ON solicitudes_servicio(ciudad);
CREATE INDEX idx_solicitudes_servicio_solicitado_at ON solicitudes_servicio(solicitado_at);

-- ============================================
-- TABLA: mensajes
-- ============================================
CREATE TABLE mensajes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversacion_id UUID,
    telefono VARCHAR(20) NOT NULL,
    tipo_mensaje VARCHAR(50) NOT NULL CHECK (tipo_mensaje IN ('texto', 'imagen', 'audio', 'video', 'documento', 'ubicacion', 'contacto')),
    contenido TEXT NOT NULL,
    url_media VARCHAR(500),
    tipo_media VARCHAR(20),
    respuesta_ia TEXT,
    estado_procesamiento VARCHAR(20) DEFAULT 'pendiente' CHECK (estado_procesamiento IN ('pendiente', 'procesando', 'completado', 'error')),
    metadata JSONB DEFAULT '{}',
    creado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para mensajes
CREATE INDEX idx_mensajes_conversacion ON mensajes(conversacion_id);
CREATE INDEX idx_mensajes_telefono ON mensajes(telefono);
CREATE INDEX idx_mensajes_tipo ON mensajes(tipo_mensaje);
CREATE INDEX idx_mensajes_estado ON mensajes(estado_procesamiento);
CREATE INDEX idx_mensajes_creado_at ON mensajes(creado_at);

-- ============================================
-- TABLA: sesiones
-- ============================================
CREATE TABLE sesiones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telefono VARCHAR(20) NOT NULL,
    id_sesion VARCHAR(255) NOT NULL,
    estado VARCHAR(20) DEFAULT 'activa' CHECK (estado IN ('activa', 'inactiva', 'expirada', 'error')),
    codigo_qr TEXT,
    datos_sesion JSONB DEFAULT '{}',
    expira_at TIMESTAMP,
    ultima_actividad TIMESTAMP DEFAULT NOW(),
    creado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para sesiones
CREATE INDEX idx_sesiones_telefono ON sesiones(telefono);
CREATE INDEX idx_sesiones_id_sesion ON sesiones(id_sesion);
CREATE INDEX idx_sesiones_estado ON sesiones(estado);
CREATE INDEX idx_sesiones_expira_at ON sesiones(expira_at);
CREATE INDEX idx_sesiones_ultima_actividad ON sesiones(ultima_actividad);

-- ============================================
-- TABLA: tareas_programadas
-- ============================================
CREATE TABLE tareas_programadas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_tarea VARCHAR(50) NOT NULL CHECK (tipo_tarea IN ('enviar_whatsapp', 'recordatorio', 'seguimiento', 'feedback', 'notificacion')),
    payload JSONB NOT NULL,
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_progreso', 'completada', 'fallida', 'cancelada')),
    prioridad INTEGER DEFAULT 0 CHECK (prioridad >= 0 AND prioridad <= 10),
    programada_at TIMESTAMP NOT NULL,
    iniciada_at TIMESTAMP,
    completada_at TIMESTAMP,
    mensaje_error TEXT,
    intentos INTEGER DEFAULT 0 CHECK (intentos >= 0),
    max_intentos INTEGER DEFAULT 3 CHECK (max_intentos > 0),
    creado_at TIMESTAMP DEFAULT NOW()
);

-- Índices para tareas_programadas
CREATE INDEX idx_tareas_programadas_estado ON tareas_programadas(estado);
CREATE INDEX idx_tareas_programadas_tipo ON tareas_programadas(tipo_tarea);
CREATE INDEX idx_tareas_programadas_programada_at ON tareas_programadas(programada_at);
CREATE INDEX idx_tareas_programadas_prioridad ON tareas_programadas(prioridad);
```

### Fase 2: Migración de Datos

#### 2.1. Migrar Profesiones
```sql
-- Migrar datos de professions a profesiones
INSERT INTO profesiones (id, nombre, especialidad, categoria, esta_activo, creado_at, actualizado_at)
SELECT
    id,
    name,
    specialty,
    category,
    is_active,
    created_at,
    updated_at
FROM professions
ON CONFLICT (id) DO NOTHING;
```

#### 2.2. Migrar Clientes
```sql
-- Migrar datos de customers a clientes
INSERT INTO clientes (id, telefono, nombre_completo, ciudad, ciudad_confirmada_at, notas, creado_at, actualizado_at)
SELECT
    id,
    phone_number,
    full_name,
    city,
    city_confirmed_at,
    COALESCE(notes, '{}')::jsonb,
    created_at,
    updated_at
FROM customers
ON CONFLICT (id) DO NOTHING;

-- Para customers sin ID único, generar nuevos IDs
INSERT INTO clientes (telefono, nombre_completo, ciudad, ciudad_confirmada_at, notas, creado_at, actualizado_at)
SELECT
    phone_number,
    full_name,
    city,
    city_confirmed_at,
    COALESCE(notes, '{}')::jsonb,
    created_at,
    updated_at
FROM customers
WHERE id IS NULL
ON CONFLICT (telefono) DO NOTHING;
```

#### 2.3. Migrar Proveedores
```sql
-- Migrar usuarios tipo provider a proveedores
INSERT INTO proveedores (id, telefono, nombre, email, nombre_empresa, descripcion_empresa, direccion, ciudad, pais, latitud, longitud, estado, rating, creado_at, actualizado_at)
SELECT
    id,
    phone_number,
    name,
    email,
    business_name,
    business_description,
    address,
    city,
    country,
    latitude,
    longitude,
    status,
    5.0, -- Rating default ya que no existe en users
    created_at,
    updated_at
FROM users
WHERE user_type = 'provider'
ON CONFLICT (id) DO NOTHING;
```

#### 2.4. Migrar Relaciones Proveedor-Profesión
```sql
-- Migrar provider_professions a proveedor_profesiones
INSERT INTO proveedor_profesiones (proveedor_id, profesion_id, especialidad, anos_experiencia, certificaciones, es_principal, estado_verificacion, creado_at)
SELECT
    provider_id,
    profession_id,
    specialty,
    COALESCE(experience_years, 0),
    COALESCE(certifications, '[]')::jsonb,
    COALESCE(is_primary, false),
    COALESCE(verification_status, 'pendiente'),
    created_at
FROM provider_professions
ON CONFLICT (proveedor_id, profesion_id) DO NOTHING;
```

#### 2.5. Migrar Servicios de Proveedores
```sql
-- Migrar provider_services a servicios_proveedor
INSERT INTO servicios_proveedor (id, proveedor_id, titulo, descripcion, categoria, precio, tipo_precio, disponibilidad, esta_activo, creado_at, actualizado_at)
SELECT
    id,
    provider_id,
    title,
    description,
    category,
    price,
    COALESCE(price_type, 'fijo'),
    COALESCE(availability, '{}')::jsonb,
    is_active,
    created_at,
    updated_at
FROM provider_services
ON CONFLICT (id) DO NOTHING;
```

#### 2.6. Migrar Solicitudes de Servicio
```sql
-- Migrar service_requests a solicitudes_servicio
INSERT INTO solicitudes_servicio (cliente_id, telefono, tipo_solicitud, profesion_solicitada, ciudad, latitud, longitud, proveedores_sugeridos, estado, solicitado_at, resuelto_at)
SELECT
    -- Buscar cliente_id desde la nueva tabla clientes usando phone_number
    (SELECT id FROM clientes WHERE telefono = service_requests.phone_number LIMIT 1),
    phone_number,
    'servicio',
    profession,
    location_city,
    location_lat,
    location_lng,
    COALESCE(suggested_providers, '[]')::jsonb,
    CASE
        WHEN resolved_at IS NOT NULL THEN 'resuelta'
        ELSE 'pendiente'
    END,
    requested_at,
    resolved_at
FROM service_requests
ON CONFLICT DO NOTHING;
```

#### 2.7. Migrar Mensajes
```sql
-- Migrar messages a mensajes
INSERT INTO mensajes (id, conversacion_id, telefono, tipo_mensaje, contenido, url_media, tipo_media, respuesta_ia, estado_procesamiento, metadata, creado_at)
SELECT
    id,
    conversation_id,
    -- Normalizar teléfono para mensajes
    CASE
        WHEN user_id IS NOT NULL THEN (SELECT phone_number FROM users WHERE id = user_id LIMIT 1)
        ELSE NULL
    END,
    COALESCE(message_type, 'texto'),
    content,
    media_url,
    media_type,
    ai_response,
    COALESCE(processing_status, 'completado'),
    COALESCE(metadata, '{}')::jsonb,
    timestamp
FROM messages
WHERE id IS NOT NULL
ON CONFLICT (id) DO NOTHING;
```

#### 2.8. Migrar Sesiones
```sql
-- Migrar sessions a sesiones
INSERT INTO sesiones (id, telefono, id_sesion, estado, codigo_qr, datos_sesion, expira_at, ultima_actividad, creado_at)
SELECT
    id,
    -- Obtener teléfono desde user_id
    (SELECT phone_number FROM users WHERE id = user_id LIMIT 1),
    session_id,
    status,
    qr_code,
    COALESCE(session_data, '{}')::jsonb,
    expires_at,
    last_activity,
    created_at
FROM sessions
ON CONFLICT (id) DO NOTHING;
```

#### 2.9. Migrar Tareas Programadas
```sql
-- Migrar task_queue a tareas_programadas
INSERT INTO tareas_programadas (id, tipo_tarea, payload, estado, prioridad, programada_at, iniciada_at, completada_at, mensaje_error, intentos, max_intentos, creado_at)
SELECT
    id,
    task_type,
    COALESCE(payload, '{}')::jsonb,
    status,
    COALESCE(priority, 0),
    scheduled_at,
    started_at,
    completed_at,
    error_message,
    COALESCE(retry_count, 0),
    COALESCE(max_retries, 3),
    created_at
FROM task_queue
ON CONFLICT (id) DO NOTHING;
```

### Fase 3: Validación de Datos Migrados

#### 3.1. Verificar Integridad
```sql
-- Verificar conteos de registros
SELECT
    'customers' as tabla_original,
    COUNT(*) as registros_originales
FROM customers
UNION ALL
SELECT
    'clientes' as tabla_nueva,
    COUNT(*) as registros_migrados
FROM clientes;

-- Verificar integridad de proveedores
SELECT
    'users (provider)' as tabla_original,
    COUNT(*) as registros_originales
FROM users
WHERE user_type = 'provider'
UNION ALL
SELECT
    'proveedores' as tabla_nueva,
    COUNT(*) as registros_migrados
FROM proveedores;

-- Verificar relaciones
SELECT
    pp.provider_id,
    p.nombre as proveedor_nombre,
    pr.nombre as profesion_nombre
FROM proveedor_profesiones pp
JOIN proveedores p ON pp.proveedor_id = p.id
JOIN profesiones pr ON pp.profesion_id = pr.id
LIMIT 10;
```

#### 3.2. Validar Datos Críticos
```sql
-- Validar teléfonos únicos
SELECT telefono, COUNT(*) as duplicados
FROM clientes
GROUP BY telefono
HAVING COUNT(*) > 1;

SELECT telefono, COUNT(*) as duplicados
FROM proveedores
GROUP BY telefono
HAVING COUNT(*) > 1;

-- Validar referencias
SELECT 'clientes sin teléfono válido' as issue, COUNT(*) as count
FROM clientes
WHERE telefono IS NULL OR telefono = '';

SELECT 'proveedores sin teléfono válido' as issue, COUNT(*) as count
FROM proveedores
WHERE telefono IS NULL OR telefono = '';
```

### Fase 4: Scripts de Migración Automatizada

#### 4.1. Script Python para Migración
```python
# migracion_datos.py
import psycopg2
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.conn = None

    def connect(self):
        """Establecer conexión a la base de datos"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            logger.info("✅ Conectado a la base de datos")
        except Exception as e:
            logger.error(f"❌ Error conectando a la base de datos: {e}")
            raise

    def disconnect(self):
        """Cerrar conexión"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Conexión cerrada")

    def execute_query(self, query, params=None):
        """Ejecutar query SQL"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params or ())
                self.conn.commit()
                logger.info(f"✅ Query ejecutado: {query[:50]}...")
                return cur
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Error ejecutando query: {e}")
            raise

    def backup_table(self, table_name):
        """Crear backup de una tabla específica"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_query = f"CREATE TABLE backup_{table_name}_{timestamp} AS SELECT * FROM {table_name}"
        self.execute_query(backup_query)
        logger.info(f"💾 Backup creado para tabla {table_name}")

    def migrate_customers(self):
        """Migrar tabla customers a clientes"""
        logger.info("🔄 Iniciando migración de customers a clientes...")

        # Backup
        self.backup_table('customers')

        # Migración
        migrate_query = """
        INSERT INTO clientes (id, telefono, nombre_completo, ciudad, ciudad_confirmada_at, notas, creado_at, actualizado_at)
        SELECT
            id,
            phone_number,
            full_name,
            city,
            city_confirmed_at,
            COALESCE(notes, '{}')::jsonb,
            created_at,
            updated_at
        FROM customers
        ON CONFLICT (id) DO NOTHING
        """

        self.execute_query(migrate_query)

        # Verificación
        result = self.execute_query("SELECT COUNT(*) FROM clientes").fetchone()
        logger.info(f"✅ Migración customers completada: {result[0]} registros")

    def migrate_providers(self):
        """Migrar proveedores desde users"""
        logger.info("🔄 Iniciando migración de proveedores...")

        # Backup
        self.backup_table('users')

        # Migración
        migrate_query = """
        INSERT INTO proveedores (id, telefono, nombre, email, nombre_empresa, descripcion_empresa, direccion, ciudad, pais, latitud, longitud, estado, rating, creado_at, actualizado_at)
        SELECT
            id,
            phone_number,
            name,
            email,
            business_name,
            business_description,
            address,
            city,
            country,
            latitude,
            longitude,
            status,
            5.0,
            created_at,
            updated_at
        FROM users
        WHERE user_type = 'provider'
        ON CONFLICT (id) DO NOTHING
        """

        self.execute_query(migrate_query)

        # Verificación
        result = self.execute_query("SELECT COUNT(*) FROM proveedores").fetchone()
        logger.info(f"✅ Migración proveedores completada: {result[0]} registros")

    def run_full_migration(self):
        """Ejecutar migración completa"""
        try:
            self.connect()

            # 1. Crear tablas nuevas (ejecutar SQL manualmente primero)
            logger.info("🏗️ Asegúrese de haber ejecutado el script de creación de tablas")

            # 2. Migrar datos
            self.migrate_customers()
            self.migrate_providers()

            # 3. Validar migración
            self.validate_migration()

            logger.info("🎉 Migración completada exitosamente!")

        except Exception as e:
            logger.error(f"❌ Error en migración: {e}")
            raise
        finally:
            self.disconnect()

    def validate_migration(self):
        """Validar que la migración fue exitosa"""
        logger.info("🔍 Validando migración...")

        # Verificar que no hay datos duplicados
        queries = [
            ("clientes", "SELECT telefono, COUNT(*) FROM clientes GROUP BY telefono HAVING COUNT(*) > 1"),
            ("proveedores", "SELECT telefono, COUNT(*) FROM proveedores GROUP BY telefono HAVING COUNT(*) > 1")
        ]

        for table, query in queries:
            result = self.execute_query(query).fetchall()
            if result:
                logger.warning(f"⚠️ Se encontraron duplicados en {table}: {len(result)} registros")
            else:
                logger.info(f"✅ No hay duplicados en {table}")

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    migrator.run_full_migration()
```

### Fase 5: Testing y Validación

#### 5.1. Queries de Validación
```sql
-- Test 1: Verificar integridad de datos migrados
SELECT
    'clientes' as tabla,
    COUNT(*) as total_registros,
    COUNT(CASE WHEN telefono IS NOT NULL THEN 1 END) as con_telefono,
    COUNT(CASE WHEN nombre_completo IS NOT NULL THEN 1 END) as con_nombre
FROM clientes
UNION ALL
SELECT
    'proveedores' as tabla,
    COUNT(*) as total_registros,
    COUNT(CASE WHEN telefono IS NOT NULL THEN 1 END) as con_telefono,
    COUNT(CASE WHEN nombre IS NOT NULL THEN 1 END) as con_nombre
FROM proveedores;

-- Test 2: Verificar relaciones
SELECT
    'proveedor_profesiones' as relacion,
    COUNT(*) as total,
    COUNT(DISTINCT proveedor_id) as proveedores_unicos,
    COUNT(DISTINCT profesion_id) as profesiones_unicas
FROM proveedor_profesiones;

-- Test 3: Verificar datos críticos
SELECT
    telefono,
    nombre,
    ciudad,
    estado
FROM proveedores
WHERE rating < 4.0
ORDER BY rating ASC
LIMIT 5;
```

## ⚠️ Consideraciones de Rendimiento

### Durante la Migración
1. **Ejecutar en horario de bajo uso**: Preferiblemente en madrugada o fin de semana
2. **Monitorear recursos**: CPU, memoria y conexiones a la base de datos
3. **Transacciones por lotes**: Para tablas grandes, procesar en lotes de 1000 registros
4. **Timeout extendido**: Aumentar timeouts de conexión durante la migración

### Optimización Post-Migración
```sql
-- Analizar y optimizar tablas nuevas
ANALYZE clientes;
ANALYZE proveedores;
ANALYZE profesiones;
ANALYZE proveedor_profesiones;
ANALYZE servicios_proveedor;
ANALYZE solicitudes_servicio;
ANALYZE mensajes;
ANALYZE sesiones;
ANALYZE tareas_programadas;

-- Rebuild índices si es necesario
REINDEX TABLE clientes;
REINDEX TABLE proveedores;
```

## 🚨 Rollback Plan

### Scripts de Reversión
```sql
-- Eliminar tablas nuevas si algo sale mal
DROP TABLE IF EXISTS tareas_programadas CASCADE;
DROP TABLE IF EXISTS sesiones CASCADE;
DROP TABLE IF EXISTS mensajes CASCADE;
DROP TABLE IF EXISTS solicitudes_servicio CASCADE;
DROP TABLE IF EXISTS servicios_proveedor CASCADE;
DROP TABLE IF EXISTS proveedor_profesiones CASCADE;
DROP TABLE IF EXISTS proveedores CASCADE;
DROP TABLE IF EXISTS profesiones CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;

-- Restaurar desde backup si es necesario
-- \i backup_pre_migracion_YYYYMMDD_HHMMSS.sql
```

## 📋 Checklist de Validación

- [ ] Backup completo realizado
- [ ] Tablas nuevas creadas correctamente
- [ ] Datos migrados sin pérdida
- [ ] Referencias y relaciones intactas
- [ ] Índices creados y funcionando
- [ ] Queries de validación pasando
- [ ] Performance aceptable
- [ ] Documentación actualizada
- [ ] Equipo notificado del cambio
- [ ] Plan de comunicación preparado

## 🎞️ Comandos Útiles

```bash
# Verificar tamaño de tablas
psql $DATABASE_URL -c "\dt+"

# Monitorear migración en tiempo real
watch -n 5 "psql $DATABASE_URL -c 'SELECT COUNT(*) FROM clientes; SELECT COUNT(*) FROM proveedores'"

# Verificar conexiones activas
psql $DATABASE_URL -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Monitorear logs de PostgreSQL
tail -f /var/log/postgresql/postgresql-*.log
```

---

**Importante**: Esta guía debe ser ejecutada por personal técnico con experiencia en administración de bases de datos PostgreSQL. Siempre realizar pruebas en un ambiente de staging antes de ejecutar en producción.