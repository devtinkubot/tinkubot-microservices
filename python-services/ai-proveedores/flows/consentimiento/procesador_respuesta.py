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

from flows.constructores import (  # noqa: E402
    construir_respuesta_consentimiento_aceptado,
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_revision,
    construir_respuesta_revision_con_menu_limitado,
)
from flows.interpretacion import interpretar_respuesta  # noqa: E402
from flows.sesion import establecer_flujo, reiniciar_flujo  # noqa: E402
from infrastructure.database import run_supabase  # noqa: E402
from templates.registro import (  # noqa: E402
    preguntar_real_phone,
    solicitar_ciudad_registro,
)

logger = logging.getLogger(__name__)


def _resolver_opcion_consentimiento(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea respuesta interactiva o textual a 1/2 para consentimiento."""
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_min = texto_mensaje.lower()

    if seleccionado in {
        "continue_provider_onboarding",
        "continuar",
        "continue",
        "1",
    }:
        return "1"
    if seleccionado in {"2", "rechazar", "decline", "cancelar"}:
        return "2"

    if texto_min.startswith("1"):
        return "1"
    if texto_min.startswith("2"):
        return "2"

    interpretado = interpretar_respuesta(texto_min, "consentimiento")
    if interpretado is True:
        return "1"
    if interpretado is False:
        return "2"
    return None


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

    from .registrador import registrar_consentimiento
    from .solicitador import solicitar_consentimiento
    from services.sesion_proveedor import perfil_tiene_menu_limitado

    texto_mensaje = (carga.get("message") or carga.get("content") or "").strip()
    opcion = _resolver_opcion_consentimiento(carga)

    logger.info(
        "📝 Procesando respuesta consentimiento. Texto: '%s', selected_option='%s', Carga keys: %s",
        texto_mensaje,
        carga.get("selected_option"),
        list(carga.keys()),
    )

    if opcion not in {"1", "2"}:
        logger.info(
            "Reenviando solicitud de consentimiento a %s. Opción detectada: '%s'",
            telefono,
            opcion,
        )
        return await solicitar_consentimiento(telefono)

    proveedor_id = perfil_proveedor.get("id") if perfil_proveedor else None

    if opcion == "1":
        # Determinar si está completamente registrado (no solo consentimiento).
        # Un usuario con solo consentimiento no está completamente registrado
        esta_registrado_completo = bool(
            perfil_proveedor
            and perfil_proveedor.get("id")
            and perfil_proveedor.get("full_name")  # Verificar que tiene datos completos
            # Fase 4: Eliminada verificación de profession
        )
        esta_verificado = bool(perfil_proveedor and perfil_proveedor.get("verified"))
        menu_limitado = perfil_tiene_menu_limitado(perfil_proveedor)

        flujo["has_consent"] = True
        post_consent_state = flujo.pop("post_consent_state", None)
        if post_consent_state:
            flujo["state"] = post_consent_state
        elif not esta_registrado_completo:
            requires_real_phone = bool(
                flujo.get("requires_real_phone")
                and not (
                    flujo.get("real_phone")
                    or (perfil_proveedor or {}).get("real_phone")
                )
            )
            flujo["state"] = (
                "awaiting_real_phone" if requires_real_phone else "awaiting_city"
            )
        elif not esta_verificado:
            flujo["state"] = (
                "awaiting_menu_option" if menu_limitado else "pending_verification"
            )
            flujo["menu_limitado"] = menu_limitado
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

        await registrar_consentimiento(proveedor_id, telefono, carga, "accepted")
        logger.info("Consentimiento aceptado por proveedor %s", telefono)

        if flujo.get("state") == "awaiting_real_phone":
            return {
                "success": True,
                "messages": [
                    {"response": preguntar_real_phone()},
                ],
            }

        if flujo.get("state") == "awaiting_city":
            return {
                "success": True,
                "messages": [
                    solicitar_ciudad_registro(),
                ],
            }

        if flujo.get("state") == "pending_verification" and perfil_proveedor:
            nombre_proveedor = perfil_proveedor["full_name"]
            return construir_respuesta_revision(nombre_proveedor)
        if (
            flujo.get("state") == "awaiting_menu_option"
            and menu_limitado
            and perfil_proveedor
        ):
            nombre_proveedor = perfil_proveedor["full_name"]
            return construir_respuesta_revision_con_menu_limitado(nombre_proveedor)

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

    await registrar_consentimiento(proveedor_id, telefono, carga, "declined")
    await reiniciar_flujo(telefono)
    logger.info("Consentimiento rechazado por proveedor %s", telefono)

    return construir_respuesta_consentimiento_rechazado()
