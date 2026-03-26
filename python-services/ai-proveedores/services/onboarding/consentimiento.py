"""Lógica de negocio del consentimiento de onboarding."""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, Optional

from infrastructure.database import run_supabase
from services.onboarding import session as onboarding_session
from services.onboarding.messages import (
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_solicitud_consentimiento,
)
from services.onboarding.registrador import registrar_consentimiento
from services.onboarding.registration import asegurar_proveedor_borrador
from services.shared import (
    RESPUESTAS_CONSENTIMIENTO_AFIRMATIVAS,
    RESPUESTAS_CONSENTIMIENTO_NEGATIVAS,
    SELECCION_CONSENTIMIENTO_AFIRMATIVA,
    SELECCION_CONSENTIMIENTO_NEGATIVA,
    VALOR_OPCION_AFIRMATIVA,
    VALOR_OPCION_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.onboarding.ciudad import solicitar_ciudad_registro

logger = logging.getLogger(__name__)


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
    """Mapea respuesta interactiva o textual a 1/2 para consentimiento."""
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_normalizado = normalizar_texto_interaccion(texto_mensaje)

    if seleccionado in SELECCION_CONSENTIMIENTO_AFIRMATIVA:
        return VALOR_OPCION_AFIRMATIVA
    if seleccionado in SELECCION_CONSENTIMIENTO_NEGATIVA:
        return VALOR_OPCION_NEGATIVA

    decision = normalizar_respuesta_binaria(
        texto_normalizado,
        RESPUESTAS_CONSENTIMIENTO_AFIRMATIVAS | {"continuar"},
        RESPUESTAS_CONSENTIMIENTO_NEGATIVAS | {"declinar"},
    )
    if decision is True:
        return VALOR_OPCION_AFIRMATIVA
    if decision is False:
        return VALOR_OPCION_NEGATIVA
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

    if opcion not in {"1", "2"}:
        logger.info(
            "Reenviando solicitud de consentimiento a %s. Opción detectada: '%s'",
            telefono,
            opcion,
        )
        return construir_respuesta_solicitud_consentimiento()

    proveedor_id = perfil_proveedor.get("id") if perfil_proveedor else None

    if opcion == "1":
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

        if provider_id := proveedor_id:
            try:
                if supabase:
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
                    telefono,
                    exc,
                )

        flujo.update(
            {
                "state": "onboarding_city",
                "has_consent": True,
            }
        )
        await onboarding_session.establecer_flujo(telefono, flujo)

        await registrar_consentimiento(proveedor_id, telefono, carga, "accepted")
        logger.info("Consentimiento aceptado por proveedor %s", telefono)
        return {
            "success": True,
            "messages": [solicitar_ciudad_registro()],
        }

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
                "No se pudo marcar rechazo de consentimiento para %s: %s",
                telefono,
                exc,
            )

    await registrar_consentimiento(proveedor_id, telefono, carga, "declined")
    await onboarding_session.reiniciar_flujo(telefono)
    logger.info("Consentimiento rechazado por proveedor %s", telefono)

    return construir_respuesta_consentimiento_rechazado()
