"""Lógica de negocio del consentimiento de onboarding."""

import logging
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, Optional

from flows.constructores import (
    construir_respuesta_consentimiento_rechazado,
    construir_respuesta_revision,
    construir_respuesta_solicitud_consentimiento,
)
from flows.sesion import establecer_flujo, reiniciar_flujo
from infrastructure.database import run_supabase
from services.registro import (
    registrar_proveedor_en_base_datos,
    validar_y_construir_proveedor,
)
from services.onboarding.registrador import registrar_consentimiento
logger = logging.getLogger(__name__)


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
                    "No se pudieron persistir los medios de identidad para proveedor existente tras consentimiento para %s: %s",
                    telefono,
                    exc,
                )
        return perfil_proveedor, str(proveedor_id)

    if not supabase:
        return perfil_proveedor, None

    try:
        es_valido, mensaje_error, datos_proveedor = validar_y_construir_proveedor(
            flujo,
            telefono,
        )
        if not es_valido or datos_proveedor is None:
            logger.warning(
                "No se pudo reconstruir el proveedor desde el flujo tras consentimiento para %s: %s",
                telefono,
                mensaje_error,
            )
            return perfil_proveedor, None

        proveedor_registrado = await registrar_proveedor_en_base_datos(
            supabase,
            datos_proveedor,
        )
        if not proveedor_registrado or not proveedor_registrado.get("id"):
            logger.warning(
                "No se pudo completar el alta de proveedor tras consentimiento para %s",
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
                    "No se pudieron persistir los medios de identidad tras consentimiento para %s: %s",
                    telefono,
                    exc,
                )

        return perfil_proveedor, provider_id
    except Exception as exc:
        logger.warning(
            "Error completando el alta del proveedor tras consentimiento para %s: %s",
            telefono,
            exc,
        )
        return perfil_proveedor, None


def _resolver_opcion_consentimiento(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea respuesta interactiva o textual a 1/2 para consentimiento."""
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_min = texto_mensaje.lower()
    texto_normalizado = re.sub(r"[\s\.,;:!¡¿\?]+", " ", texto_min).strip()

    if seleccionado in {
        "continue_provider_onboarding",
        "continuar",
        "continue",
        "1",
    }:
        return "1"
    if seleccionado in {"2", "rechazar", "decline", "cancelar"}:
        return "2"

    if texto_normalizado in {"1", "si", "sí", "aceptar", "acepto", "ok", "continuar"}:
        return "1"
    if texto_normalizado in {"2", "no", "rechazar", "declinar", "declino", "cancelar"}:
        return "2"
    return None


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
        "📝 Procesando respuesta consentimiento onboarding. Texto: '%s', selected_option='%s', Carga keys: %s",
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
            return {
                "success": True,
                "messages": [
                    {
                        "response": (
                            "✅ Gracias. Estamos revisando tu información y te avisaremos cuando quede listo."
                        )
                    }
                ],
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
                "state": "pending_verification",
                "has_consent": True,
                "menu_limitado": False,
                "approved_basic": False,
                "profile_pending_review": False,
                "registration_allowed": False,
                "awaiting_verification": True,
            }
        )
        await establecer_flujo(telefono, flujo)

        await registrar_consentimiento(proveedor_id, telefono, carga, "accepted")
        logger.info("Consentimiento aceptado por proveedor %s", telefono)

        nombre_proveedor = (
            (perfil_proveedor or {}).get("full_name")
            or flujo.get("full_name")
            or "Proveedor"
        )
        return construir_respuesta_revision(nombre_proveedor)

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
    await reiniciar_flujo(telefono)
    logger.info("Consentimiento rechazado por proveedor %s", telefono)

    return construir_respuesta_consentimiento_rechazado()
