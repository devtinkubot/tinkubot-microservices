# TinkuBot - Frontend Dashboard
FROM node:20-slim

# Metadata labels
LABEL maintainer="TinkuBot Team"
LABEL description="Dashboard web de administración"
LABEL version="1.0.0"

WORKDIR /app

# Actualizar npm para soporte completo de workspaces (workspace:*)
RUN npm install -g npm@11.6.2

# Copiar manifiestos para instalar dependencias con workspaces
COPY package.json ./
COPY apps/admin-dashboard/package.json ./apps/admin-dashboard/
# El paquete api-client se necesita completo por la referencia file:
COPY packages/api-client ./packages/api-client/

# Instalar dependencias (incluye dev para poder compilar con Vite)
RUN npm install

# Copiar el resto de la aplicación
COPY . .

# Compilar el dashboard con Vite
RUN npm run build

# Remover dependencias de desarrollo para la imagen final
RUN npm prune --omit=dev

# Set environment
ENV NODE_ENV=production

# Crear usuario no root para seguridad
RUN addgroup --system appgroup && adduser --system --group appuser
RUN chown -R appuser:appgroup /app
USER appuser

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:5000/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Comando para iniciar la aplicación
CMD ["npm", "start"]
