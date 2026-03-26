"""Lógica de negocio del consentimiento de onboarding."""

import logging
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.onboarding import session as onboarding_session
from services.onboarding.messages import (
    construir_respuesta_solicitud_consentimiento,
)
from services.onboarding.registrador import registrar_consentimiento
from services.onboarding.registration import asegurar_proveedor_borrador
from services.onboarding.registration.normalizacion import (
    _normalizar_telefono_ecuador,
)
from services.onboarding.whatsapp_identity import persistir_identities_whatsapp
from services.shared import (
    SELECCION_CONSENTIMIENTO_AFIRMATIVA,
    VALOR_OPCION_AFIRMATIVA,
)
from templates.onboarding.ciudad import solicitar_ciudad_registro
from templates.onboarding.telefono import preguntar_real_phone

logger = logging.getLogger(__name__)


def _extraer_real_phone_desde_telefono(telefono: Optional[str]) -> Optional[str]:
    """Devuelve `real_phone` solo si el JID observado contiene un número usable."""
    jid = str(telefono or "").strip()
    if not jid.endswith("@s.whatsapp.net"):
        return None

    user = jid.split("@", 1)[0].strip()
    if not re.fullmatch(r"\+?\d{10,20}", user or ""):
        return None

    return _normalizar_telefono_ecuador(user)


def _construir_payload_metadata_whatsapp(
    flujo: Dict[str, Any],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "updated_at": datetime.now().isoformat(),
    }
    for field in ("display_name", "formatted_name", "first_name", "last_name"):
        valor = flujo.get(field)
        texto = str(valor or "").strip()
        if texto:
            payload[field] = texto
    return payload


def _construir_payload_redes_onboarding(flujo: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "updated_at": datetime.now().isoformat(),
    }
    for field in (
        "social_media_url",
        "social_media_type",
        "facebook_username",
        "instagram_username",
    ):
        valor = flujo.get(field)
        if valor is not None:
            payload[field] = valor
    return payload


async def asegurar_proveedor_persistido_tras_consentimiento_onboarding(
    *,
    telefono: str,
    flujo: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any = None,
    subir_medios_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Asegura que el proveedor exista en Supabase tras consentir."""
    if supabase is None:
        from principal import supabase as supabase_local

        supabase = supabase_local

    proveedor_id = (perfil_proveedor or {}).get("id")
    if proveedor_id:
        if supabase:
            try:
                payload = _construir_payload_metadata_whatsapp(flujo)
                payload["has_consent"] = bool(
                    perfil_proveedor.get("has_consent") or flujo.get("has_consent")
                )
                real_phone = _extraer_real_phone_desde_telefono(
                    flujo.get("phone") or telefono
                )
                if real_phone:
                    payload["real_phone"] = real_phone
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(payload)
                    .eq("id", proveedor_id)
                    .execute(),
                    label="providers.update_whatsapp_identity_on_consent_existing",
                )
            except Exception as exc:
                logger.warning(
                    "No se pudo persistir metadata WhatsApp tras consentimiento para %s: %s",
                    telefono,
                    exc,
                )
            try:
                await persistir_identities_whatsapp(
                    supabase,
                    str(proveedor_id),
                    phone=flujo.get("phone"),
                    from_number=flujo.get("from_number"),
                    user_id=flujo.get("user_id"),
                    account_id=flujo.get("account_id"),
                )
            except Exception as exc:
                logger.warning(
                    "No se pudieron persistir identidades WhatsApp tras consentimiento para %s: %s",
                    telefono,
                    exc,
                )
        if subir_medios_fn is not None:
            try:
                await subir_medios_fn(str(proveedor_id), flujo)
            except Exception as exc:
                logger.warning(
                    "No se pudieron persistir los medios de identidad para "
                    "proveedor existente tras consentimiento para %s: %s",
                    telefono,
                    exc,
                )
        return perfil_proveedor, str(proveedor_id)

    if not supabase:
        return perfil_proveedor, None

    try:
        proveedor_registrado = await asegurar_proveedor_borrador(
            supabase,
            telefono,
        )
        if not proveedor_registrado or not proveedor_registrado.get("id"):
            logger.warning(
                "No se pudo asegurar el borrador del proveedor tras "
                "consentimiento para %s",
                telefono,
            )
            return perfil_proveedor, None

        provider_id = str(proveedor_registrado.get("id") or "").strip()
        flujo["provider_id"] = provider_id
        perfil_proveedor = proveedor_registrado

        try:
            payload = _construir_payload_metadata_whatsapp(flujo)
            payload["has_consent"] = True
            real_phone = _extraer_real_phone_desde_telefono(
                flujo.get("phone") or telefono
            )
            if real_phone:
                payload["real_phone"] = real_phone
            await run_supabase(
                lambda: supabase.table("providers")
                .update(payload)
                .eq("id", provider_id)
                .execute(),
                label="providers.update_whatsapp_identity_on_consent_new",
            )
        except Exception as exc:
            logger.warning(
                "No se pudo persistir metadata WhatsApp tras crear borrador para %s: %s",
                telefono,
                exc,
            )
        try:
            await persistir_identities_whatsapp(
                supabase,
                provider_id,
                phone=flujo.get("phone") or telefono,
                from_number=flujo.get("from_number"),
                user_id=flujo.get("user_id"),
                account_id=flujo.get("account_id"),
            )
        except Exception as exc:
            logger.warning(
                "No se pudieron persistir identidades WhatsApp tras crear borrador para %s: %s",
                telefono,
                exc,
            )

        if provider_id and subir_medios_fn is not None:
            try:
                await subir_medios_fn(provider_id, flujo)
            except Exception as exc:
                logger.warning(
                    "No se pudieron persistir los medios de identidad tras "
                    "consentimiento para %s: %s",
                    telefono,
                    exc,
                )

        return perfil_proveedor, provider_id
    except Exception as exc:
        logger.warning(
            "Error completando el alta del proveedor tras consentimiento "
            "para %s: %s",
            telefono,
            exc,
        )
        return perfil_proveedor, None


def _resolver_opcion_consentimiento(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea la respuesta interactiva a aceptación explícita."""
    seleccionado = str(carga.get("selected_option") or "").strip().lower()

    if seleccionado in SELECCION_CONSENTIMIENTO_AFIRMATIVA:
        return VALOR_OPCION_AFIRMATIVA
    return None


async def manejar_estado_consentimiento_onboarding(
    *,
    flujo: Dict[str, Any],
    tiene_consentimiento: bool,
    esta_registrado: bool,
    telefono: str,
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any = None,
    subir_medios_identidad: Any = None,
) -> Dict[str, Any]:
    """Compatibilidad con el handler histórico de consentimiento."""
    from flows.onboarding.handlers.consentimiento import (
        manejar_estado_consentimiento_onboarding as _impl,
    )

    return await _impl(
        flujo=flujo,
        tiene_consentimiento=tiene_consentimiento,
        esta_registrado=esta_registrado,
        telefono=telefono,
        carga=carga,
        perfil_proveedor=perfil_proveedor,
        supabase=supabase,
        subir_medios_identidad=subir_medios_identidad,
    )


async def procesar_respuesta_consentimiento_onboarding(
    *,
    telefono: str,
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    perfil_proveedor: Optional[Dict[str, Any]],
    supabase: Any = None,
    subir_medios_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """Procesa la respuesta de consentimiento del onboarding."""

    if supabase is None:
        from principal import supabase as supabase_local

        supabase = supabase_local

    texto_mensaje = (carga.get("message") or carga.get("content") or "").strip()
    opcion = _resolver_opcion_consentimiento(carga)

    logger.info(
        (
            "📝 Procesando respuesta consentimiento onboarding. Texto: '%s', "
            "selected_option='%s', Carga keys: %s"
        ),
        texto_mensaje,
        carga.get("selected_option"),
        list(carga.keys()),
    )

    if opcion != VALOR_OPCION_AFIRMATIVA:
        logger.info(
            "Consentimiento no confirmado por %s. selected_option='%s', texto='%s'",
            telefono,
            carga.get("selected_option"),
            texto_mensaje,
        )
        return construir_respuesta_solicitud_consentimiento()

    proveedor_id = perfil_proveedor.get("id") if perfil_proveedor else None

    flujo["has_consent"] = True

    perfil_proveedor, proveedor_id = (
        await asegurar_proveedor_persistido_tras_consentimiento_onboarding(
            telefono=telefono,
            flujo=flujo,
            perfil_proveedor=perfil_proveedor,
            supabase=supabase,
            subir_medios_fn=subir_medios_fn,
        )
    )

    if not proveedor_id:
        logger.warning(
            "No se pudo resolver provider_id para consentimiento aceptado de %s",
            telefono,
        )
        flujo["state"] = "onboarding_city"
        await onboarding_session.establecer_flujo(telefono, flujo)
        return {
            "success": True,
            "messages": [solicitar_ciudad_registro()],
        }

    real_phone = _extraer_real_phone_desde_telefono(flujo.get("phone") or telefono)
    if real_phone:
        flujo["real_phone"] = real_phone
        flujo["requires_real_phone"] = False
        nuevo_estado = "onboarding_city"
        respuesta_siguiente = solicitar_ciudad_registro()
    else:
        flujo["requires_real_phone"] = True
        nuevo_estado = "onboarding_real_phone"
        respuesta_siguiente = preguntar_real_phone()

    flujo.update(
        {
            "state": nuevo_estado,
            "has_consent": True,
        }
    )
    await onboarding_session.establecer_flujo(telefono, flujo)

    await registrar_consentimiento(proveedor_id, telefono, carga, "accepted")
    logger.info("Consentimiento aceptado por proveedor %s", telefono)
    return {
        "success": True,
        "messages": [respuesta_siguiente],
    }
