"""
Procesador de respuesta de consentimiento de proveedores.

Este módulo maneja el procesamiento de la respuesta del proveedor
a la solicitud de consentimiento.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Agregar el directorio raíz al sys.path para imports absolutos
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from flows.constructores import (
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_solicitud_consentimiento,
)
from flows.sesion import establecer_flujo, reiniciar_flujo
from flows.interpretacion import interpretar_respuesta
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def procesar_respuesta_consentimiento(  # noqa: C901
    phone: str,
    flow: Dict[str, Any],
    payload: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Procesar respuesta de consentimiento para registro de proveedores.

    Args:
        phone: Número de teléfono del proveedor
        flow: Diccionario con el estado actual del flujo
        payload: Diccionario con los datos del mensaje recibido
        provider_profile: Diccionario con el perfil del proveedor (si existe)

    Returns:
        Diccionario con la respuesta a enviar al proveedor
    """
    from main import supabase  # Import dinámico para evitar circular import

    from .solicitador import solicitar_consentimiento
    from .registrador import registrar_consentimiento

    message_text = (payload.get("message") or payload.get("content") or "").strip()
    lowered = message_text.lower()
    option = None

    if lowered.startswith("1"):
        option = "1"
    elif lowered.startswith("2"):
        option = "2"
    else:
        interpreted = interpretar_respuesta(lowered, "consentimiento")
        if interpreted is True:
            option = "1"
        elif interpreted is False:
            option = "2"

    if option not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s", phone)
        return await solicitar_consentimiento(phone)

    provider_id = provider_profile.get("id") if provider_profile else None

    if option == "1":
        flow["has_consent"] = True
        flow["state"] = "awaiting_menu_option"
        await establecer_flujo(phone, flow)

        if supabase and provider_id:
            try:
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(
                        {
                            "has_consent": True,
                            "updated_at": datetime.now().isoformat(),
                        }
                    )
                    .eq("id", provider_id)
                    .execute(),
                    label="providers.update_consent_true",
                )
            except Exception as exc:
                logger.error(
                    "No se pudo actualizar flag de consentimiento para %s: %s",
                    phone,
                    exc,
                )

        await registrar_consentimiento(
            provider_id, phone, payload, "accepted"
        )
        logger.info("Consentimiento aceptado por proveedor %s", phone)

        # Determinar si el usuario está COMPLETAMENTE registrado (no solo consentimiento)
        # Un usuario con solo consentimiento no está completamente registrado
        is_fully_registered = bool(
            provider_profile
            and provider_profile.get("id")
            and provider_profile.get("full_name")  # Verificar que tiene datos completos
            and provider_profile.get("profession")
        )

        return construir_respuesta_consentimiento_aceptado(is_fully_registered)

    # Rechazo de consentimiento
    if supabase and provider_id:
        try:
            await run_supabase(
                lambda: supabase.table("providers")
                .update(
                    {
                        "has_consent": False,
                        "updated_at": datetime.now().isoformat(),
                    }
                )
                .eq("id", provider_id)
                .execute(),
                label="providers.update_consent_false",
            )
        except Exception as exc:
            logger.error(
                "No se pudo marcar rechazo de consentimiento para %s: %s", phone, exc
            )

    await registrar_consentimiento(
        provider_id, phone, payload, "declined"
    )
    await reiniciar_flujo(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return construir_respuesta_consentimiento_rechazado()
