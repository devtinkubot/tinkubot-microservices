"""Handler de onboarding para el teléfono real."""

import re
from typing import Any, Dict, Optional

from services.onboarding.event_payloads import payload_real_phone
from services.onboarding.event_publisher import (
    EVENT_TYPE_REAL_PHONE,
    onboarding_async_persistence_enabled,
    publicar_evento_onboarding,
)
from services.onboarding.registration.normalizacion import _normalizar_telefono_ecuador
from utils import limpiar_espacios
from templates.onboarding.ciudad import preguntar_ciudad
from templates.onboarding.telefono import error_real_phone_invalido


def _normalizar_real_phone(valor: str) -> Optional[str]:
    limpio = limpiar_espacios(valor)
    if not limpio:
        return None

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

    return _normalizar_telefono_ecuador(compactado)


async def manejar_espera_real_phone_onboarding(
    flujo: Dict[str, Any], texto_mensaje: Optional[str]
) -> Dict[str, Any]:
    """Procesa la captura del número real durante onboarding."""
    real_phone = _normalizar_real_phone(texto_mensaje or "")

    if not real_phone:
        return {
            "success": True,
            "messages": [{"response": error_real_phone_invalido()}],
        }

    flujo["real_phone"] = real_phone
    flujo["requires_real_phone"] = False
    flujo["state"] = "onboarding_city"
    if onboarding_async_persistence_enabled():
        await publicar_evento_onboarding(
            event_type=EVENT_TYPE_REAL_PHONE,
            flujo=flujo,
            payload=payload_real_phone(
                real_phone=real_phone,
                checkpoint="onboarding_city",
            ),
        )

    return {
        "success": True,
        "messages": [{"response": preguntar_ciudad()}],
    }
