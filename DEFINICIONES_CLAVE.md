# 🚀 TinkuBot - Sistema de Gestión de Puertos

#

# Este archivo define la asignación oficial de puertos para todos los servicios

# Mantener sincronizado con docs/sistema-puertos.md

#

# Formato: CATEGORIA_SERVICIO_PORT=numero

# ===========================================

# 🔵 Agentes de IA - Python (Serie 5000-5099)

# ===========================================

# Servicios de alto rendimiento para procesamiento de IA

AI_SERVICE_CLIENTES_PORT=5001
AI_SERVICE_PROVEEDORES_PORT=5002

# Futuros Servicios

AI_SERVICE_ORCHESTATOR_PORT=5000
AI_SERVICE_ADMINISTRACION_PORT=5003
AI_SERVICE_QUEJAS_PORT=5004
AI_SERVICE_SUSCRIPCIONES_PORT=5005

# 🟢 Frontend y Dashboards (Serie 6000-6099)

# ===========================================

# Interfaces de usuario y paneles de visualización

DASHBOARD_SERVICE_PORT=6000

# 🟡 Servicios WhatsApp (Serie 7000-7099)

# ==========================================

# Servicios de integración con WhatsApp API

WHATSAPP_CLIENTES_PORT=7001
WHATSAPP_PROVEEDORES_PORT=7002

# Futuros Servicios

WHATSAPP_ADMINISTRACION_PORT=7003
WHATSAPP_QUEJAS_PORT=7004
WHATSAPP_SUSCRIPCIONES_PORT=7005

# 🌐 URLs de Servicios Completos

# ===============================

# Formato estandarizado para comunicación interna

# Agentes de IA

AI_SERVICE_CLIENTES_URL=http://ai-service-clientes:5001
AI_SERVICE_PROVEEDORES_URL=http://ai-service-proveedores:5002

# Frontend y Dashboards

DASHBOARD_SERVICE_URL=http://frontend-service:6002

# Servicios WhatsApp

WHATSAPP_CLIENTES_URL=http://whatsapp-service-clientes:7001
WHATSAPP_PROVEEDORES_URL=http://whatsapp-service-proveedores:7002

# 📊 Endpoints de Health Check

# =============================

# Endpoints estándar para monitoreo de salud

AI_SERVICE_CLIENTES_HEALTH=http://ai-service-clientes:5001/health
AI_SERVICE_PROVEEDORES_HEALTH=http://ai-service-proveedores:5002/health

DASHBOARD_SERVICE_HEALTH=http://frontend-service:6002/health

WHATSAPP_CLIENTES_HEALTH=http://whatsapp-service-clientes:7001/health
WHATSAPP_PROVEEDORES_HEALTH=http://whatsapp-service-proveedores:7002/health

# 🔒 Configuración de Seguridad por Puerto

# =========================================

# Niveles de seguridad para exposición externa

# Puertos públicos (requieren autenticación)

PUBLIC_PORTS=6002

# Puertos internos (solo acceso red interna)

INTERNAL_PORTS=5001,5002,7001,7002

# Puertos de desarrollo (solo en entorno dev)

DEV_PORTS=5010,5011,5012,5013,6011,6012,6013,7010,7011,7012,7013

# 📝 Notas

# ========

# - Mantener este archivo sincronizado con docs/sistema-puertos.md

# - Los cambios en puertos deben ser coordinados con el equipo de arquitectura

# - Usar siempre variables de entorno en lugar de hardcoded ports

# - Documentar nuevos servicios en sistema-puertos.md antes de implementar

#

# Última actualización: 2025-09-26

# Versión: 2.0.0
