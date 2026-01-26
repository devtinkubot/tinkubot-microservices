# Export centralizado de modelos del servicio ai-proveedores
# Este módulo proporciona acceso unificado a todos los modelos Pydantic

# Modelos de registro
from .registro import (
    SolicitudRegistroProveedor
)

# Modelos de mensajes
from .mensajes import (
    SolicitudMensajeWhatsApp,
    RecepcionMensajeWhatsApp
)

# Modelos de sistema
from .sistema import (
    RespuestaSalud
)

# Modelos de proveedores (compatibilidad con esquema unificado)
from .proveedores import (
    SolicitudCreacionProveedor,
    RespuestaProveedor
)

__all__ = [
    # Registro
    "SolicitudRegistroProveedor",
    # Mensajes
    "SolicitudMensajeWhatsApp",
    "RecepcionMensajeWhatsApp",
    # Sistema
    "RespuestaSalud",
    # Proveedores (compatibilidad con esquema unificado)
    "SolicitudCreacionProveedor",
    "RespuestaProveedor",
]
