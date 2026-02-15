"""
Middleware de FastAPI para correlation IDs y contexto de request.

Este middleware:
- Extrae o genera un correlation ID para cada request
- Lo propaga a las respuestas HTTP
- Establece contexto estructurado para logging
- Limpia el contexto al finalizar la request
"""

import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from infrastructure.logging.structured_logger import (
    set_correlation_id,
    clear_correlation_id,
    set_request_context,
    clear_request_context,
    get_correlation_id,
)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware que maneja correlation IDs para tracing distribuido.

    Flujo:
    1. Busca X-Correlation-ID en headers de la request
    2. Si no existe, genera un UUID nuevo
    3. Establece el ID en context vars para logging automático
    4. Agrega el ID a la response
    5. Limpia el contexto al finalizar
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"
    REQUEST_ID_HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Procesa la request con correlation tracking."""
        # 1. Obtener o generar correlation ID
        correlation_id = request.headers.get(self.CORRELATION_ID_HEADER)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # 2. Establecer en contexto
        set_correlation_id(correlation_id)

        # 3. Establecer contexto de request
        set_request_context(
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) or None,
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:100],  # Truncar
        )

        # 4. Tiempo de inicio
        start_time = time.monotonic()

        try:
            # 5. Procesar request
            response = await call_next(request)

            # 6. Agregar headers de correlation a la response
            response.headers[self.CORRELATION_ID_HEADER] = correlation_id

            # También agregar como X-Request-ID para compatibilidad
            response.headers[self.REQUEST_ID_HEADER] = correlation_id

            # 7. Agregar timing
            duration_ms = (time.monotonic() - start_time) * 1000
            response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"

            return response

        finally:
            # 8. Siempre limpiar contexto
            clear_correlation_id()
            clear_request_context()

    def _get_client_ip(self, request: Request) -> str:
        """Obtiene la IP del cliente, considerando proxies."""
        # X-Forwarded-For puede tener múltiples IPs
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Tomar la primera (cliente original)
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP usado por algunos proxies
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Direct connection
        if request.client:
            return request.client.host

        return "unknown"


def setup_logging_middleware(app, service_name: str = "ai-clientes"):
    """
    Configura el middleware de logging y correlation IDs.

    Args:
        app: Aplicación FastAPI
        service_name: Nombre del servicio para logs
    """
    from infrastructure.logging.structured_logger import configure_logging

    # Configurar logging estructurado
    log_level = getattr(app, "log_level", "INFO")
    configure_logging(
        level=log_level,
        service_name=service_name,
    )

    # Agregar middleware de correlation ID
    app.add_middleware(CorrelationIdMiddleware)

    return app
