"""Manejador de confirmación del onboarding de proveedores."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from flows.validators.input import parsear_cadena_servicios
from models.proveedores import SolicitudCreacionProveedor
from services.onboarding.messages import construir_respuesta_solicitud_consentimiento
from services.onboarding.registration import validar_y_construir_proveedor
from services.onboarding.session import reiniciar_flujo
from services.shared import (
    RESPUESTAS_CONFIRMACION_REGISTRO_AFIRMATIVAS,
    RESPUESTAS_CONFIRMACION_REGISTRO_NEGATIVAS,
    SELECCION_CONFIRMACION_REGISTRO_AFIRMATIVA,
    SELECCION_CONFIRMACION_REGISTRO_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from templates.onboarding.registration import (
    CONFIRM_ACCEPT_ID,
    CONFIRM_REJECT_ID,
)
from templates.review.estados import mensaje_proveedor_en_revision
from templates.shared import (
    mensaje_no_pude_guardar_informacion_registro,
    mensaje_no_pude_validar_datos_registro,
    mensaje_reiniciar_ciudad_principal,
)


def _resolver_opcion_confirmacion(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea respuesta interactiva o textual a 'accept'/'reject'."""
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_min = normalizar_texto_interaccion(texto_mensaje)

    if seleccionado in {
        *SELECCION_CONFIRMACION_REGISTRO_AFIRMATIVA,
        CONFIRM_ACCEPT_ID,
    }:
        return "accept"
    if seleccionado in {
        *SELECCION_CONFIRMACION_REGISTRO_NEGATIVA,
        CONFIRM_REJECT_ID,
    }:
        return "reject"

    if texto_min.startswith("1") or texto_min.startswith("confirm"):
        return "accept"
    if texto_min.startswith("2") or "editar" in texto_min or "no acepto" in texto_min:
        return "reject"

    decision = normalizar_respuesta_binaria(
        texto_min,
        RESPUESTAS_CONFIRMACION_REGISTRO_AFIRMATIVAS,
        RESPUESTAS_CONFIRMACION_REGISTRO_NEGATIVAS,
    )
    if decision is True:
        return "accept"
    if decision is False:
        return "reject"

    return None


async def manejar_confirmacion_onboarding(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    telefono: str,
    registrar_proveedor_fn: Callable[
        [SolicitudCreacionProveedor], Awaitable[Optional[Dict[str, Any]]]
    ],
    subir_medios_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
    logger: Any,
) -> Dict[str, Any]:
    """Procesa la confirmación del registro dentro del contexto onboarding."""
    opcion = _resolver_opcion_confirmacion(carga)

    logger.info(
        "📝 Procesando confirmación onboarding. selected_option='%s', opcion='%s'",
        carga.get("selected_option"),
        opcion,
    )

    if opcion == "reject":
        tiene_consentimiento = flujo.get("has_consent", False)
        real_phone = flujo.get("real_phone")
        requiere_real_phone = flujo.get("requires_real_phone", False)
        flujo.clear()
        flujo["state"] = "onboarding_city"
        if tiene_consentimiento:
            flujo["has_consent"] = True
        if real_phone:
            flujo["real_phone"] = real_phone
        if requiere_real_phone:
            flujo["requires_real_phone"] = True
        return {
            "success": True,
            "messages": [{"response": mensaje_reiniciar_ciudad_principal()}],
        }

    if opcion == "accept":
        flujo["has_consent"] = True
        es_valido, mensaje_error, datos_proveedor = validar_y_construir_proveedor(
            flujo, telefono
        )

        if not es_valido or datos_proveedor is None:
            return {
                "success": True,
                "messages": [
                    {"response": mensaje_no_pude_validar_datos_registro(mensaje_error)}
                ],
            }

        proveedor_registrado = await registrar_proveedor_fn(datos_proveedor)
        if proveedor_registrado:
            logger.info(
                "Proveedor registrado exitosamente: %s",
                proveedor_registrado.get("id"),
            )
            proveedor_id = proveedor_registrado.get("id")
            servicios_registrados = []
            if isinstance(proveedor_registrado.get("services_normalized"), list):
                servicios_registrados = [
                    str(servicio).strip()
                    for servicio in proveedor_registrado.get("services_normalized", [])
                    if str(servicio).strip()
                ]
            if not servicios_registrados:
                servicios_registrados = parsear_cadena_servicios(
                    proveedor_registrado.get("services")
                )
            flujo["services"] = servicios_registrados
            if proveedor_id:
                await subir_medios_fn(proveedor_id, flujo)
            await reiniciar_flujo(telefono)
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_proveedor_en_revision(
                            datos_proveedor.full_name
                        )
                    }
                ],
                "reset_flow": True,
                "new_flow": {
                    "state": "pending_verification",
                    "has_consent": True,
                    "registration_allowed": False,
                    "provider_id": proveedor_id,
                    "services": servicios_registrados,
                    "awaiting_verification": True,
                },
            }

        logger.error("No se pudo registrar el proveedor")
        return {
            "success": True,
            "messages": [{"response": mensaje_no_pude_guardar_informacion_registro()}],
        }

    return {
        "success": True,
        "messages": construir_respuesta_solicitud_consentimiento()["messages"],
    }
