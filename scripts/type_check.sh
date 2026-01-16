#!/bin/bash
# Type checking con Pyright para ai-clientes service
# Uso: ./scripts/type_check.sh [archivo_o_directorio]

set -e

PYTHONPATH=/home/du/produccion/tinkubot-microservices/python-services/ai-clientes

echo "🔍 Ejecutando Pyright type checking..."

if [ -n "$1" ]; then
    # Validar archivo o directorio específico
    echo "📁 Validando: $1"
    pyright "$1"
else
    # Validar todos los archivos de servicios
    echo "📁 Validando todos los servicios..."
    pyright python-services/ai-clientes/services/service_*.py
fi

echo "✅ Type checking completado sin errores"
