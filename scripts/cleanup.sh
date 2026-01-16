#!/bin/bash
# Limpieza de código - remueve archivos temporales y formatea código
# Uso: ./scripts/cleanup.sh

set -e

echo "🧹 Limpiando código..."

# 1. Remover __pycache__
echo "  - Removiendo __pycache__..."
find python-services -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 2. Remover .pyc
echo "  - Removiendo archivos .pyc..."
find python-services -type f -name "*.pyc" -delete

# 3. Remover .pyo
echo "  - Removiendo archivos .pyo..."
find python-services -type f -name "*.pyo" -delete

# 4. Formatear con black (si está instalado)
if command -v black &> /dev/null; then
    echo "  - Formateando con black..."
    black python-services/ai-clientes
else
    echo "  ⚠️  black no instalado, omitiendo..."
fi

# 5. Ordenar imports con isort (si está instalado)
if command -v isort &> /dev/null; then
    echo "  - Ordenando imports con isort..."
    isort python-services/ai-clientes
else
    echo "  ⚠️  isort no instalado, omitiendo..."
fi

# 6. Lint con ruff (si está instalado)
if command -v ruff &> /dev/null; then
    echo "  - Ejecutando ruff..."
    ruff check python-services/ai-clientes --fix
else
    echo "  ⚠️  ruff no instalado, omitiendo..."
fi

echo "✅ Limpieza completada"
