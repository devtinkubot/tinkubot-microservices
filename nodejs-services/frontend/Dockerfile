FROM node:20-slim

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

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 5000

# Comando para iniciar la aplicación
CMD ["npm", "start"]
