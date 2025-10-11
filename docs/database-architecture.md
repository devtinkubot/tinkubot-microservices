# Arquitectura de Base de Datos - Estado Actual

## 📋 Resumen Ejecutivo

Este documento describe la arquitectura real de base de datos de TinkuBot implementada y funcionando, reflejando las tablas y estructuras que están actualmente en producción.

## 🏗️ Tablas Principales

### 1. `customers` - Gestión de Clientes B2C

**Propósito**: Almacenamiento de información de clientes que interactúan con el bot de WhatsApp.

**Estructura Real**:
```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    city_confirmed_at TIMESTAMP,
    has_consent BOOLEAN DEFAULT false,  -- ⚠️ Campo clave para consentimiento
    notes JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Campos Importantes**:
- `phone_number`: Identificador único del cliente
- `has_consent`: Indica si el cliente ha aceptado compartir sus datos con proveedores
- `city_confirmed_at`: Timestamp de cuando se confirmó la ciudad del cliente

### 2. `consents` - Registro Legal de Consentimientos

**Propósito**: Cumplimiento normativo para registro de consentimientos de datos.

**Estructura Real**:
```sql
CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES customers(id),
    user_type VARCHAR(20) DEFAULT 'customer',
    response VARCHAR(20) NOT NULL,  -- 'accepted' o 'declined'
    message_log JSONB NOT NULL,     -- Metadata completa del consentimiento
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Metadata de Consentimiento** (en `message_log`):
```json
{
  "consent_timestamp": "2025-01-XX...",
  "phone": "+593...",
  "message_id": "WA_MESSAGE_ID",
  "exact_response": "Sí, acepto",
  "consent_type": "provider_contact",
  "platform": "whatsapp",
  "message_type": "text",
  "device_type": "android"
}
```

### 3. `service_requests` - Registro de Solicitudes

**Propósito**: Historial de solicitudes de servicios realizadas por clientes.

**Estructura Real**:
```sql
CREATE TABLE service_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) NOT NULL,
    intent VARCHAR(50) DEFAULT 'service_request',
    profession VARCHAR(100),
    location_city VARCHAR(100),
    requested_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    suggested_providers JSONB DEFAULT '[]'
);
```

### 4. `messages` - Historial de Conversaciones

**Propósito**: Almacenamiento de mensajes intercambiados en las conversaciones.

**Estructura Real** (basada en código del servicio):
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID,
    phone VARCHAR(20) NOT NULL,
    message_type VARCHAR(50),
    content TEXT NOT NULL,
    is_bot BOOLEAN DEFAULT false,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

### 5. `task_queue` - Tareas Programadas

**Propósito**: Sistema de colas para envíos programados (feedback, recordatorios).

**Estructura Real**:
```sql
CREATE TABLE task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    scheduled_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## 🔄 Flujo de Datos Real

### 1. Flujo de Consentimiento de Clientes

```mermaid
sequenceDiagram
    participant C as Cliente
    participant WA as WhatsApp
    participant AI as AI Service Clientes
    participant DB as Supabase

    C->>WA: Envía mensaje inicial
    WA->>AI: /handle-whatsapp-message
    AI->>DB: Verifica customer.has_consent
    DB-->>AI: has_consent = false/null
    AI->>WA: Solicita consentimiento
    WA->>C: "¿Aceptas compartir tus datos?"
    C->>WA: Responde "Sí, acepto"
    WA->>AI: /handle-whatsapp-message con selección
    AI->>DB: UPDATE customers SET has_consent = true
    AI->>DB: INSERT INTO consents (metadata completa)
    AI->>WA: "✅ Gracias por aceptar"
    WA->>C: Confirmación de consentimiento
```

### 2. Flujo de Búsqueda de Proveedores

```mermaid
sequenceDiagram
    participant C as Cliente
    participant AI as AI Service Clientes
    participant P as AI Service Proveedores
    participant DB as Supabase

    C->>AI: "Necesito plomero en Quito"
    AI->>P: POST /search-providers
    P-->>AI: Lista de proveedores
    AI->>DB: INSERT INTO service_requests
    AI->>C: Presenta opciones de proveedores
    C->>AI: Selecciona proveedor
    AI->>C: Envia contacto del proveedor
    AI->>DB: INSERT INTO task_queue (feedback request)
```

## 📊 Estado Actual del Sistema

### ✅ **Implementado y Funcionando**
- ✅ Gestión de clientes con tabla `customers`
- ✅ Sistema completo de consentimiento con `consents`
- ✅ Flujo de búsqueda de proveedores activo
- ✅ Registro de solicitudes en `service_requests`
- ✅ Sistema de feedback programado
- ✅ Integración con WhatsApp Web.js

### ⚠️ **Consideraciones Técnicas**
- Las tablas mantienen nombres en inglés (`customers`, no `clientes`)
- No se implementó la migración a nombres en español
- El sistema funciona correctamente con la estructura actual

## 🚀 Servicios que Usan Cada Tabla

### `customers`
- **ai-service-clientes**: `get_or_create_customer()`, `update_customer_city()`
- **whatsapp-service-clientes**: Validación de consentimiento inicial

### `consents`
- **ai-service-clientes**: Registro de consentimientos aceptados/rechazados

### `service_requests`
- **ai-service-clientes**: Registro automático de solicitudes completadas

### `task_queue`
- **ai-service-clientes**: Programación de feedback, retry de envíos
- **whatsapp-service-clientes**: Ejecución de tareas programadas

### `messages`
- **ai-service-clientes**: Historial de conversaciones vía Redis sessions

## 🔧 Configuración del Entorno

Las variables de entorno relevantes para la base de datos:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_BACKEND_API_KEY=your_service_key
SUPABASE_BUCKET_NAME=tinkubot-sessions

# Database Connection
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

## 📋 Checklist de Validación

Para verificar que el sistema funciona correctamente:

- [ ] Los clientes nuevos reciben solicitud de consentimiento
- [ ] Los consentimientos se registran en `customers.has_consent`
- [ ] Los consentimientos se guardan en `consents` con metadata completa
- [ ] Las solicitudes de servicio registran en `service_requests`
- [ ] Los feedbacks se programan en `task_queue`
- [ ] El historial de conversaciones se mantiene accesible

---

**Última actualización**: Enero 2025
**Estado**: Documentación sincronizada con código en producción
**Próxima revisión**: Después de ciclo de QA completado