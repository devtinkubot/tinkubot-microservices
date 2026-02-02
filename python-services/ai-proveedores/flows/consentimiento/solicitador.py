"""
Solicitador de consentimiento para proveedores.

Este módulo contiene la función para solicitar consentimiento
a los proveedores durante el proceso de registro.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from flows.constructores import construir_respuesta_solicitud_consentimiento

logger = logging.getLogger(__name__)


async def solicitar_consentimiento(telefono: str) -> Dict[str, Any]:
    """
    Generar mensajes de solicitud de consentimiento para proveedores.

    Args:
        telefono: Número de teléfono del proveedor

    Returns:
        Diccionario con la respuesta de solicitud de consentimiento
    """
    return construir_respuesta_solicitud_consentimiento()
