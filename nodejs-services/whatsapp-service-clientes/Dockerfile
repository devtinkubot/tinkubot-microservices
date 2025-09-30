# Usar una imagen base de Node.js
FROM node:20-slim

# Instalar dependencias necesarias para Puppeteer (Chrome)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    wget \
    xdg-utils \
    chromium \
    --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*

# Usar Chromium del sistema y evitar su descarga durante npm install
ENV PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Configurar directorio de trabajo
WORKDIR /usr/src/app

# Copiar archivos de dependencias e instalar (rápido y reproducible)
COPY package*.json ./
# Usar npm ci y omitir devDependencies para imagen más ligera
RUN npm ci --omit=dev

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 7001

# Comando para iniciar el servicio
CMD [ "npm", "start" ]
