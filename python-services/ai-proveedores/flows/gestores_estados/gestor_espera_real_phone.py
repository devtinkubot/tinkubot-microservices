"""Manejador del estado awaiting_real_phone."""

import re
from typing import Any, Dict, Optional

from services.registro.normalizacion import _normalizar_telefono_ecuador
from services.servicios_proveedor.utilidades import limpiar_espacios
from templates.registro import (
    error_real_phone_invalido,
    preguntar_ciudad,
)


def _normalizar_real_phone(valor: str) -> Optional[str]:
    limpio = limpiar_espacios(valor)
    if not limpio:
        return None

    # Remover separadores comunes sin perder prefijo +
    compactado = re.sub(r"[\s\-\(\)\.]+", "", limpio)
    if not compactado:
        return None

    if compactado.startswith("+"):
        digitos = compactado[1:]
    else:
        digitos = compactado

    if not digitos.isdigit():
        return None

    if len(digitos) < 10 or len(digitos) > 20:
        return None

    # Normalizar formato ecuatoriano (09... → 5939..., +593... → 593...)
    return _normalizar_telefono_ecuador(compactado)


def manejar_espera_real_phone(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la captura del número real para proveedores con @lid."""
    real_phone = _normalizar_real_phone(texto_mensaje or "")

    if not real_phone:
        return {
            "success": True,
            "messages": [{"response": error_real_phone_invalido()}],
        }

    flujo["real_phone"] = real_phone
    flujo["requires_real_phone"] = False
    flujo["state"] = "awaiting_city"

    return {
        "success": True,
        "messages": [{"response": preguntar_ciudad()}],
    }
