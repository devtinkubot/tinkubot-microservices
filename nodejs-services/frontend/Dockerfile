FROM node:20-slim

WORKDIR /app

# Copiar package.json y package-lock.json
COPY package*.json ./
# Instalar dependencias de forma reproducible y sin devDependencies
RUN npm install --omit=dev --production

# Copiar el resto de la aplicación
COPY . .

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 5000

# Comando para iniciar la aplicación
CMD ["npm", "start"]
