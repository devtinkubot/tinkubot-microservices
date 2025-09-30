# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Arquitectura General

TinkuBot es un sistema de microservicios para automatización de WhatsApp con IA. La arquitectura está basada en servicios Node.js y Python, comunicados a través de HTTP/REST y WebSockets.

### Servicios Node.js

- **nodejs-services/frontend-service**: Interface web (Express + Bootstrap) - Puerto 8200
- **nodejs-services/whatsapp-service-clientes**: Bot para clientes (+593 99 882 3053) - Puerto 8005
- **nodejs-services/whatsapp-service-proveedores**: Bot para proveedores - Puerto 8006
- **session-service**: Gestión de sesiones con Redis - Puerto 8004
- **auth-service**: Servicio de autenticación - Puerto 8002

### Servicios Python

- **ai-service-clientes**: Procesamiento con IA para clientes - Puerto 5003
- **ai-service-proveedores**: Gestión de proveedores y búsqueda - Puerto 5007

### Arquitectura de Comunicación

- **HTTP/REST**: Comunicación síncrona entre servicios
- **WebSockets**: Tiempo real para actualizaciones del frontend
- **Redis**: Cache y mensajería entre servicios

## Comandos de Desarrollo y Construcción

### Inicio del Sistema

```bash
# Inicio completo con Docker Compose
docker-compose up --build
docker-compose up -d  # modo detached

# Servicios individuales
cd python-services/ai-service-clientes && python3 main_simple.py
cd python-services/ai-service-proveedores && python3 main_simple.py
```

### Desarrollo Local

```bash
# Frontend Service
cd nodejs-services/frontend-service
npm run dev  # con nodemon
npm start    # producción

# WhatsApp Service
cd nodejs-services/whatsapp-service
npm install
npm run dev  # si hay nodemon
node index.js

# AI Service Clientes
cd python-services/ai-service-clientes
python3 main_simple.py

# AI Service Proveedores
cd python-services/ai-service-proveedores
python3 main_simple.py

# Session Service
cd nodejs-services/session-service
npm install
node index.js
```

### Construcción y Limpieza

```bash
# Construir imágenes Docker
docker-compose build
docker-compose build --no-cache  # limpieza completa

# Limpiar y reconstruir
docker-compose down -v
docker system prune -f
docker-compose build --no-cache
```

### Monitoreo y Logs

```bash
# Estado de contenedores
docker-compose ps

# Logs en tiempo real
docker-compose logs -f
docker-compose logs -f frontend-service
docker-compose logs -f whatsapp-service-clientes
docker-compose logs -f ai-service-clientes
docker-compose logs -f ai-service-proveedores

# Logs con timestamp
docker-compose logs -t frontend-service
```

### Health Checks

```bash
# Verificar servicios principales
curl http://localhost:6002/health
curl http://localhost:7001/health
curl http://localhost:7002/health
curl http://localhost:5001/health
curl http://localhost:5002/health
```

## Arquitectura de Servicios

### Frontend Service (Port 8200)

- **Tecnología**: Express + Socket.io + Bootstrap 5
- **Función**: Dashboard web para monitorear y gestionar bots
- **Dependencias**:
  - Conecta con ambos servicios WhatsApp (clientes:8005, proveedores:8006)
  - Usa Socket.io para actualizaciones en tiempo real
- **Endpoints**: Dashboard principal, generación de QR, estadísticas

### WhatsApp Services (Ports 8005, 8006)

- **Tecnología**: Node.js + whatsapp-web.js + Selenium
- **Función**: Automatización de WhatsApp Web
- **Características**:
  - Múltiples instancias (clientes y proveedores)
  - Generación de códigos QR
  - Persistencia de sesiones en volúmenes Docker
  - Integración con AI Services para procesamiento de mensajes
- **Variables de entorno**:
  - `AI_SERVICE_URL`: URL del servicio de IA
  - `SESSION_SERVICE_URL`: URL del servicio de sesiones
  - `INSTANCE_ID` y `INSTANCE_NAME`: Identificación de la instancia
  - `WHATSAPP_PORT`: Puerto específico

### AI Service Clientes (Port 5003)

- **Tecnología**: Python + FastAPI + OpenAI
- **Función**: Procesamiento de lenguaje natural para clientes
- **Características**:
  - Integración con OpenAI GPT-3.5
  - Detección de intenciones y contextos
  - Coordinación con AI Service Proveedores
  - Gestión de conversaciones y seguimiento
- **Dependencias**: OpenAI API key, Redis para caché

### AI Service Proveedores (Port 5007)

- **Tecnología**: Python + FastAPI + PostgreSQL
- **Función**: Gestión y búsqueda de proveedores
- **Características**:
  - Búsqueda geolocalizada de proveedores
  - Gestión de disponibilidad y rating
  - Almacenamiento de información de proveedores
  - Estadísticas y reportes
- **Endpoints**: `/search-providers`, `/register-provider`, `/providers/stats`

### Session Service (Port 8004)

- **Tecnología**: Node.js + Redis
- **Función**: Gestión centralizada de sesiones
- **Características**: Cache en Redis para mejorar rendimiento

## Imágenes Docker Optimizadas

Para maximizar el rendimiento y minimizar el consumo de recursos, TinkuBot utiliza imágenes Docker optimizadas:

### Servicios Node.js con Chrome/Puppeteer

- **whatsapp-service-clientes**: `node:20-slim` (~50MB)
- **whatsapp-service-proveedores**: `node:20-slim` (~50MB)
- **Ventaja**: Mejor compatibilidad con dependencias de Chrome/Puppeteer

### Servicios Node.js Ligeros

- **frontend-service**: `node:20-alpine` (~40MB)
- **Ventaja**: Tamaño mínimo con máximo rendimiento para frontend

### Servicios Python

- **ai-service-clientes**: `python:3.11-alpine` (~35MB)
- **ai-service-proveedores**: `python:3.11-alpine` (~35MB)
- **Ventaja**: Imágenes ultra-ligeras con Alpine Linux

### Beneficios de la Optimización

- Reducción del 30-40% en tamaño de imágenes
- Tiempos de build y despliegue más rápidos
- Menor consumo de recursos en producción
- Mejor rendimiento general del sistema

## Configuración de Variables de Entorno

### Archivos .env

- `.env.example`: Plantilla base
- `.env`: Configuración principal
- `.env.puertos`: Configuración de puertos específicos

### Variables Requeridas

```bash
# OpenAI
OPENAI_API_KEY=tu-api-key

# Redis
REDIS_URL=redis://localhost:6379

# Database (para proveedores)
DATABASE_URL=postgresql://user:pass@localhost:5432/tinkubot

# Instancias
CLIENTES_INSTANCE_ID=clientes
CLIENTES_INSTANCE_NAME=Bot Clientes
CLIENTES_WHATSAPP_PORT=8005
PROVEEDORES_INSTANCE_ID=proveedores
PROVEEDORES_INSTANCE_NAME=Bot Proveedores
PROVEEDORES_WHATSAPP_PORT=8006
```

## Estructura de Datos y Flujo

### Flujo de Mensajes de Clientes

1. Usuario envía mensaje a WhatsApp
2. `whatsapp-service-clientes` recibe mensaje
3. Envía a `ai-service-clientes` para procesamiento con OpenAI
4. Si se detecta solicitud de servicio, llama a `ai-service-proveedores`
5. `ai-service-proveedores` busca proveedores en la base de datos
6. Genera respuesta con resultados y opciones
7. Devuelve respuesta a `whatsapp-service-clientes`
8. Envía respuesta al usuario por WhatsApp

### Base de Datos de Proveedores

- **Motor**: PostgreSQL con extensión PostGIS
- **Almacenamiento**: Información de proveedores, ubicaciones, ratings
- **Búsqueda**: Geolocalizada por profesión y ubicación
- **Disponibilidad**: Tiempo real de disponibilidad de proveedores

## Desarrollo y Troubleshooting

### Problemas Comunes

1. **Permisos de volúmenes Docker**: Verificar permisos de `whatsapp-data-*`
2. **Conexión OpenAI**: Verificar API key y límites de uso
3. **Conexión Redis**: Verificar servicio Redis y configuración
4. **Chrome/Selenium**: Verificar modo headless y dependencias
5. **Comunicación entre servicios**: Verificar URLs y puertos

### Debug

```bash
# Acceder a contenedores
docker exec -it tinkubot-frontend-service bash
docker exec -it tinkubot-whatsapp-service-clientes bash
docker exec -it tinkubot-ai-service-clientes bash

# Verificar redes Docker
docker network ls
docker network inspect tinkubot-microservices_tinkubot-network

# Probar conexiones entre servicios
docker exec -it tinkubot-ai-service-clientes curl http://ai-service-proveedores:5007/health
```

## Endpoints Principales

### Frontend Service

- `GET /` - Dashboard principal
- `GET /health` - Health check
- WebSocket para actualizaciones en tiempo real

### WhatsApp Services

- `GET /health` - Health check
- `GET /qr` - Obtener código QR
- `POST /messages` - Enviar mensaje (uso interno)

### AI Service Clientes

- `GET /health` - Health check
- `POST /handle-whatsapp-message` - Procesar mensaje de WhatsApp
- `POST /process` - Procesar mensaje con IA

### AI Service Proveedores

- `GET /health` - Health check
- `POST /search-providers` - Buscar proveedores por profesión y ubicación
- `POST /register-provider` - Registrar nuevo proveedor
- `GET /providers/stats` - Obtener estadísticas de proveedores

### Session Service

- `GET /health` - Health check
- Endpoints de gestión de sesiones con Redis
