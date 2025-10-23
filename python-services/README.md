# TinkuBot Python Services

Servicios de IA de TinkuBot migrados a Python con FastAPI, Redis Pub/Sub y PostGIS.

## 🏗️ Arquitectura Actualizada

### Servicios Implementados

1. **Search Token** (Puerto 8000)
   - Búsqueda avanzada de proveedores con tokenización
   - Cache ultrarrápido con Redis
   - Múltiples estrategias de búsqueda (token-based, full-text, híbrida)

2. **AI Clientes** (Puerto 8001)
   - Procesamiento de mensajes de clientes con OpenAI
   - Entendimiento de necesidades y extracción de información
   - Coordinación con servicio de proveedores
   - ✅ **Gestión de sesiones integrada** (ahora incluye el Session Service)

3. **AI Proveedores** (Puerto 8002)
   - Búsqueda geolocalizada de proveedores con PostGIS
   - Gestión de disponibilidad y perfiles de proveedores
   - Matching basado en ubicación y habilidades

### Cambio Reciente: Eliminación del Session Service

**ANTES (5 servicios):**

```
WhatsApp Service (Node.js) → Session Service (Node.js) → AI Service (Python)
     ↓                       ↓                       ↓
   Mensaje               Guardar sesión         Procesar IA
```

**AHORA (2 servicios + WhatsApp):**

```
WhatsApp Service (Node.js) → AI Service Clientes (Python)
     ↓                       ↓
   Mensaje               Guardar sesión + Procesar IA
```

**Beneficios:**

- ✅ Menos latencia (eliminamos un salto de red)
- ✅ Menos complejidad (un servicio menos que gestionar)
- ✅ Mejor rendimiento (contexto integrado en procesamiento de IA)
- ✅ Más mantenible (menos puntos de fallo)

### Tecnologías Utilizadas

- **FastAPI**: Framework web moderno y rápido
- **AsyncIO**: Programación asíncrona para alto rendimiento
- **Redis (Upstash)**: Cache y almacenamiento temporal de flujo
- **Supabase**: Persistencia de customers, consentimientos y proveedores
- **OpenAI**: Procesamiento de lenguaje natural
- **httpx**: Cliente HTTP asíncrono para comunicarse con otros servicios

## 🚀 Instalación y Configuración

### Requisitos Previos

- Python 3.11+
- PostgreSQL con extensión PostGIS
- Cuenta de Upstash Redis
- API Key de OpenAI

### Configuración Inicial

1. **Clonar el repositorio**

   ```bash
   cd python-services
   ```

2. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

### Variables de Entorno Requeridas

```bash
# OpenAI
OPENAI_API_KEY=tu-api-key-aqui

# Supabase/PostgreSQL
SUPABASE_URL=tu-supabase-url
SUPABASE_SERVICE_KEY=tu-service-key
DATABASE_URL=postgresql://usuario:password@host:puerto/basedatos

# Redis Upstash (Pub/Sub y Cache)
REDIS_URL=rediss://:password@host:puerto

# Puertos de servicios
CLIENTES_SERVICE_PORT=5001
PROVEEDORES_SERVICE_PORT=5002
```

## 🏃‍♂️ Ejecución

### Método Recomendado: Docker Compose

```bash
# Iniciar todos los servicios Python
docker compose up -d search-token ai-clientes ai-proveedores

# Verificar estado
docker compose ps
```

### Desarrollo Local (sin Docker)

Si prefieres desarrollar localmente sin Docker, cada servicio tiene sus propias dependencias:

**Search Token**

```bash
cd search-token
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**AI Clientes**

```bash
cd ai-clientes
pip install -r requirements.txt
python main.py
```

**AI Proveedores**

```bash
cd ai-proveedores
pip install -r requirements.txt
python main.py
```

### Verificar Estado

```bash
# Search Token
curl http://localhost:8000/health

# AI Clientes
curl http://localhost:8001/health

# AI Proveedores
curl http://localhost:8002/health
```

## 🔍 Validación de Calidad Local

**IMPORTANTE**: Antes de subir cualquier cambio a GitHub, debes ejecutar la validación de calidad local.

### Flujo de Trabajo Recomendado

1. **Hacer cambios en el código**
2. **Ejecutar validación de calidad** (obligatorio)
3. **Si todo está OK**: Hacer commit y push a GitHub
4. **Si hay errores**: Corregir y repetir desde paso 2

### Ejecutar Validación de Calidad

```bash
# Validar todos los servicios (recomendado)
python validate_quality.py

# Validar solo un servicio específico
python validate_quality.py --service ai-clientes

# Validar y corregir automáticamente (formato e importaciones)
python validate_quality.py --fix
```

### Herramientas de Validación Incluidas

El script de validación ejecuta automáticamente:

- **📝 Black**: Formato automático de código
- **📦 isort**: Ordenamiento de importaciones
- **🔍 Flake8**: Linting y estilo de código
- **🔧 MyPy**: Verificación de tipos estáticos
- **🔒 Bandit**: Análisis de seguridad
- **🐍 Python**: Validación de sintaxis básica

### Configuración de Herramientas

Las herramientas utilizan archivos de configuración locales:
- `.flake8` - Configuración de Flake8
- `.mypy.ini` - Configuración de MyPy
- `pyproject.toml` - Configuración de Black, isort y Bandit

**Nota**: Estos archivos son para uso local y no se deben subir a GitHub.

## 📚 API Documentation

### AI Service Clientes (Puerto 5001)

#### Endpoints

- `GET /` - Información del servicio
- `GET /health` - Health check
- `POST /process-message` - Procesar mensaje con IA
- `POST /handle-whatsapp-message` - Manejar mensaje de WhatsApp

#### Endpoints de Sesiones (compatibles con Session Service anterior)

- `POST /sessions` - Guardar mensaje en sesión
- `GET /sessions/{phone}` - Obtener historial de conversación
- `DELETE /sessions/{phone}` - Eliminar sesiones de usuario
- `GET /sessions/stats` - Obtener estadísticas de sesiones

#### Ejemplo de Uso

```bash
# Procesar mensaje de cliente
curl -X POST "http://localhost:5001/process-message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito un plomero en Quito para una emergencia",
    "user_type": "cliente",
    "context": {"phone": "+593998823053"}
  }'
```

### AI Service Proveedores (Puerto 5002)

#### Endpoints

- `GET /` - Información del servicio
- `GET /health` - Health check
- `POST /search-providers` - Buscar proveedores por ubicación
- `POST /register-provider` - Registrar nuevo proveedor
- `PUT /update-provider/{id}` - Actualizar proveedor
- `GET /provider/{id}` - Obtener proveedor
- `GET /providers/stats` - Estadísticas de proveedores

#### Ejemplo de Uso

```bash
# Buscar proveedores
curl -X POST "http://localhost:5002/search-providers" \
  -H "Content-Type: application/json" \
  -d '{
    "profession": "plomero",
    "location": {"lat": -0.1807, "lng": -78.4678},
    "radius_km": 10.0,
    "min_rating": 4.0,
    "available_only": true
  }'
```

## 🔄 Comunicación entre Servicios

Los servicios se comunican a través de **Redis Pub/Sub**:

### Canales de Comunicación

- `provider_search_requests`: Solicitudes de búsqueda del servicio clientes
- `provider_search_responses`: Respuestas del servicio proveedores

### Flujo de Comunicación Actualizado

1. Cliente envía mensaje a WhatsApp
2. WhatsApp service (Node.js) → AI Service Clientes
3. AI Service Clientes **guarda sesión automáticamente** y procesa mensaje
4. AI Service Clientes publica solicitud en Redis (si necesita proveedores)
5. AI Service Proveedores recibe solicitud y busca proveedores
6. AI Service Proveedores publica resultados en Redis
7. AI Service Clientes recibe resultados, **guarda respuesta en sesión** y responde al cliente

### Ventajas del Nuevo Flujo

- ✅ **Sesiones automáticas**: No requiere llamadas adicionales
- ✅ **Contexto integrado**: OpenAI recibe historial directamente
- ✅ **Menos latencia**: Eliminamos llamado al Session Service
- ✅ **Coherencia garantizada**: Mensajes y respuestas siempre sincronizados

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests unitarios
pytest -m unit

# Tests de integración
pytest -m integration

# Tests con coverage
pytest --cov=. --cov-report=html
```

### Type Checking

```bash
mypy .
```

## 🗄️ Base de Datos

### Estructura de Tablas

```sql
CREATE TABLE providers (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    profession VARCHAR(255) NOT NULL,
    location_lat DECIMAL(10, 8) NOT NULL,
    location_lng DECIMAL(11, 8) NOT NULL,
    rating DECIMAL(3, 2) DEFAULT 0.0,
    available BOOLEAN DEFAULT true,
    services_offered TEXT[],
    experience_years INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Crear índice geoespacial
CREATE INDEX idx_providers_location ON providers USING GIST (
    ST_MakePoint(location_lng, location_lat)
);
```

## 🚀 Despliegue

### Docker

```bash
# Construir imágenes
docker-compose build

# Iniciar servicios
docker-compose up -d
```

### Migración desde Session Service

Si vienes de la arquitectura anterior con Session Service:

1. **Ejecutar script de validación:**

   ```bash
   python validate_migration.py
   ```

2. **Actualizar WhatsApp services:**
   - Reemplazar `SESSION_SERVICE_URL` por `AI_SERVICE_CLIENTES_URL`
   - Seguir la guía en `MIGRATION_GUIDE.md`

3. **Verificar funcionamiento:**

   ```bash
   # Probar endpoints de sesiones
   curl -X POST "http://localhost:5001/sessions" \
     -H "Content-Type: application/json" \
     -d '{"phone": "+593998823053", "message": "Test"}'
   ```

4. **Eliminar session-service:**
   - Remover del docker-compose.yml principal
   - Detener contenedor: `docker stop session-service`

### Google Cloud Platform

1. **Configurar Cloud SQL** con PostgreSQL y PostGIS
2. **Configurar Upstash Redis** para Pub/Sub
3. **Deploy en Cloud Run** o Compute Engine

## 🔧 Monitoreo

### Logs

```bash
# Ver logs en tiempo real
python start_services.py

# O con Docker
docker-compose logs -f
```

### Métricas

Los servicios exponen métricas básicas:

- Health checks
- Tiempos de respuesta
- Errores de procesamiento

## 📊 Rendimiento

### Características

- ⚡ **Alto rendimiento**: AsyncIO para procesamiento concurrente
- 🌍 **Búsqueda geolocalizada**: PostGIS para búsquedas espaciales eficientes
- 💾 **Cache inteligente**: Redis para reducir consultas a BD
- 🔗 **Comunicación asíncrona**: Redis Pub/Sub sin bloqueo
- 🛡️ **Type safety**: MyPy para detección temprana de errores

### Benchmarks

- Procesamiento de mensajes: < 500ms
- Búsqueda de proveedores: < 200ms (100 proveedores)
- Comunicación entre servicios: < 50ms
- Uso de memoria: ~50MB por servicio

## 🤝 Contribución

1. Hacer fork del repositorio
2. Crear feature branch
3. Implementar cambios con tests
4. Verificar con mypy y flake8
5. Hacer pull request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo LICENSE para detalles.

## 🆘 Soporte

Para problemas o preguntas:

- Crear issue en el repositorio
- Revisar logs de los servicios
- Verificar health checks
