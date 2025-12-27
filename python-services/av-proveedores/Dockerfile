# TinkuBot - AV Proveedores Service
FROM python:3.11-slim

# Metadata labels
LABEL maintainer="TinkuBot Team"
LABEL description="Servicio de verificación de disponibilidad de proveedores"
LABEL version="1.0.0"

WORKDIR /app

# Instalar dependencias del sistema (curl para health checks)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Crear usuario no root para seguridad
RUN addgroup --system appgroup && adduser --system --group appuser
RUN chown -R appuser:appgroup /app
USER appuser

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV AV_PROVEEDORES_PUERTO=8005

# Exponer puerto
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8005/salud || exit 1

# Comando de inicio
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${AV_PROVEEDORES_PUERTO:-8005}"]
