"""Helpers de ingreso y dedupe para mensajes WhatsApp de proveedores."""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.redis import cliente_redis
from services.availability.estados import (
    MEDIA_STATES,
    MENU_STATES,
    ONBOARDING_STATES,
    PROFILE_COMPLETION_STATES,
)
from services.shared.interactive_controls import PROFILE_SINGLE_USE_CONTROL_IDS
from services.shared.interactive_controls import SERVICE_CONFIRM_ID
from services.shared.interactive_controls import SERVICE_CORRECT_ID
from services.shared.whatsapp_identity import normalizar_telefono_canonico

CLAVE_DEDUPE_MEDIA = "prov_media_dedupe:{}:{}"
TTL_DEDUPE_MEDIA_SEGUNDOS = int(os.getenv("PROVIDER_MEDIA_DEDUPE_TTL_SECONDS", "900"))
CLAVE_DEDUPE_INTERACTIVE = "prov_interactive_dedupe:{}:{}"
CLAVE_DEDUPE_INTERACTIVE_ACTION = "prov_interactive_action_dedupe:{}:{}:{}:{}"
TTL_DEDUPE_INTERACTIVE_SEGUNDOS = int(
    os.getenv("PROVIDER_INTERACTIVE_DEDUPE_TTL_SECONDS", "900")
)


def _obtener_cliente_redis():
    """Resuelve el cliente Redis activo respetando monkeypatches legacy."""
    principal = sys.modules.get("principal")
    if principal is not None and hasattr(principal, "cliente_redis"):
        return principal.cliente_redis
    return cliente_redis


def resolver_message_id(carga: Dict[str, Any]) -> str:
    """Obtiene el identificador estable del mensaje."""
    return str(carga.get("id") or carga.get("message_id") or "").strip()


def es_evento_multimedia(carga: Dict[str, Any]) -> bool:
    """Detecta si la carga representa un mensaje multimedia."""
    if any(
        carga.get(campo) for campo in ("image_base64", "media_base64", "file_base64")
    ):
        return True
    if carga.get("attachments") or carga.get("media"):
        return True
    contenido = carga.get("content") or carga.get("message")
    return isinstance(contenido, str) and contenido.startswith("data:image/")


def es_evento_interactivo(carga: Dict[str, Any]) -> bool:
    """Detecta si la carga representa una interacción de tipo botón/lista."""
    if carga.get("selected_option"):
        return True
    message_type = str(carga.get("message_type") or "").strip().lower()
    return message_type.startswith("interactive_")


def resumen_contexto_interactivo_semantico(
    estado: Optional[str], flujo: Optional[Dict[str, Any]]
) -> str:
    """Construye un contexto semántico para dedupe sin message_id."""
    flujo = flujo or {}
    nonce = str(flujo.get("service_add_confirmation_nonce") or "").strip()
    return f"{estado or 'unknown'}:{nonce or 'no_nonce'}"


async def es_mensaje_multimedia_duplicado(
    telefono: str,
    estado: Optional[str],
    carga: Dict[str, Any],
) -> bool:
    """Detecta duplicados multimedia usando Redis."""
    if estado not in MEDIA_STATES:
        return False
    if not es_evento_multimedia(carga):
        return False

    message_id = resolver_message_id(carga)
    if not message_id:
        return False

    redis_activo = _obtener_cliente_redis()
    creado = await redis_activo.set_if_absent(
        CLAVE_DEDUPE_MEDIA.format(telefono, message_id),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_MEDIA_SEGUNDOS,
    )
    return not creado


async def es_mensaje_interactivo_duplicado(
    telefono: str,
    estado: Optional[str],
    carga: Dict[str, Any],
    flujo: Optional[Dict[str, Any]] = None,
) -> bool:
    """Detecta duplicados de interacciones y acciones de un solo uso."""
    if (
        estado not in ONBOARDING_STATES
        and estado not in MENU_STATES
        and estado not in PROFILE_COMPLETION_STATES
    ):
        return False
    if not es_evento_interactivo(carga):
        return False

    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    if seleccionado in {SERVICE_CONFIRM_ID, SERVICE_CORRECT_ID}:
        return False
    message_id = resolver_message_id(carga)
    if not message_id:
        if seleccionado not in PROFILE_SINGLE_USE_CONTROL_IDS:
            return False
        contexto = resumen_contexto_interactivo_semantico(estado, flujo)
        redis_activo = _obtener_cliente_redis()
        creado_semantico = await redis_activo.set_if_absent(
            CLAVE_DEDUPE_INTERACTIVE_ACTION.format(
                telefono,
                estado or "unknown",
                seleccionado,
                contexto,
            ),
            {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
            expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
        )
        return not creado_semantico

    redis_activo = _obtener_cliente_redis()
    creado = await redis_activo.set_if_absent(
        CLAVE_DEDUPE_INTERACTIVE.format(telefono, message_id),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
    )
    if not creado:
        return True

    if seleccionado not in PROFILE_SINGLE_USE_CONTROL_IDS:
        return False

    contexto = resumen_contexto_interactivo_semantico(estado, flujo)
    creado_semantico = await redis_activo.set_if_absent(
        CLAVE_DEDUPE_INTERACTIVE_ACTION.format(
            telefono,
            estado or "unknown",
            seleccionado,
            contexto,
        ),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
    )
    return not creado_semantico
