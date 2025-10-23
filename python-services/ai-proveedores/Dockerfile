# Dockerfile para AI Service Proveedores - Versión Optimizada con Alpine
FROM python:3.11-slim

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para mejor caché de Docker
COPY ai-proveedores/requirements.txt ./requirements.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente del servicio
COPY ai-proveedores/ .

# (Opcional) Copiar librería compartida si se requiere en el futuro
COPY shared-lib ./shared_lib

# Crear usuario no root (Debian/Ubuntu)
RUN useradd -m -u 1000 -s /bin/sh appuser && chown -R appuser:appuser /app
USER appuser

# Exponer puerto
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
