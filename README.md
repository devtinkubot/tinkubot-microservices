# Microservicios TinkuBot

Sistema de chatbot en WhatsApp para conectar clientes con proveedores de servicios en Ecuador, utilizando Inteligencia Artificial, búsqueda semántica y geolocalización en tiempo real.

## 🏗 Arquitectura

TinkuBot utiliza una arquitectura de microservicios en contenedores, orquestada mediante Docker Compose:

- **Servicios de IA (Python/FastAPI)**:
  - `ai-clientes`: Cerebro del asistente para clientes. Procesa la intención del usuario, extrae necesidades y coordina las búsquedas.
  - `ai-proveedores`: Cerebro del asistente para proveedores. Gestiona perfiles y procesos de incorporación (onboarding).
  - `ai-search`: Motor de búsqueda inteligente. Utiliza estrategias híbridas (texto + semántica) con OpenAI y Redis.
  - `av-proveedores`: Puente MQTT para la verificación de disponibilidad de proveedores en tiempo real.

- **Servicios de Conectividad (Node.js)**:
  - `wa-clientes`: Cliente de WhatsApp (basado en `whatsapp-web.js`) para usuarios finales.
  - `wa-proveedores`: Cliente de WhatsApp para proveedores.
  - `frontend`: Panel administrativo y Puerta de Enlace (API Gateway) para gestión interna (desarrollado con Express + Vite/React).

- **Infraestructura**:
  - **Mosquitto**: Gestor de mensajes (Broker) MQTT para comunicación asíncrona de disponibilidad.
  - **Redis**: Caché de alto rendimiento y gestión de sesiones.
  - **Supabase**: Base de datos PostgreSQL (+PostGIS) y almacenamiento de archivos.

## 🚀 Instalación y Despliegue

### Requisitos Previos

- Docker Engine y Docker Compose v2 o superior.
- Node.js v20+ (para ejecución local sin Docker).
- Python 3.13+ (para ejecución local sin Docker).
- Cuenta de Supabase (URL y claves de API).
- Clave de API de OpenAI.

### Configuración

1. **Clonar el repositorio**:
   ```bash
   git clone <url-del-repositorio>
   cd tinkubot-microservices
   ```

2. **Configurar variables de entorno**:
   ```bash
   cp .env.example .env
   # Edite el archivo .env con sus credenciales reales (Supabase, OpenAI, Redis, etc.)
   nano .env
   ```

3. **Iniciar servicios con Docker Compose**:
   ```bash
   docker compose up -d --build
   ```

4. **Verificar el estado**:
   ```bash
   docker compose ps
   ```

## 📂 Estructura del Proyecto

```
tinkubot-microservices/
├── python-services/           # Microservicios en Python
│   ├── ai-clientes/           # Lógica de atención al cliente
│   ├── ai-proveedores/        # Lógica de gestión de proveedores
│   ├── ai-search/             # Motor de búsqueda y recomendación
│   ├── av-proveedores/        # Verificación de disponibilidad (MQTT)
│   └── shared-lib/            # Librerías comunes (Base de datos, Modelos, Configuración)
├── nodejs-services/           # Microservicios en Node.js
│   ├── wa-clientes/           # Interfaz WhatsApp para Clientes
│   ├── wa-proveedores/        # Interfaz WhatsApp para Proveedores
│   └── frontend/              # Panel Web (Monorepo)
├── docs/                      # Documentación adicional
├── docker-compose.yml         # Orquestación de servicios
└── mosquitto.conf             # Configuración del gestor MQTT
```

## 🩺 Verificación de Estado (Health Checks)

Una vez iniciados los servicios, puede verificar su funcionamiento en las siguientes direcciones locales:

| Servicio | URL Local | Descripción |
|----------|-----------|-------------|
| **Frontend** | `http://localhost:5000` | Panel Administrativo |
| **WA Clientes** | `http://localhost:5001/health` | Estado del bot de clientes |
| **WA Proveedores** | `http://localhost:5002/health` | Estado del bot de proveedores |
| **AI Search** | `http://localhost:8000/api/v1/health` | API de búsqueda |
| **AI Clientes** | `http://localhost:8001/health` | API de IA Clientes |
| **AI Proveedores** | `http://localhost:8002/health` | API de IA Proveedores |
| **AV Proveedores** | `http://localhost:8005/salud` | Estado del puente MQTT |

## 🛠 Desarrollo Local

### Servicios Python
Cada servicio dentro de `python-services` cuenta con su propio archivo de dependencias `requirements.txt`.
```bash
cd python-services/ai-clientes
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Servicios Node.js
Cada servicio dentro de `nodejs-services` cuenta con su archivo `package.json`.
```bash
cd nodejs-services/wa-clientes
npm install
npm run dev
```

## ✅ Validaciones y Documentacion

Validadores principales:

```bash
python validate_quality_code.py
python validate_docker.py
```

Documentacion unificada:

- `docs/TINKUBOT_SERVICES.md`

## 📝 Registros (Logs) y Monitoreo

Para visualizar los registros de un servicio específico:
```bash
docker compose logs -f ai-clientes
```

Para visualizar los registros de todos los servicios simultáneamente:
```bash
docker compose logs -f
```

## 🤝 Contribución

1. Crear una rama para su nueva funcionalidad (`git checkout -b feature/nueva-funcionalidad`).
2. Realizar los cambios respetando la estructura de microservicios.
3. Asegurarse de que el archivo `docker-compose.yml` refleje cualquier cambio de puerto o variable.
4. Abrir una Solicitud de Extracción (Pull Request).

## 📄 Licencia

Este proyecto es propiedad de TinkuBot.
