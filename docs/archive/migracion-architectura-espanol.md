# Propuesta de Migración: Arquitectura en Español

## 📋 Resumen Ejecutivo

Este documento presenta una propuesta estratégica para migrar la arquitectura de base de datos actual de TinkuBot a nombres en español, alineando la tecnología con el modelo de negocio y facilitando la escalabilidad futura con instituciones y partners comerciales.

## 🎯 Objetivos

### Objetivo Principal
Estandarizar la nomenclatura de la base de datos en español para reflejar el modelo de negocio de TinkuBot y facilitar la comprensión y mantenimiento del sistema.

### Objetivos Secundarios
- Simplificar el modelo de datos actual
- Mejorar la claridad entre clientes y proveedores
- Preparar la arquitectura para integraciones institucionales
- Reducir la complejidad en el código

## 🔍 Análisis del Estado Actual

### Arquitectura Actual
```sql
-- Tablas Principales (Inglés)
users (user_type: 'provider' | 'client')  -- ⚠️ Ambigüedad
customers                                  -- ⚠️ Duplicidad con users
professions
provider_professions
provider_services
service_requests
messages
sessions
task_queue
```

### Problemas Identificados

#### 1. **Ambigüedad en el Modelo de Usuarios**
- `users.user_type = 'provider'` vs tabla `customers` separada
- Dos entidades representando el mismo concepto (cliente)
- Duplicidad de datos y lógica

#### 2. **Complejidad en Consultas**
```python
# Código actual - Complejidad innecesaria
customer_profile = get_or_create_customer(phone=phone)          # Tabla customers
provider_user_id = await supabase_find_or_create_user_provider() # Tabla users
```

#### 3. **Mantenimiento Dificultoso**
- Nombres en inglés para un negocio hispanohablante
- Conceptos poco claros para nuevos desarrolladores
- Documentación confusa

## 🏗️ Propuesta de Nueva Arquitectura

### Modelo de Negocio Reflejado en la Base de Datos

#### **Clientes (B2C) - Flujo Simple**
```sql
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
```

#### **Proveedores (B2B) - Perfil Completo**
```sql
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
    estado VARCHAR(20) DEFAULT 'activo',
    nivel_verificacion VARCHAR(20) DEFAULT 'basico',
    rating DECIMAL(3, 2) DEFAULT 5.0,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);
```

### Mapeo Completo de Tablas

| Tabla Actual | Tabla Propuesta | Justificación |
|-------------|-----------------|---------------|
| `users` (user_type='provider') | `proveedores` | Especialización para proveedores |
| `customers` | `clientes` | Simplificación para clientes |
| `professions` | `profesiones` | Claridad lingüística |
| `provider_professions` | `proveedor_profesiones` | Relación clara |
| `provider_services` | `servicios_proveedor` | Servicios específicos |
| `service_requests` | `solicitudes_servicio` | Claridad del concepto |
| `messages` | `mensajes` | Idioma consistente |
| `sessions` | `sesiones` | Idioma consistente |
| `task_queue` | `tareas_programadas` | Claridad funcional |

### Estructura Detallada Propuesta

#### 1. **clientes**
```sql
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

-- Índices
CREATE INDEX idx_clientes_telefono ON clientes(telefono);
CREATE INDEX idx_clientes_ciudad ON clientes(ciudad);
CREATE INDEX idx_clientes_estado ON clientes(estado);
```

#### 2. **proveedores**
```sql
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
    estado VARCHAR(20) DEFAULT 'activo',
    nivel_verificacion VARCHAR(20) DEFAULT 'basico',
    rating DECIMAL(3, 2) DEFAULT 5.0,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_proveedores_telefono ON proveedores(telefono);
CREATE INDEX idx_proveedores_ciudad ON proveedores(ciudad);
CREATE INDEX idx_proveedores_estado ON proveedores(estado);
CREATE INDEX idx_proveedores_rating ON proveedores(rating);
```

#### 3. **profesiones**
```sql
CREATE TABLE profesiones (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    especialidad VARCHAR(255),
    categoria VARCHAR(100),
    esta_activo BOOLEAN DEFAULT true,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);
```

#### 4. **proveedor_profesiones**
```sql
CREATE TABLE proveedor_profesiones (
    id SERIAL PRIMARY KEY,
    proveedor_id UUID REFERENCES proveedores(id),
    profesion_id INTEGER REFERENCES profesiones(id),
    especialidad VARCHAR(255),
    anos_experiencia INTEGER DEFAULT 0,
    certificaciones JSONB DEFAULT '[]',
    es_principal BOOLEAN DEFAULT false,
    estado_verificacion VARCHAR(20) DEFAULT 'pendiente',
    creado_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_proveedor_profesiones_proveedor ON proveedor_profesiones(proveedor_id);
CREATE INDEX idx_proveedor_profesiones_profesion ON proveedor_profesiones(profesion_id);
```

#### 5. **servicios_proveedor**
```sql
CREATE TABLE servicios_proveedor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proveedor_id UUID REFERENCES proveedores(id),
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(100),
    precio DECIMAL(10, 2),
    tipo_precio VARCHAR(20) DEFAULT 'fijo', -- 'fijo', 'rango', 'a_convenir'
    disponibilidad JSONB DEFAULT '{}',
    esta_activo BOOLEAN DEFAULT true,
    creado_at TIMESTAMP DEFAULT NOW(),
    actualizado_at TIMESTAMP DEFAULT NOW()
);
```

#### 6. **solicitudes_servicio**
```sql
CREATE TABLE solicitudes_servicio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id UUID REFERENCES clientes(id),
    telefono VARCHAR(20) NOT NULL,
    tipo_solicitud VARCHAR(50) DEFAULT 'servicio',
    profesion_solicitada VARCHAR(100),
    ciudad VARCHAR(100),
    latitud DECIMAL(10, 8),
    longitud DECIMAL(11, 8),
    proveedores_sugeridos JSONB DEFAULT '[]',
    estado VARCHAR(20) DEFAULT 'pendiente',
    solicitado_at TIMESTAMP DEFAULT NOW(),
    resuelto_at TIMESTAMP
);
```

#### 7. **mensajes**
```sql
CREATE TABLE mensajes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversacion_id UUID,
    telefono VARCHAR(20) NOT NULL,
    tipo_mensaje VARCHAR(50) NOT NULL, -- 'texto', 'imagen', 'audio', etc.
    contenido TEXT NOT NULL,
    url_media VARCHAR(500),
    tipo_media VARCHAR(20),
    respuesta_ia TEXT,
    estado_procesamiento VARCHAR(20) DEFAULT 'pendiente',
    metadata JSONB DEFAULT '{}',
    creado_at TIMESTAMP DEFAULT NOW()
);
```

#### 8. **sesiones**
```sql
CREATE TABLE sesiones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telefono VARCHAR(20) NOT NULL,
    id_sesion VARCHAR(255) NOT NULL,
    estado VARCHAR(20) DEFAULT 'activa',
    codigo_qr TEXT,
    datos_sesion JSONB DEFAULT '{}',
    expira_at TIMESTAMP,
    ultima_actividad TIMESTAMP DEFAULT NOW(),
    creado_at TIMESTAMP DEFAULT NOW()
);
```

#### 9. **tareas_programadas**
```sql
CREATE TABLE tareas_programadas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_tarea VARCHAR(50) NOT NULL, -- 'enviar_whatsapp', 'recordatorio', etc.
    payload JSONB NOT NULL,
    estado VARCHAR(20) DEFAULT 'pendiente',
    prioridad INTEGER DEFAULT 0,
    programada_at TIMESTAMP NOT NULL,
    iniciada_at TIMESTAMP,
    completada_at TIMESTAMP,
    mensaje_error TEXT,
    intentos INTEGER DEFAULT 0,
    max_intentos INTEGER DEFAULT 3,
    creado_at TIMESTAMP DEFAULT NOW()
);
```

## 🚀 Beneficios de la Migración

### 1. **Claridad del Modelo de Negocio**
- Separación clara entre B2C (clientes) y B2B (proveedores)
- Nomenclatura alineada con el lenguaje del negocio
- Facilita la incorporación de nuevos desarrolladores

### 2. **Simplificación del Código**
```python
# Nuevo código - Más claro y sencillo
def get_or_create_cliente(telefono: str, **kwargs):
    return supabase.table("clientes").upsert({
        "telefono": telefono,
        **kwargs
    }).execute()

def get_or_create_proveedor(telefono: str, **kwargs):
    return supabase.table("proveedores").upsert({
        "telefono": telefono,
        **kwargs
    }).execute()
```

### 3. **Preparación para Escalabilidad**
- Estructura lista para integraciones institucionales
- Campos específicos para verificaciones y certificaciones
- Flexibilidad para diferentes niveles de partnership

### 4. **Mantenimiento Mejorado**
- Documentación más clara
- Queries más legibles
- Debugging simplificado

## 📊 Impacto en el Sistema

### Servicios Afectados

#### **Python Services**
1. **ai-service-clientes**
   - Cambios en `get_or_create_customer()` → `get_or_create_cliente()`
   - Actualización de queries a tabla `customers` → `clientes`
   - Modificación en manejo de `service_requests` → `solicitudes_servicio`

2. **ai-service-proveedores**
   - Cambios en `supabase_find_or_create_user_provider()` → `get_or_create_proveedor()`
   - Actualización de queries a `users` → `proveedores`
   - Modificación en `provider_professions` → `proveedor_profesiones`

#### **Node.js Services**
1. **whatsapp-service-clientes**
   - Actualización de referencias a tablas en español
   - Modificación en `SupabaseStore.js`

2. **whatsapp-service-proveedores**
   - Actualización de referencias a tablas en español
   - Modificación en `SupabaseStore.js`

### Consultas Críticas a Modificar

```python
# Antes
supabase.table("customers").select("*").eq("phone_number", phone)
supabase.table("users").select("*").eq("user_type", "provider")
supabase.table("service_requests").insert({...})

# Después
supabase.table("clientes").select("*").eq("telefono", telefono)
supabase.table("proveedores").select("*").eq("estado", "activo")
supabase.table("solicitudes_servicio").insert({...})
```

## ⚠️ Consideraciones y Riesgos

### Riesgos Principales
1. **Downtime durante migración**: Planificar durante horas de bajo uso
2. **Pérdida de datos**: Backup completo antes de iniciar
3. **Inconsistencias temporales**: Testing exhaustivo post-migración
4. **Rollback complejo**: Tener scripts de reversión listos

### Mitigaciones
1. **Migración por fases**: Reducir impacto y facilitar rollback
2. **Testing riguroso**: Ambiente de staging replicado
3. **Monitorización constante**: Alertas durante y después de la migración
4. **Documentación clara**: Guías paso a paso para el equipo

## 📅 Plan de Migración

Consulte el documento `docs/guias/plan-entregas.md` para el desglose detallado de fases y entregas.

## 📚 Documentación Adicional

- `docs/guias/migracion-datos.md` - Guía técnica de migración de datos
- `docs/guias/configuracion-entorno.md` - Configuración de entorno
- `docs/guias/actualizacion-codigo.md` - Cambios en código por servicio
- `docs/guias/plan-entregas.md` - Plan de entregas parciales
- `docs/guias/testing-validacion.md` - Estrategia de testing
- `docs/guias/rollback.md` - Procedimientos de reversión

## 🎯 Conclusión

Esta migración representa una inversión estratégica en la arquitectura de TinkuBot que:

- **Alinea tecnología con negocio**: Nombres claros que reflejan la realidad del sistema
- **Simplifica el mantenimiento**: Código más legible y documentación clara
- **Prepara para el crecimiento**: Estructura lista para integraciones institucionales
- **Reduce complejidad**: Eliminación de ambigüedades y duplicidades

El cambio está justificado por los beneficios a largo plazo en mantenibilidad, escalabilidad y claridad del sistema.

---

**Autor**: TinkuBot Technical Team
**Versión**: 1.0
**Fecha**: Octubre 2025
**Estado**: Propuesta para revisión y aprobación