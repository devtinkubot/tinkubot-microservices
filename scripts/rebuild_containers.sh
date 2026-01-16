#!/bin/bash
# Reconstrucción de contenedores Docker
# Uso: ./scripts/rebuild_containers.sh

set -e

echo "🐳 Reconstrucción de contenedores Docker..."

# 1. Limpiar contenedores y volúmenes
echo "🧹 Limpiando contenedores viejos..."
docker compose down -v

# 2. Reconstruir imágenes sin cache
echo "🔨 Reconstruyendo imágenes..."
docker compose build --no-cache --pull

# 3. Iniciar contenedores
echo "🚀 Iniciando contenedores..."
docker compose up -d

# 4. Esperar que los servicios estén saludables
echo "⏳ Esperando servicios saludables..."
sleep 10

# 5. Mostrar status
echo "📊 Status de contenedores:"
docker compose ps

echo ""
echo "✅ Reconstrucción completa!"
echo "📝 Ver logs con: docker compose logs -f"
echo "🔍 Inspeccionar con: docker compose exec ai-clientes bash"
