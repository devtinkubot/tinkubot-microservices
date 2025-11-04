# 🔧 MAPEO INTEGRAL DE VARIABLES DE ENTORNO - TINKUBOT v2.0

## 📋 **PROBLEMA CRÍTICO IDENTIFICADO**

**Variables de entorno configuradas en código pero NO mapeadas en archivos .env:**
- Los servicios leen variables de `process.env`/`os.getenv()`
- El archivo `.env` actual está vacío/incompleto
- No existe validación que asegure configuración consistente

---

## 🎯 **ESTADO ACTUAL DEL MAPEO**

### ✅ **VARIABLES CORRECTAMENTE MAPEADAS EN CÓDIGO**

#### **Python Services (ai-clientes, ai-proveedores, search-token)**
```python
# ✅ USO CORRECTO: settings de shared-lib/config.py
from shared_lib.config import settings

# Variables correctamente mapeadas:
openai_api_key: settings.openai_api_key
supabase_url: settings.supabase_url
supabase_service_key: settings.supabase_service_key
database_url: settings.database_url
redis_url: settings.redis_url

# Puertos correctamente configurados:
clientes_service_port: settings.clientes_service_port
proveedores_service_port: settings.proveedores_service_port
search_token_port: settings.search_token_port
```

#### **Node.js Services (frontend, wa-clientes, wa-proveedores)**
```javascript
// ❌ PROBLEMA: Variables dispersas en cada servicio sin estandarización

// wa-clientes/index.js
const AI_SERVICE_URL = process.env.AI_SERVICE_CLIENTES_URL || 'http://ai-srv-clientes:8001';
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_BACKEND_API_KEY;

// wa-proveedores/index.js
const AI_SERVICE_URL = process.env.PROVEEDORES_AI_SERVICE_URL || 'http://ai-proveedores:8002';

// frontend/index.js - No usa variables de entorno complejas

// ❌ INCONSISTENCIAS:
1. Mismos nombres de variables con sufijos diferentes
2. Nombres inconsistentes en package.json ya corregidos
```

---

## 🛠️ **PLANTILLA COMPLETA .env**

### **Variables Obligatorias**
```bash
# ===========================================
# CONFIGURACIÓN SUPABASE
# ===========================================
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_BACKEND_API_KEY=your-supabase-backend-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

# ===========================================
# CONFIGURACIÓN BASE DE DATOS (PostgreSQL + PostGIS)
# ===========================================
DATABASE_URL=postgresql://user:password@host:5432/database

# ===========================================
# CONFIGURACIÓN REDIS
# ===========================================
REDIS_URL=redis://default:your-redis-token@redis-host

# ===========================================
# CONFIGURACIÓN OPENAI
# ===========================================
OPENAI_API_KEY=your-openai-api-key

# ===========================================
# CONFIGURACIÓN WHATSAPP (Node.js - Puerto Dinámico)
# ===========================================
WHATSAPP_HEADLESS=true
WHATSAPP_WINDOW_SIZE=1920,1080

# ===========================================
# SERVICIOS WHATSAPP (Node.js)
# ===========================================
FRONTEND_SERVICE_PORT=5000
WHATSAPP_CLIENTES_PORT=5001
WHATSAPP_PROVEEDORES_PORT=5002

# ===========================================
# SERVICIO DE PROVEEDORES (BFF)
# ===========================================
PROVIDERS_SERVICE_URL=http://providers-service:7000
PROVIDERS_SERVICE_HOST=providers-service
PROVIDERS_SERVICE_PORT=7000
PROVIDERS_SERVICE_TIMEOUT_MS=5000

# ===========================================
# SERVICIOS AI (Python)
# ===========================================
SEARCH_TOKEN_PORT=8000
AI_SERVICE_CLIENTES_PORT=8001
AI_SERVICE_PROVEEDORES_PORT=8002

# ===========================================
# SERVICIOS WHATSAPP (Python - URLs para comunicación entre servicios)
# ===========================================
SEARCH_TOKEN_URL=http://search-token:8000
CLIENTES_AI_SERVICE_URL=http://ai-clientes:8001
PROVEEDORES_AI_SERVICE_URL=http://ai-proveedores:8002
# Nota: docker-compose.yml inyecta estas URLs directamente en el frontend y en cualquier
# servicio que las necesite; los nombres deben mantenerse exactamente igual.
WHATSAPP_CLIENTES_URL=http://wa-clientes:5001
WHATSAPP_PROVEEDORES_URL=http://wa-proveedores:5002

# ===========================================
# CONFIGURACIÓN DE PUERTOS (ESQUEMA ACTUALIZADO)
# ===========================================
# Frontend y Dashboards
FRONTEND_SERVICE_PORT=5000
ORCHESTRATOR_SERVER_PORT=8008

# Servicios WhatsApp
WHATSAPP_CLIENTES_PORT=5001
WHATSAPP_PROVEEDORES_PORT=5002

# Servicios de Búsqueda y Agentes
SEARCH_TOKEN_PORT=8000
AI_SERVICE_CLIENTES_PORT=8001
AI_SERVICE_PROVEEDORES_PORT=8002
ORCHESTRATOR_SERVER_PORT=8008

# ===========================================
# CONFIGURACIÓN DE LOGGING
# ===========================================
LOG_LEVEL=INFO
NODE_ENV=development

# ===========================================
# CONFIGURACIÓN DE INSTANCIAS
# ===========================================
MAX_RETRIES=5
SESSION_TIMEOUT=3600
HEALTH_CHECK_INTERVAL=30
METRICS_ENABLED=true
```

### **Variables de Desarrollo**
```bash
# Descomentar las claves reales en desarrollo
# SUPABASE_URL=postgresql://postgres:password@localhost:5432/tinkubot_dev
# DATABASE_URL=postgresql://postgres:password@localhost:5432/tinkubot_dev
```

---

## 🔧 **VALIDACIONES REQUERIDAS ANTES DE DESPLIEGUE**

### **1. Check de Variables Obligatorias**
```bash
# Validar que todas las variables críticas estén configuradas:
echo "✅ Validando variables críticas..."
if [[ -z "$SUPABASE_URL" || -z "$SUPABASE_BACKEND_API_KEY" || -z "$DATABASE_URL" || -z "$REDIS_URL" ]]; then
    echo "❌ ERROR: Faltan variables obligatorias"
    exit 1
else
    echo "✅ Variables críticas configuradas"
fi
```

### **2. Check de Conexiones entre Servicios**
```bash
# Verificar que los puertos y URLs coincidan entre servicios:
if [[ "$AI_SERVICE_CLIENTES_PORT" == "8001" ]] && [[ "$CLIENTES_AI_SERVICE_URL" == "http://ai-clientes:8001" ]]; then
    echo "✅ Conexión ai-clientes → ai-proveedores: OK"
else
    echo "❌ ERROR: Inconsistencia en puertos/URLs"
fi

if [[ "$AI_SERVICE_PROVEEDORES_PORT" == "8002" ]] && [[ "$PROVEEDORES_AI_SERVICE_URL" == "http://ai-proveedores:8002" ]]; then
    echo "✅ Conexión ai-proveedores → wa-proveedores: OK"
else
    echo "❌ ERROR: Inconsistencia en puertos/URLs"
fi
```

### **3. Validación de Servicios Individuales**
```bash
# Validar cada servicio individualmente
docker-compose config && docker-compose ps
```

---

## 📋 **SCRIPT DE VALIDACIÓN AUTOMÁTICA**

`validate-environment.sh`
```bash
#!/bin/bash

set -e

echo "🔍 VALIDANDO ENTORNO DE TINKUBOT v2.0"
echo "=================================="

# Validar variables críticas
critical_vars=("SUPABASE_URL" "SUPABASE_BACKEND_API_KEY" "DATABASE_URL" "REDIS_URL" "OPENAI_API_KEY")
missing_vars=()

for var in "${critical_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "❌ FALTA CRÍTICA: $var no está configurada"
        missing_vars+=("$var")
    else
        echo "✅ $var configurada correctamente"
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo ""
    echo "🚨 ERRORES CRÍTICOS ENCONTRADOS:"
    printf '  - %s\n' "${missing_vars[@]}"
    echo ""
    echo "Por favor, configura estas variables en tu archivo .env"
    echo ""
    exit 1
else
    echo "✅ Todas las variables críticas están configuradas"
fi

echo "=================================="

# Validar puertos y URLs
expected_ports=("8000:8001:8002")
expected_urls=("http://ai-clientes:8001" "http://ai-proveedores:8002")

port_check=true
url_check=true

# Validar servicio de búsqueda
if [[ ! "$SEARCH_TOKEN_PORT" == "8000" ]]; then
    echo "❌ ERROR: SEARCH_TOKEN_PORT debe ser 8000"
    port_check=false
fi

# Validar servicios de IA
if [[ ! "$AI_SERVICE_CLIENTES_PORT" == "8001" ]] || [[ ! "$AI_SERVICE_PROVEEDORES_PORT" == "8002" ]]; then
    echo "❌ ERROR: Puertos de servicios AI incorrectos"
    port_check=false
fi

# Validar servicios WhatsApp
if [[ ! "$WHATSAPP_CLIENTES_PORT" == "5001" ]] || [[ ! "$WHATSAPP_PROVEEDORES_PORT" == "5002" ]]; then
    echo "❌ ERROR: Puertos de servicios WhatsApp incorrectos"
    port_check=false
fi

# Validar URLs entre servicios
if [[ "$SEARCH_TOKEN_URL" != "http://search-token:8000" ]] || [[ "$CLIENTES_AI_SERVICE_URL" != "http://ai-clientes:8001" ]] || [[ "$PROVEEDORES_AI_SERVICE_URL" != "http://ai-proveedores:8002" ]]; then
    echo "❌ ERROR: URLs entre servicios inconsistentes"
    url_check=false
fi

# Validar Docker Compose
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ ERROR: No se encontró docker-compose.yml"
    port_check=false
fi

# Resultado final
if [ "$port_check" = true ] && [ "$url_check" = true ]; then
    echo "✅ VALIDACIÓN EXITOSA"
    echo "🎯 TinkuBot v2.0 listo para QA y despliegue"
    exit 0
else
    echo "❌ VALIDACIÓN FALLÓ"
    exit 1
fi

# Hacer ejecutable
chmod +x validate-environment.sh
```

---

## 📚 **INSTRUCCIONES PARA QA**

### **Para validar localmente:**
```bash
# 1. Copiar plantilla .env
cp .env.template .env

# 2. Editar con tus valores reales
nano .env  # o tu editor preferido

# 3. Ejecutar validación
./validate-environment.sh

# 4. Construir y probar
docker-compose build --no-cache
docker-compose up -d

# 5. Verificar logs
docker-compose logs -f ai-clientes ai-proveedores search-token
```

### **Para despliegue en producción:**
```bash
# 1. Configurar variables de producción en .env
# 2. Usar docker-compose.prod.yml (si existe)
# 3. Ejecutar con modo producción
docker-compose -f docker-compose.prod.yml up -d
```

---

## 🎯 **ESTADO FINAL DE IMPLEMENTACIÓN**

**Estado Actual:** 🔴 **CRÍTICO**
**Problema:** Variables de entorno desconfiguradas
**Solución:** Template .env completo + validación automática
**Impacto:** Bloquea total del despliegue hasta resolver

** QA Listo Para:** ✅ Aplicar el template .env y ejecutar validación
