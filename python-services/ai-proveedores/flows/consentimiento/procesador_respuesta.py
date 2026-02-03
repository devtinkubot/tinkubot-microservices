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
from templates import mensaje_consentimiento_aceptado
from templates.registro import PROMPT_INICIO_REGISTRO

logger = logging.getLogger(__name__)


async def procesar_respuesta_consentimiento(  # noqa: C901
    telefono: str,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Procesar respuesta de consentimiento para registro de proveedores.

    Args:
        telefono: Número de teléfono del proveedor
        flujo: Diccionario con el estado actual del flujo
        carga: Diccionario con los datos del mensaje recibido
        perfil_proveedor: Diccionario con el perfil del proveedor (si existe)

    Returns:
        Diccionario con la respuesta a enviar al proveedor
    """
    from principal import supabase  # Import dinámico para evitar circular import

    from .solicitador import solicitar_consentimiento
    from .registrador import registrar_consentimiento

    texto_mensaje = (carga.get("message") or carga.get("content") or "").strip()
    texto_min = texto_mensaje.lower()
    opcion = None

    # Debug: Log para ver qué recibimos
    logger.info(f"📝 Procesando respuesta consentimiento. Texto: '{texto_mensaje}', Carga keys: {list(carga.keys())}")

    if texto_min.startswith("1"):
        opcion = "1"
    elif texto_min.startswith("2"):
        opcion = "2"
    else:
        interpretado = interpretar_respuesta(texto_min, "consentimiento")
        if interpretado is True:
            opcion = "1"
        elif interpretado is False:
            opcion = "2"

    if opcion not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s. Opción detectada: '%s'", telefono, opcion)
        return await solicitar_consentimiento(telefono)

    proveedor_id = perfil_proveedor.get("id") if perfil_proveedor else None

    if opcion == "1":
        flujo["has_consent"] = True
        post_consent_state = flujo.pop("post_consent_state", None)
        if post_consent_state:
            flujo["state"] = post_consent_state
        else:
            flujo["state"] = "awaiting_menu_option"
        await establecer_flujo(telefono, flujo)

        if supabase and proveedor_id:
            try:
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(
                        {
                            "has_consent": True,
                            "updated_at": datetime.now().isoformat(),
                        }
                    )
                    .eq("id", proveedor_id)
                    .execute(),
                    label="providers.update_consent_true",
                )
            except Exception as exc:
                logger.error(
                    "No se pudo actualizar flag de consentimiento para %s: %s",
                    telefono,
                    exc,
                )

        await registrar_consentimiento(
            proveedor_id, telefono, carga, "accepted"
        )
        logger.info("Consentimiento aceptado por proveedor %s", telefono)

        # Determinar si el usuario está COMPLETAMENTE registrado (no solo consentimiento)
        # Un usuario con solo consentimiento no está completamente registrado
        esta_registrado_completo = bool(
            perfil_proveedor
            and perfil_proveedor.get("id")
            and perfil_proveedor.get("full_name")  # Verificar que tiene datos completos
            # Fase 4: Eliminada verificación de profession
        )

        if post_consent_state == "awaiting_city":
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_consentimiento_aceptado()},
                    {"response": PROMPT_INICIO_REGISTRO},
                ],
            }

        return construir_respuesta_consentimiento_aceptado(esta_registrado_completo)

    # Rechazo de consentimiento
    if supabase and proveedor_id:
        try:
            await run_supabase(
                lambda: supabase.table("providers")
                .update(
                    {
                        "has_consent": False,
                        "updated_at": datetime.now().isoformat(),
                    }
                )
                .eq("id", proveedor_id)
                .execute(),
                label="providers.update_consent_false",
            )
        except Exception as exc:
            logger.error(
                "No se pudo marcar rechazo de consentimiento para %s: %s", telefono, exc
            )

    await registrar_consentimiento(
        proveedor_id, telefono, carga, "declined"
    )
    await reiniciar_flujo(telefono)
    logger.info("Consentimiento rechazado por proveedor %s", telefono)

    return construir_respuesta_consentimiento_rechazado()
