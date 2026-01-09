"""Servicio de gestión de consentimiento de proveedores."""
import json
import logging
import unicodedata
from datetime import datetime
from typing import Any, Dict, Optional

from templates.prompts import (
    consent_acknowledged_message,
    consent_declined_message,
    consent_prompt_messages,
    provider_main_menu_message,
    provider_post_registration_menu_message,
)

from utils.db_utils import run_supabase

# Importar funciones de flujo
from services.flow_service import establecer_flujo, reiniciar_flujo

logger = logging.getLogger(__name__)


async def solicitar_consentimiento_proveedor(phone: str) -> Dict[str, Any]:
    """Generar mensajes de solicitud de consentimiento para proveedores."""
    prompts = consent_prompt_messages()
    messages = [{"response": text} for text in prompts]
    return {"success": True, "messages": messages}


def interpretar_respuesta_usuario(
    text: Optional[str], modo: str = "menu"
) -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-4, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3", "4" o None
        - modo="consentimiento": True, False o None
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización unificada
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

    # Modo consentimiento (sí/no)
    if modo == "consentimiento":
        affirmative = {
            "1",
            "si",
            "s",
            "acepto",
            "autorizo",
            "confirmo",
            "claro",
            "de acuerdo",
        }
        negative = {"2", "no", "n", "rechazo", "rechazar", "declino", "no autorizo"}

        if normalized_value in affirmative:
            return True
        if normalized_value in negative:
            return False
        return None

    # Modo menú (opciones 1-4)
    if modo == "menu":
        # Opción 1 - Gestionar servicios
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "servicio" in normalized_value
            or "servicios" in normalized_value
            or "gestionar" in normalized_value
        ):
            return "1"

        # Opción 2 - Selfie
        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "selfie" in normalized_value
            or "foto" in normalized_value
            or "selfis" in normalized_value
            or "photo" in normalized_value
        ):
            return "2"

        # Opción 3 - Redes sociales
        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "red" in normalized_value
            or "social" in normalized_value
            or "instagram" in normalized_value
            or "facebook" in normalized_value
        ):
            return "3"

        # Opción 4 - Salir
        if (
            normalized_value.startswith("4")
            or normalized_value.startswith("cuatro")
            or "salir" in normalized_value
            or "terminar" in normalized_value
            or "menu" in normalized_value
            or "volver" in normalized_value
        ):
            return "4"

        return None

    # Modo no reconocido
    return None


async def registrar_consentimiento_proveedor(
    supabase, provider_id: Optional[str], phone: str,
    payload: Dict[str, Any], response: str
) -> None:
    """Persistir registro de consentimiento en tabla consents."""
    if not supabase:
        return

    try:
        consent_data = {
            "consent_timestamp": payload.get("timestamp") or datetime.utcnow().isoformat(),
            "phone": phone,
            "message_id": payload.get("id") or payload.get("message_id"),
            "exact_response": payload.get("message") or payload.get("content"),
            "consent_type": "provider_registration",
            "platform": payload.get("platform") or "whatsapp",
        }

        record = {
            "user_id": provider_id,
            "user_type": "provider",
            "response": response,
            "message_log": json.dumps(consent_data, ensure_ascii=False),
        }
        await run_supabase(
            lambda: supabase.table("consents").insert(record).execute(),
            label="consents.insert",
        )
    except Exception as exc:
        logger.error(f"No se pudo guardar consentimiento de proveedor {phone}: {exc}")


async def manejar_respuesta_consentimiento(  # noqa: C901
    phone: str,
    flow: Dict[str, Any],
    payload: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
    supabase,  # Parámetro agregado
) -> Dict[str, Any]:
    """Procesar respuesta de consentimiento para registro de proveedores."""
    message_text = (payload.get("message") or payload.get("content") or "").strip()
    lowered = message_text.lower()
    option = None

    if lowered.startswith("1"):
        option = "1"
    elif lowered.startswith("2"):
        option = "2"
    else:
        interpreted = interpretar_respuesta_usuario(lowered, "consentimiento")
        if interpreted is True:
            option = "1"
        elif interpreted is False:
            option = "2"

    if option not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s", phone)
        return await solicitar_consentimiento_proveedor(phone)

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

        await registrar_consentimiento_proveedor(
            supabase, provider_id, phone, payload, "accepted"
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
        menu_message = (
            provider_post_registration_menu_message()
            if is_fully_registered
            else provider_main_menu_message()
        )

        messages = [
            {"response": consent_acknowledged_message()},
            {"response": menu_message},
        ]
        return {
            "success": True,
            "messages": messages,
        }

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

    await registrar_consentimiento_proveedor(
        supabase, provider_id, phone, payload, "declined"
    )
    await reiniciar_flujo(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return {
        "success": True,
        "messages": [{"response": consent_declined_message()}],
    }
