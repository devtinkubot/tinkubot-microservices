"""
Configuración de logging estructurado con JSON y correlation IDs.

Este módulo proporciona un sistema de logging estructurado que:
- Emite logs en formato JSON para fácil parsing
- Incluye correlation IDs para tracing distribuido
- Soporta context variables para metadata automática
- Es compatible con el sistema de logging estándar de Python
"""

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variables para correlation tracking
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def get_correlation_id() -> Optional[str]:
    """Obtiene el correlation ID del contexto actual."""
    return correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """
    Establece un correlation ID en el contexto.

    Args:
        cid: ID existente o None para generar uno nuevo

    Returns:
        El correlation ID establecido
    """
    cid = cid or str(uuid.uuid4())
    correlation_id.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Limpia el correlation ID del contexto."""
    correlation_id.set(None)


def set_request_context(**kwargs) -> None:
    """
    Establece metadata adicional en el contexto de la request.

    Args:
        **kwargs: Pares clave-valor a agregar al contexto
    """
    current = request_context.get({})
    current.update(kwargs)
    request_context.set(current)


def clear_request_context() -> None:
    """Limpia el contexto de la request."""
    request_context.set({})


class StructuredFormatter(logging.Formatter):
    """
    Formatter que produce logs en formato JSON estructurado.

    Incluye automáticamente:
    - Timestamp ISO 8601
    - Correlation ID del contexto
    - Level, logger name, message
    - Extra fields pasados al log
    """

    def __init__(self, service_name: str = "ai-clientes"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el record como JSON."""
        # Base structure
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        # Add correlation ID if available
        cid = get_correlation_id()
        if cid:
            log_data["correlation_id"] = cid

        # Add request context if available
        ctx = request_context.get({})
        if ctx:
            log_data["context"] = ctx

        # Add location info
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "asctime",
            }:
                extra_fields[key] = value

        if extra_fields:
            log_data["extra"] = extra_fields

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_data["stack_trace"] = self.formatStack(record.stack_info)

        # Convert to JSON
        import json
        try:
            return json.dumps(log_data, ensure_ascii=False, default=str)
        except Exception:
            # Fallback a string simple si JSON falla
            return str(log_data)


class HumanReadableFormatter(logging.Formatter):
    """
    Formatter para desarrollo con output legible pero estructurado.
    """

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Formatea el record de forma legible."""
        # Timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Color del nivel
        color = self.COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:8}{self.RESET}"

        # Correlation ID
        cid = get_correlation_id()
        cid_str = f"[{cid[:8]}] " if cid else ""

        # Mensaje base
        base = f"{timestamp} {level} {cid_str}{record.name}: {record.getMessage()}"

        # Agregar contexto si existe
        ctx = request_context.get({})
        if ctx:
            context_str = " | ".join(f"{k}={v}" for k, v in ctx.items() if v is not None)
            if context_str:
                base += f" | {context_str}"

        # Agregar exception si existe
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


def configure_logging(
    level: str = "INFO",
    json_output: bool = None,
    service_name: str = "ai-clientes",
) -> None:
    """
    Configura el sistema de logging estructurado.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        json_output: True para JSON, False para humano-legible.
                    None = auto-detect desde LOG_FORMAT env var
        service_name: Nombre del servicio para los logs
    """
    # Detectar formato automáticamente si no se especifica
    if json_output is None:
        json_output = os.getenv("LOG_FORMAT", "json").lower() == "json"

    # Crear formatter apropiado
    if json_output:
        formatter = StructuredFormatter(service_name=service_name)
    else:
        formatter = HumanReadableFormatter()

    # Configurar handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remover handlers existentes
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    # Agregar nuevo handler
    root_logger.addHandler(handler)

    # Configurar loggers de terceros
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado.

    Args:
        name: Nombre del logger (usualmente __name__)

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
