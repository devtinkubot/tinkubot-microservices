"""Helpers de ingreso y dedupe para mensajes WhatsApp de proveedores."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from infrastructure.redis import cliente_redis
from services.availability.estados import (
    MEDIA_STATES,
    MENU_STATES,
    ONBOARDING_STATES,
    PROFILE_COMPLETION_STATES,
)
from services.maintenance.actualizar_servicios import actualizar_servicios
from services.onboarding.progress import (
    es_perfil_onboarding_completo,
    resolver_checkpoint_onboarding_desde_perfil,
)
from templates.onboarding.registration import (
    PROFILE_SINGLE_USE_CONTROL_IDS,
    SERVICE_CONFIRM_ID,
    SERVICE_CORRECT_ID,
)

CLAVE_DEDUPE_MEDIA = "prov_media_dedupe:{}:{}"
TTL_DEDUPE_MEDIA_SEGUNDOS = int(os.getenv("PROVIDER_MEDIA_DEDUPE_TTL_SECONDS", "900"))
CLAVE_DEDUPE_INTERACTIVE = "prov_interactive_dedupe:{}:{}"
CLAVE_DEDUPE_INTERACTIVE_ACTION = "prov_interactive_action_dedupe:{}:{}:{}:{}"
TTL_DEDUPE_INTERACTIVE_SEGUNDOS = int(
    os.getenv("PROVIDER_INTERACTIVE_DEDUPE_TTL_SECONDS", "900")
)


def normalizar_telefono_canonico(raw_from: str, raw_phone: str) -> str:
    """Normaliza el teléfono del remitente al formato canónico del servicio."""

    def _normalizar_jid(valor: str) -> Optional[str]:
        texto = (valor or "").strip()
        if "@" not in texto:
            return None

        user, server = texto.split("@", 1)
        user = user.strip()
        server = server.strip().lower()
        if not user or not server:
            return None
        return f"{user}@{server}"

    def _extraer_user_jid(valor: str) -> str:
        texto = (valor or "").strip()
        if not texto:
            return ""
        if "@" in texto:
            return texto.split("@", 1)[0].strip()
        return texto

    jid = _normalizar_jid(raw_from) or _normalizar_jid(raw_phone)
    if jid:
        return jid

    user = _extraer_user_jid(raw_phone)
    if not user:
        return ""
    return f"{user}@s.whatsapp.net"


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


def normalizar_lista_servicios_flujo(flujo: Dict[str, Any]) -> list[str]:
    """Normaliza la lista de servicios temporales/persistidos del flujo."""
    servicios = flujo.get("servicios_temporales")
    if servicios is None:
        servicios = flujo.get("services")
    resultado: list[str] = []
    for servicio in list(servicios or []):
        texto = str(servicio or "").strip()
        if texto and texto not in resultado:
            resultado.append(texto)
    return resultado


async def sincronizar_servicios_si_cambiaron(
    flujo_anterior: Dict[str, Any],
    flujo_actual: Dict[str, Any],
    *,
    supabase: Any,
    logger: Any,
) -> bool:
    """Persiste servicios cuando el conjunto cambió entre estados."""
    provider_id = str(
        flujo_actual.get("provider_id") or flujo_anterior.get("provider_id") or ""
    ).strip()
    if not provider_id or not supabase:
        return False

    servicios_previos = normalizar_lista_servicios_flujo(flujo_anterior)
    servicios_actuales = normalizar_lista_servicios_flujo(flujo_actual)
    if servicios_previos == servicios_actuales:
        return False

    try:
        servicios_persistidos = await actualizar_servicios(
            provider_id,
            servicios_actuales,
        )
    except Exception as exc:
        logger.warning(
            "No se pudieron sincronizar los servicios persistidos para %s: %s",
            provider_id,
            exc,
        )
        return False

    flujo_actual["services"] = servicios_persistidos
    if "servicios_temporales" in flujo_actual:
        flujo_actual["servicios_temporales"] = list(servicios_persistidos)
    return True


def rehidratar_estado_onboarding_desde_supabase(
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
) -> bool:
    """Reconstruye el estado del onboarding si Redis llegó vacío o incompleto."""
    if flujo.get("state") or not perfil_proveedor:
        return False

    checkpoint = resolver_checkpoint_onboarding_desde_perfil(perfil_proveedor)
    if not checkpoint:
        return False

    flujo["state"] = checkpoint
    flujo["onboarding_step"] = checkpoint
    if perfil_proveedor.get("onboarding_step_updated_at") is not None:
        flujo["onboarding_step_updated_at"] = perfil_proveedor.get(
            "onboarding_step_updated_at"
        )
    if checkpoint == "awaiting_menu_option" and not es_perfil_onboarding_completo(
        perfil_proveedor
    ):
        flujo["mode"] = "registration"
    elif checkpoint == "awaiting_menu_option":
        flujo.pop("mode", None)
    return True


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

    creado = await cliente_redis.set_if_absent(
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
        creado_semantico = await cliente_redis.set_if_absent(
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

    creado = await cliente_redis.set_if_absent(
        CLAVE_DEDUPE_INTERACTIVE.format(telefono, message_id),
        {"state": estado, "processed_at": datetime.now(timezone.utc).isoformat()},
        expire=TTL_DEDUPE_INTERACTIVE_SEGUNDOS,
    )
    if not creado:
        return True

    if seleccionado not in PROFILE_SINGLE_USE_CONTROL_IDS:
        return False

    contexto = resumen_contexto_interactivo_semantico(estado, flujo)
    creado_semantico = await cliente_redis.set_if_absent(
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
