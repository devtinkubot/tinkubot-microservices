#!/bin/bash

# Script para configurar Husky en todos los servicios Node.js

echo "Configurando Husky para pre-commit hooks..."

# Directorios de servicios Node.js
services=("nodejs-services/whatsapp-service-clientes" "nodejs-services/whatsapp-service-proveedores" "nodejs-services/frontend-service")

for service in "${services[@]}"; do
    if [ -d "$service" ]; then
        echo "Configurando Husky en $service..."
        cd "$service"

        # Instalar dependencias
        npm install

        # Inicializar Husky
        npx husky install

        # Crear pre-commit hook
        npx husky add .husky/pre-commit "npx lint-staged"

        cd ../..
    else
        echo "Directorio $service no encontrado"
    fi
done

echo "Configuración de Husky completada"