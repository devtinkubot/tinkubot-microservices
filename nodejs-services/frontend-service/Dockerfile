FROM node:20-slim

WORKDIR /app

# Copiar package.json y package-lock.json
COPY package*.json ./
# Instalar dependencias de forma reproducible y sin devDependencies
RUN npm ci --omit=dev

# Copiar el resto de la aplicación
COPY . .

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 6002

# Comando para iniciar la aplicación
CMD ["npm", "start"]
