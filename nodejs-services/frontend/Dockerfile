FROM node:20-slim

WORKDIR /app

ENV TZ=America/Guayaquil

# Asegurar zona horaria local dentro del contenedor
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
  && rm -rf /var/lib/apt/lists/*

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

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 5000

# Comando para iniciar la aplicación
RUN groupadd -g 10001 appgroup && useradd -u 10001 -g appgroup -m -s /bin/bash appuser && chown -R appuser:appgroup /app
USER appuser
CMD ["npm", "start"]
