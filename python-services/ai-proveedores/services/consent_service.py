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


def interpretar_opcion_menu(text: Optional[str]) -> Optional[str]:
    """
    Interpretar respuesta de menú (opciones 1-4).

    Args:
        text: Texto a interpretar

    Returns:
        "1", "2", "3", "4" o None si no es reconocido
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

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


def interpretar_consentimiento(text: Optional[str]) -> Optional[bool]:
    """
    Interpretar respuesta de consentimiento (sí/no).

    Args:
        text: Texto a interpretar

    Returns:
        True para afirmativo, False para negativo, None si no es reconocido
    """
    value = (text or "").strip().lower()
    if not value:
        return None

    # Normalización
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode().strip()

    if not normalized_value:
        return None

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


def interpretar_respuesta_usuario(
    text: Optional[str], modo: str = "menu"
) -> Optional[object]:
    """
    Interpretar respuesta del usuario unificando menú y consentimiento.

    Esta función mantiene compatibilidad hacia atrás. Nuevo código debería usar
    interpretar_opcion_menu() o interpretar_consentimiento() directamente.

    Args:
        text: Texto a interpretar
        modo: "menu" para opciones 1-4, "consentimiento" para sí/no

    Returns:
        - modo="menu": "1", "2", "3", "4" o None
        - modo="consentimiento": True, False o None
    """
    if modo == "consentimiento":
        return interpretar_consentimiento(text)
    if modo == "menu":
        return interpretar_opcion_menu(text)
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


def _validar_respuesta_consentimiento(payload: Dict[str, Any]) -> Optional[str]:
    """
    Validar y normalizar respuesta de consentimiento del usuario.

    Args:
        payload: Payload con el mensaje del usuario

    Returns:
        "1" para aceptar, "2" para rechazar, None si es inválido
    """
    message_text = (payload.get("message") or payload.get("content") or "").strip()
    lowered = message_text.lower()

    # Validación directa por número
    if lowered.startswith("1"):
        return "1"
    if lowered.startswith("2"):
        return "2"

    # Validación por texto usando interpretar_consentimiento
    interpreted = interpretar_consentimiento(lowered)
    if interpreted is True:
        return "1"
    if interpreted is False:
        return "2"

    return None


async def _actualizar_estado_consentimiento(
    supabase, provider_id: Optional[str], has_consent: bool, phone: str
) -> None:
    """
    Actualizar estado de consentimiento en base de datos.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor
        has_consent: Nuevo estado de consentimiento
        phone: Teléfono del proveedor (para logs)
    """
    if not supabase or not provider_id:
        return

    try:
        await run_supabase(
            lambda: supabase.table("providers")
            .update(
                {
                    "has_consent": has_consent,
                    "updated_at": datetime.now().isoformat(),
                }
            )
            .eq("id", provider_id)
            .execute(),
            label=f"providers.update_consent_{has_consent}",
        )
    except Exception as exc:
        logger.error(
            "No se pudo actualizar flag de consentimiento para %s: %s",
            phone,
            exc,
        )


def _generar_mensaje_respuesta_consentimiento(
    provider_profile: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generar mensajes de respuesta después de procesar consentimiento.

    Args:
        provider_profile: Perfil del proveedor para determinar mensaje

    Returns:
        Diccionario con success y messages
    """
    # Determinar si el usuario está COMPLETAMENTE registrado
    is_fully_registered = bool(
        provider_profile
        and provider_profile.get("id")
        and provider_profile.get("full_name")
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


async def manejar_respuesta_consentimiento(
    phone: str,
    flow: Dict[str, Any],
    payload: Dict[str, Any],
    provider_profile: Optional[Dict[str, Any]],
    supabase,
) -> Dict[str, Any]:
    """
    Procesar respuesta de consentimiento para registro de proveedores.

    Esta función coordina la validación, persistencia y generación de mensajes
    para las respuestas de consentimiento.

    Args:
        phone: Teléfono del proveedor
        flow: Diccionario de flujo de conversación
        payload: Payload con el mensaje del usuario
        provider_profile: Perfil del proveedor (opcional)
        supabase: Cliente de Supabase

    Returns:
        Diccionario con success y messages
    """
    # Validar respuesta
    option = _validar_respuesta_consentimiento(payload)

    if option not in {"1", "2"}:
        logger.info("Reenviando solicitud de consentimiento a %s", phone)
        return await solicitar_consentimiento_proveedor(phone)

    provider_id = provider_profile.get("id") if provider_profile else None

    # Procesar aceptación
    if option == "1":
        flow["has_consent"] = True
        flow["state"] = "awaiting_menu_option"
        await establecer_flujo(phone, flow)

        # Actualizar estado en BD
        await _actualizar_estado_consentimiento(supabase, provider_id, True, phone)

        # Registrar consentimiento
        await registrar_consentimiento_proveedor(
            supabase, provider_id, phone, payload, "accepted"
        )
        logger.info("Consentimiento aceptado por proveedor %s", phone)

        # Generar mensajes de respuesta
        return _generar_mensaje_respuesta_consentimiento(provider_profile)

    # Procesar rechazo
    await _actualizar_estado_consentimiento(supabase, provider_id, False, phone)

    await registrar_consentimiento_proveedor(
        supabase, provider_id, phone, payload, "declined"
    )
    await reiniciar_flujo(phone)
    logger.info("Consentimiento rechazado por proveedor %s", phone)

    return {
        "success": True,
        "messages": [{"response": consent_declined_message()}],
    }
