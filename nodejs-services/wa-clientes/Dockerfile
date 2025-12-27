# TinkuBot - WhatsApp Clientes Service
FROM node:20-slim

# Metadata labels
LABEL maintainer="TinkuBot Team"
LABEL description="WhatsApp Bot para clientes con Puppeteer"
LABEL version="1.0.0"

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
ENV PUPPETEER_SKIP_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV NODE_ENV=production

# Configurar directorio de trabajo
WORKDIR /usr/src/app

# Copiar archivos de dependencias e instalar (rápido y reproducible)
COPY package*.json ./
# Usar npm install y omitir devDependencies para imagen más ligera
RUN npm install --omit=dev --production

# Copiar el resto del código de la aplicación
COPY . .

# Crear usuario no root para seguridad
RUN addgroup --system appgroup && adduser --system --group appuser
RUN chown -R appuser:appgroup /usr/src/app
USER appuser

# Exponer el puerto (dinámico mediante variable de entorno)
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD node -e "require('http').get('http://localhost:5001/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Comando para iniciar el servicio
CMD [ "npm", "start" ]
