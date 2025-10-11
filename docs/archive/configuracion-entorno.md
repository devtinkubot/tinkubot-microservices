# Guía: Configuración de Entorno para Migración

## 🎯 Objetivo

Establecer la configuración necesaria en todos los servicios y componentes del sistema para soportar la migración a las nuevas tablas en español.

## 📋 Requisitos Previos

1. **Acceso administrativo** a Supabase
2. **Permisos de modificación** en repositorio Git
3. **Entorno de staging** para pruebas
4. **Backup completo** del sistema actual

## 🔧 Variables de Entorno a Modificar

### 1. Archivo `.env` Principal

```bash
# Variables actuales (ingles) → Variables nuevas (español)
# DATABASE_URL - Sin cambios (misma base de datos)
DATABASE_URL=postgresql://postgres.euescxureboitxqjduym:sb_secret_N84Ggqc1reCT26MlJAvh3g_M3_bLRv5@db.euescxureboitxqjduym.supabase.co:5432/postgres

# SUPABASE_URL - Sin cambios
SUPABASE_URL=https://euescxureboitxqjduym.supabase.co

# SUPABASE_BACKEND_API_KEY - Sin cambios
SUPABASE_BACKEND_API_KEY=sb_secret_N84Ggqc1reCT26MlJAvh3g_M3_bLRv5

# Variables de conexión a servicios - Sin cambios
AI_SERVICE_CLIENTES_URL=http://ai-service-clientes:5001
PROVEEDORES_AI_SERVICE_URL=http://ai-service-proveedores:5002
WHATSAPP_CLIENTES_URL=http://whatsapp-service-clientes:7001
WHATSAPP_PROVEEDORES_URL=http://whatsapp-service-proveedores:7002
```

### 2. Nuevas Variables de Configuración

```bash
# Variables para manejo de migración
MIGRATION_MODE=true
MIGRATION_BACKUP_ENABLED=true
MIGRATION_DRY_RUN=false
MIGRATION_BATCH_SIZE=1000

# Variables de nombres de tablas (para flexibilidad)
TABLE_CLIENTES=clientes
TABLE_PROVEEDORES=proveedores
TABLE_PROFESIONES=profesiones
TABLE_PROVEEDOR_PROFESIONES=proveedor_profesiones
TABLE_SERVICIOS_PROVEEDOR=servicios_proveedor
TABLE_SOLICITUDES_SERVICIO=solicitudes_servicio
TABLE_MENSAJES=mensajes
TABLE_SESIONES=sesiones
TABLE_TAREAS_PROGRAMADAS=tareas_programadas
```

## 🐳 Configuración Docker Compose

### docker-compose.yml - Modificaciones

```yaml
version: '3.8'

services:
  # AI Service Clientes
  ai-service-clientes:
    build: ./python-services/ai-service-clientes
    ports:
      - "5001:5001"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_BACKEND_API_KEY=${SUPABASE_BACKEND_API_KEY}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MIGRATION_MODE=${MIGRATION_MODE}
      - TABLE_CLIENTES=${TABLE_CLIENTES}
      - TABLE_PROFESIONES=${TABLE_PROFESIONES}
      - TABLE_SOLICITUDES_SERVICIO=${TABLE_SOLICITUDES_SERVICIO}
      - TABLE_MENSAJES=${TABLE_MENSAJES}
      - TABLE_SESIONES=${TABLE_SESIONES}
      - TABLE_TAREAS_PROGRAMADAS=${TABLE_TAREAS_PROGRAMADAS}
    depends_on:
      - redis
    restart: unless-stopped

  # AI Service Proveedores
  ai-service-proveedores:
    build: ./python-services/ai-service-proveedores
    ports:
      - "5002:5002"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_BACKEND_API_KEY=${SUPABASE_BACKEND_API_KEY}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MIGRATION_MODE=${MIGRATION_MODE}
      - TABLE_PROVEEDORES=${TABLE_PROVEEDORES}
      - TABLE_PROFESIONES=${TABLE_PROFESIONES}
      - TABLE_PROVEEDOR_PROFESIONES=${TABLE_PROVEEDOR_PROFESIONES}
      - TABLE_SERVICIOS_PROVEEDOR=${TABLE_SERVICIOS_PROVEEDOR}
    depends_on:
      - redis
    restart: unless-stopped

  # WhatsApp Service Clientes
  whatsapp-service-clientes:
    build: ./nodejs-services/whatsapp-service-clientes
    ports:
      - "7001:7001"
    environment:
      - NODE_ENV=production
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_BACKEND_API_KEY=${SUPABASE_BACKEND_API_KEY}
      - SUPABASE_BUCKET_NAME=${SUPABASE_BUCKET_NAME}
      - AI_SERVICE_CLIENTES_URL=${AI_SERVICE_CLIENTES_URL}
      - MIGRATION_MODE=${MIGRATION_MODE}
      - TABLE_CLIENTES=${TABLE_CLIENTES}
      - TABLE_MENSAJES=${TABLE_MENSAJES}
      - TABLE_SESIONES=${TABLE_SESIONES}
    volumes:
      - whatsapp-data-clientes:/app/.wwebjs_auth
    restart: unless-stopped

  # WhatsApp Service Proveedores
  whatsapp-service-proveedores:
    build: ./nodejs-services/whatsapp-service-proveedores
    ports:
      - "7002:7002"
    environment:
      - NODE_ENV=production
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_BACKEND_API_KEY=${SUPABASE_BACKEND_API_KEY}
      - SUPABASE_BUCKET_NAME=${SUPABASE_BUCKET_NAME}
      - PROVEEDORES_AI_SERVICE_URL=${PROVEEDORES_AI_SERVICE_URL}
      - MIGRATION_MODE=${MIGRATION_MODE}
      - TABLE_PROVEEDORES=${TABLE_PROVEEDORES}
      - TABLE_MENSAJES=${TABLE_MENSAJES}
      - TABLE_SESIONES=${TABLE_SESIONES}
    volumes:
      - whatsapp-data-proveedores:/app/.wwebjs_auth
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
  whatsapp-data-clientes:
  whatsapp-data-proveedores:
```

## 📁 Configuración por Servicio

### 1. AI Service Clientes

#### Archivo: `python-services/ai-service-clientes/config.py`

```python
# config.py - Configuración actualizada
import os
from typing import Optional

class Settings:
    """Configuración para AI Service Clientes con soporte de migración"""

    # Configuración básica
    app_name: str = "AI Service Clientes"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Base de datos
    database_url: str = os.getenv("DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_BACKEND_API_KEY", "")

    # Configuración de migración
    migration_mode: bool = os.getenv("MIGRATION_MODE", "false").lower() == "true"
    migration_dry_run: bool = os.getenv("MIGRATION_DRY_RUN", "false").lower() == "true"

    # Nombres de tablas (configurables para migración)
    table_clientes: str = os.getenv("TABLE_CLIENTES", "clientes")
    table_profesiones: str = os.getenv("TABLE_PROFESIONES", "profesiones")
    table_solicitudes_servicio: str = os.getenv("TABLE_SOLICITUDES_SERVICIO", "solicitudes_servicio")
    table_mensajes: str = os.getenv("TABLE_MENSAJES", "mensajes")
    table_sesiones: str = os.getenv("TABLE_SESIONES", "sesiones")
    table_tareas_programadas: str = os.getenv("TABLE_TAREAS_PROGRAMADAS", "tareas_programadas")

    # Nombres de tablas legacy (para fallback durante migración)
    table_customers_legacy: str = "customers"
    table_service_requests_legacy: str = "service_requests"
    table_messages_legacy: str = "messages"
    table_sessions_legacy: str = "sessions"
    table_task_queue_legacy: str = "task_queue"

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # OpenAI
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "150"))
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

    # Servicios
    clientes_service_port: int = int(os.getenv("CLIENTES_SERVER_PORT", "5001"))
    whatsapp_clientes_port: int = int(os.getenv("WHATSAPP_CLIENTES_PORT", "7001"))

    # Flow TTL (en segundos)
    flow_ttl_seconds: int = int(os.getenv("FLOW_TTL_SECONDS", "3600"))  # 1 hora

    # Feedback settings
    feedback_delay_seconds: int = int(os.getenv("FEEDBACK_DELAY_SECONDS", "3600"))  # 1 hora

    # Task polling
    task_poll_interval_seconds: int = int(os.getenv("TASK_POLL_INTERVAL_SECONDS", "30"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def use_legacy_tables(self) -> bool:
        """Determina si usar tablas legacy durante migración"""
        return self.migration_mode and not self.migration_dry_run

    def get_table_name(self, table_type: str) -> str:
        """Obtener nombre de tabla según configuración y modo de migración"""
        if self.use_legacy_tables:
            legacy_mapping = {
                "clientes": self.table_customers_legacy,
                "solicitudes_servicio": self.table_service_requests_legacy,
                "mensajes": self.table_messages_legacy,
                "sesiones": self.table_sessions_legacy,
                "tareas_programadas": self.table_task_queue_legacy
            }
            return legacy_mapping.get(table_type, table_type)

        new_mapping = {
            "clientes": self.table_clientes,
            "profesiones": self.table_profesiones,
            "solicitudes_servicio": self.table_solicitudes_servicio,
            "mensajes": self.table_mensajes,
            "sesiones": self.table_sesiones,
            "tareas_programadas": self.table_tareas_programadas
        }
        return new_mapping.get(table_type, table_type)

settings = Settings()
```

### 2. AI Service Proveedores

#### Archivo: `python-services/ai-service-proveedores/config_proveedores.py`

```python
# config_proveedores.py - Configuración actualizada
import os
from typing import Optional

class ProviderSettings:
    """Configuración para AI Service Proveedores con soporte de migración"""

    # Configuración básica
    app_name: str = "AI Service Proveedores"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Base de datos
    database_url: str = os.getenv("DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_BACKEND_API_KEY", "")

    # Configuración de migración
    migration_mode: bool = os.getenv("MIGRATION_MODE", "false").lower() == "true"
    migration_dry_run: bool = os.getenv("MIGRATION_DRY_RUN", "false").lower() == "true"

    # Nombres de tablas (configurables para migración)
    table_proveedores: str = os.getenv("TABLE_PROVEEDORES", "proveedores")
    table_profesiones: str = os.getenv("TABLE_PROFESIONES", "profesiones")
    table_proveedor_profesiones: str = os.getenv("TABLE_PROVEEDOR_PROFESIONES", "proveedor_profesiones")
    table_servicios_proveedor: str = os.getenv("TABLE_SERVICIOS_PROVEEDOR", "servicios_proveedor")

    # Nombres de tablas legacy (para fallback durante migración)
    table_users_legacy: str = "users"
    table_professions_legacy: str = "professions"
    table_provider_professions_legacy: str = "provider_professions"
    table_provider_services_legacy: str = "provider_services"

    # OpenAI
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    # Servicios
    proveedores_service_port: int = int(os.getenv("PROVEEDORES_SERVER_PORT", "5002"))
    whatsapp_proveedores_port: int = int(os.getenv("WHATSAPP_PROVEEDORES_PORT", "7002"))

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Flow TTL
    flow_ttl_seconds: int = int(os.getenv("FLOW_TTL_SECONDS", "3600"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def use_legacy_tables(self) -> bool:
        """Determina si usar tablas legacy durante migración"""
        return self.migration_mode and not self.migration_dry_run

    def get_table_name(self, table_type: str) -> str:
        """Obtener nombre de tabla según configuración y modo de migración"""
        if self.use_legacy_tables:
            legacy_mapping = {
                "proveedores": self.table_users_legacy,
                "profesiones": self.table_professions_legacy,
                "proveedor_profesiones": self.table_provider_professions_legacy,
                "servicios_proveedor": self.table_provider_services_legacy
            }
            return legacy_mapping.get(table_type, table_type)

        new_mapping = {
            "proveedores": self.table_proveedores,
            "profesiones": self.table_profesiones,
            "proveedor_profesiones": self.table_proveedor_profesiones,
            "servicios_proveedor": self.table_servicios_proveedor
        }
        return new_mapping.get(table_type, table_type)

provider_settings = ProviderSettings()
```

### 3. WhatsApp Services

#### Archivo: `nodejs-services/whatsapp-service-clientes/.env.production`

```bash
# WhatsApp Service Clientes - Configuración de Producción
NODE_ENV=production

# Supabase
SUPABASE_URL=https://euescxureboitxqjduym.supabase.co
SUPABASE_BACKEND_API_KEY=sb_secret_N84Ggqc1reCT26MlJAvh3g_M3_bLRv5
SUPABASE_BUCKET_NAME=wa_sessions

# Configuración de migración
MIGRATION_MODE=false
TABLE_CLIENTES=clientes
TABLE_MENSAJES=mensajes
TABLE_SESIONES=sesiones

# AI Service
AI_SERVICE_CLIENTES_URL=http://ai-service-clientes:5001

# Configuración de WhatsApp
WHATSAPP_HEADLESS=true
WHATSAPP_WINDOW_SIZE=1920,1080
CLIENTES_INSTANCE_NAME=TinkuBot Clientes
CLIENTES_INSTANCE_ID=bot-clientes
CLIENTES_WHATSAPP_PORT=7001

# Logging
LOG_LEVEL=info
```

#### Archivo: `nodejs-services/whatsapp-service-proveedores/.env.production`

```bash
# WhatsApp Service Proveedores - Configuración de Producción
NODE_ENV=production

# Supabase
SUPABASE_URL=https://euescxureboitxqjduym.supabase.co
SUPABASE_BACKEND_API_KEY=sb_secret_N84Ggqc1reCT26MlJAvh3g_M3_bLRv5
SUPABASE_BUCKET_NAME=wa_sessions

# Configuración de migración
MIGRATION_MODE=false
TABLE_PROVEEDORES=proveedores
TABLE_MENSAJES=mensajes
TABLE_SESIONES=sesiones

# AI Service
PROVEEDORES_AI_SERVICE_URL=http://ai-service-proveedores:5002

# Configuración de WhatsApp
WHATSAPP_HEADLESS=true
WHATSAPP_WINDOW_SIZE=1920,1080
PROVEEDORES_INSTANCE_NAME=TinkuBot Proveedores
PROVEEDORES_INSTANCE_ID=bot-proveedores
PROVEEDORES_WHATSAPP_PORT=7002

# Logging
LOG_LEVEL=info
```

## 🔄 Scripts de Configuración

### Script: `scripts/setup-migration-env.sh`

```bash
#!/bin/bash

# setup-migration-env.sh - Script para configurar entorno de migración

set -e

echo "🔧 Configurando entorno para migración..."

# Verificar variables requeridas
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "❌ Error: Variable $1 no está definida"
        exit 1
    fi
}

# Variables requeridas
check_env_var "DATABASE_URL"
check_env_var "SUPABASE_URL"
check_env_var "SUPABASE_BACKEND_API_KEY"

# Crear archivo .env.migration
cat > .env.migration << EOF
# Configuración para modo de migración
MIGRATION_MODE=true
MIGRATION_BACKUP_ENABLED=true
MIGRATION_DRY_RUN=false
MIGRATION_BATCH_SIZE=1000

# Variables heredadas del entorno principal
DATABASE_URL=${DATABASE_URL}
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_BACKEND_API_KEY=${SUPABASE_BACKEND_API_KEY}
SUPABASE_BUCKET_NAME=${SUPABASE_BUCKET_NAME}
REDIS_URL=${REDIS_URL}
OPENAI_API_KEY=${OPENAI_API_KEY}

# Nombres de tablas nuevos
TABLE_CLIENTES=clientes
TABLE_PROVEEDORES=proveedores
TABLE_PROFESIONES=profesiones
TABLE_PROVEEDOR_PROFESIONES=proveedor_profesiones
TABLE_SERVICIOS_PROVEEDOR=servicios_proveedor
TABLE_SOLICITUDES_SERVICIO=solicitudes_servicio
TABLE_MENSAJES=mensajes
TABLE_SESIONES=sesiones
TABLE_TAREAS_PROGRAMADAS=tareas_programadas

# Configuración de servicios
AI_SERVICE_CLIENTES_URL=http://ai-service-clientes:5001
PROVEEDORES_AI_SERVICE_URL=http://ai-service-proveedores:5002
WHATSAPP_CLIENTES_URL=http://whatsapp-service-clientes:7001
WHATSAPP_PROVEEDORES_URL=http://whatsapp-service-proveedores:7002

# Logging
LOG_LEVEL=DEBUG
EOF

echo "✅ Archivo .env.migration creado"

# Actualizar docker-compose para modo migración
cat > docker-compose.migration.yml << EOF
version: '3.8'

services:
  # Base de datos con acceso directo para migración
  migration-db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=${DATABASE_URL##*/}
      - POSTGRES_USER=${DATABASE_URL##*@}
      - POSTGRES_PASSWORD=secret
    volumes:
      - ./migration-scripts:/docker-entrypoint-initdb.d
    profiles:
      - migration

  # Servicio de migración
  migration-service:
    build:
      context: .
      dockerfile: migration-scripts/Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - MIGRATION_MODE=true
      - MIGRATION_DRY_RUN=false
    volumes:
      - ./migration-scripts:/app/scripts
    depends_on:
      - migration-db
    profiles:
      - migration
EOF

echo "✅ Archivo docker-compose.migration.yml creado"

# Crear directorios necesarios
mkdir -p migration-scripts
mkdir -p logs/migration

echo "🎉 Configuración de migración completada"
echo ""
echo "📋 Próximos pasos:"
echo "1. Revisar .env.migration"
echo "2. Ejecutar: docker-compose -f docker-compose.migration.yml --profile migration up"
echo "3. Monitorear logs: tail -f logs/migration/*.log"
```

### Script: `scripts/validate-config.sh`

```bash
#!/bin/bash

# validate-config.sh - Validar configuración de entorno

set -e

echo "🔍 Validando configuración del entorno..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función de validación
validate_setting() {
    local setting_name=$1
    local setting_value=${!2}
    local required=$3

    if [ -z "$setting_value" ]; then
        if [ "$required" = "true" ]; then
            echo -e "${RED}❌ $setting_name: No configurado (requerido)${NC}"
            return 1
        else
            echo -e "${YELLOW}⚠️ $setting_name: No configurado (opcional)${NC}"
            return 0
        fi
    else
        echo -e "${GREEN}✅ $setting_name: Configurado${NC}"
        return 0
    fi
}

# Validar variables principales
echo "📋 Validando variables principales..."
validate_setting "DATABASE_URL" "DATABASE_URL" "true"
validate_setting "SUPABASE_URL" "SUPABASE_URL" "true"
validate_setting "SUPABASE_BACKEND_API_KEY" "SUPABASE_BACKEND_API_KEY" "true"
validate_setting "REDIS_URL" "REDIS_URL" "true"
validate_setting "OPENAI_API_KEY" "OPENAI_API_KEY" "true"

# Validar variables de migración
echo ""
echo "📋 Validando variables de migración..."
validate_setting "MIGRATION_MODE" "MIGRATION_MODE" "false"
validate_setting "MIGRATION_BACKUP_ENABLED" "MIGRATION_BACKUP_ENABLED" "false"
validate_setting "TABLE_CLIENTES" "TABLE_CLIENTES" "false"
validate_setting "TABLE_PROVEEDORES" "TABLE_PROVEEDORES" "false"

# Validar conexión a Supabase
if [ ! -z "$SUPABASE_URL" ] && [ ! -z "$SUPABASE_BACKEND_API_KEY" ]; then
    echo ""
    echo "📋 Validando conexión a Supabase..."
    response=$(curl -s -H "apikey: $SUPABASE_BACKEND_API_KEY" -H "Authorization: Bearer $SUPABASE_BACKEND_API_KEY" "$SUPABASE_URL/rest/v1/" | head -1)

    if [[ $response == *"swagger"* ]]; then
        echo -e "${GREEN}✅ Conexión a Supabase: Exitosa${NC}"
    else
        echo -e "${RED}❌ Conexión a Supabase: Fallida${NC}"
        echo "Response: $response"
    fi
fi

# Validar estructura de archivos
echo ""
echo "📋 Validando estructura de archivos..."
required_files=(
    "docs/migracion-architectura-espanol.md"
    "docs/guias/migracion-datos.md"
    "python-services/ai-service-clientes/config.py"
    "python-services/ai-service-proveedores/config_proveedores.py"
    "docker-compose.yml"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file: Existe${NC}"
    else
        echo -e "${RED}❌ $file: No encontrado${NC}"
    fi
done

echo ""
echo "🎉 Validación de configuración completada"
```

## 🔍 Testing de Configuración

### Script: `scripts/test-connection.py`

```python
#!/usr/bin/env python3

# test-connection.py - Testing de conexiones y configuración

import os
import sys
import logging
from supabase import create_client
import psycopg2
import redis

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_supabase_connection():
    """Probar conexión a Supabase"""
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_BACKEND_API_KEY")

        if not url or not key:
            logger.error("❌ SUPABASE_URL o SUPABASE_BACKEND_API_KEY no configurados")
            return False

        client = create_client(url, key)

        # Probar consulta simple
        result = client.table("professions").select("count").execute()
        logger.info("✅ Conexión a Supabase exitosa")
        return True

    except Exception as e:
        logger.error(f"❌ Error conectando a Supabase: {e}")
        return False

def test_postgres_connection():
    """Probar conexión directa a PostgreSQL"""
    try:
        db_url = os.getenv("DATABASE_URL")

        if not db_url:
            logger.error("❌ DATABASE_URL no configurado")
            return False

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Probar consulta simple
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        conn.close()
        logger.info("✅ Conexión a PostgreSQL exitosa")
        return True

    except Exception as e:
        logger.error(f"❌ Error conectando a PostgreSQL: {e}")
        return False

def test_redis_connection():
    """Probar conexión a Redis"""
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        if redis_url.startswith("redis://"):
            host = redis_url.split("://")[1].split(":")[0]
            port = int(redis_url.split(":")[2])
        else:
            host = "localhost"
            port = 6379

        r = redis.Redis(host=host, port=port, decode_responses=True)
        r.ping()

        logger.info("✅ Conexión a Redis exitosa")
        return True

    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")
        return False

def test_table_existence():
    """Probar existencia de tablas"""
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_BACKEND_API_KEY")
        migration_mode = os.getenv("MIGRATION_MODE", "false").lower() == "true"

        client = create_client(url, key)

        # Tablas a verificar según modo
        if migration_mode:
            tables = ["customers", "users", "professions", "service_requests"]
        else:
            tables = ["clientes", "proveedores", "profesiones", "solicitudes_servicio"]

        for table in tables:
            try:
                result = client.table(table).select("count").limit(1).execute()
                logger.info(f"✅ Tabla '{table}': Accesible")
            except Exception as e:
                logger.error(f"❌ Tabla '{table}': Error - {e}")

    except Exception as e:
        logger.error(f"❌ Error verificando tablas: {e}")

def main():
    """Función principal"""
    logger.info("🔍 Iniciando testing de configuración...")

    # Cargar variables de entorno
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()

    # Ejecutar tests
    tests = [
        ("Supabase", test_supabase_connection),
        ("PostgreSQL", test_postgres_connection),
        ("Redis", test_redis_connection),
        ("Tablas", test_table_existence)
    ]

    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n📋 Testeando: {test_name}")
        results[test_name] = test_func()

    # Resumen
    logger.info("\n📊 Resumen de tests:")
    for test_name, result in results.items():
        status = "✅ OK" if result else "❌ ERROR"
        logger.info(f"  {test_name}: {status}")

    # Salir con código de error si algún test falló
    if not all(results.values()):
        logger.error("\n❌ Algunos tests fallaron. Revisar configuración.")
        sys.exit(1)
    else:
        logger.info("\n🎉 Todos los tests pasaron exitosamente.")

if __name__ == "__main__":
    main()
```

## 📋 Checklist de Configuración

### Pre-Migración
- [ ] Backup completo de base de datos
- [ ] Variables de entorno configuradas en `.env.migration`
- [ ] Scripts de configuración creados y probados
- [ ] Docker Compose actualizado para modo migración
- [ ] Tests de conexión ejecutados exitosamente
- [ ] Documentación actualizada

### Durante Migración
- [ ] Modo migración activado (`MIGRATION_MODE=true`)
- [ ] Logs habilitados en nivel DEBUG
- [ ] Monitoreo de recursos del sistema
- [ ] Validación de cada fase antes de continuar

### Post-Migración
- [ ] Modo migración desactivado
- [ ] Variables de entorno limpiadas
- [ ] Testing completo del sistema
- [ ] Documentación actualizada
- [ ] Equipo notificado del cambio completado

## 🚨 Troubleshooting

### Problemas Comunes

1. **Error de conexión a Supabase**
   ```bash
   # Verificar variables de entorno
   echo $SUPABASE_URL
   echo $SUPABASE_BACKEND_API_KEY

   # Probar conexión manual
   curl -H "apikey: $SUPABASE_BACKEND_API_KEY" "$SUPABASE_URL/rest/v1/"
   ```

2. **Tablas no encontradas**
   ```bash
   # Listar tablas disponibles
   psql $DATABASE_URL -c "\dt"

   # Verificar esquema
   psql $DATABASE_URL -c "\dn"
   ```

3. **Variables de entorno no cargadas**
   ```bash
   # Recargar variables
   source .env

   # Verificar carga
   env | grep -E "(SUPABASE|MIGRATION|TABLE)"
   ```

4. **Docker Compose errores**
   ```bash
   # Limpiar y reconstruir
   docker-compose down -v
   docker system prune -f
   docker-compose build --no-cache
   ```

## 📞 Contacto de Soporte

Para problemas técnicos durante la configuración:

- **Documentación técnica**: `docs/guias/migracion-datos.md`
- **Scripts de migración**: `migration-scripts/`
- **Logs del sistema**: `logs/migration/`
- **Equipo de desarrollo**: [contacto@tinkubot.com]

---

**Importante**: Realizar todas las configuraciones primero en un ambiente de staging antes de aplicar en producción.