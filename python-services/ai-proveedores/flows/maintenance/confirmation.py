"""Manejador del estado de confirmación (async)."""

from typing import Any, Awaitable, Callable, Dict, Optional

from flows.constructors import construir_respuesta_solicitud_consentimiento
from flows.validators.input import parsear_cadena_servicios
from models.proveedores import SolicitudCreacionProveedor
from services.maintenance.registration import validar_y_construir_proveedor
from services.shared import (
    RESPUESTAS_CONFIRMACION_REGISTRO_AFIRMATIVAS,
    RESPUESTAS_CONFIRMACION_REGISTRO_NEGATIVAS,
    SELECCION_CONFIRMACION_REGISTRO_AFIRMATIVA,
    SELECCION_CONFIRMACION_REGISTRO_NEGATIVA,
    normalizar_respuesta_binaria,
    normalizar_texto_interaccion,
)
from services.shared.identidad_proveedor import (
    resolver_nombre_visible_proveedor,
)
from templates.maintenance import CONFIRM_ACCEPT_ID, CONFIRM_REJECT_ID
from templates.maintenance.revision import mensaje_proveedor_en_revision
from templates.shared import (
    mensaje_no_pude_guardar_informacion_registro,
    mensaje_no_pude_validar_datos_registro,
    mensaje_reiniciar_ciudad_principal,
)


def _resolver_opcion_confirmacion(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea respuesta interactiva o textual a 'accept'/'reject' para confirmación.

    Args:
        carga: Diccionario con selected_option y/o message/content.

    Returns:
        'accept' si acepta, 'reject' si rechaza, None si no se puede determinar.
    """
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_min = normalizar_texto_interaccion(texto_mensaje)

    # Botones interactivos
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

    # Fallback a texto
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


async def manejar_confirmacion(
    flujo: Dict[str, Any],
    carga: Dict[str, Any],
    telefono: str,
    registrar_proveedor_fn: Callable[
        [SolicitudCreacionProveedor], Awaitable[Optional[Dict[str, Any]]]
    ],
    subir_medios_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
    reiniciar_flujo_fn: Callable[[], Awaitable[None]],
    logger: Any,
) -> Dict[str, Any]:
    """Procesa la confirmación del registro y crea el proveedor.

    Args:
        flujo: Diccionario del flujo conversacional.
        carga: Diccionario con selected_option y/o message/content del usuario.
        telefono: Número de teléfono del proveedor.
        registrar_proveedor_fn: Función asíncrona para registrar el proveedor.
        subir_medios_fn: Función asíncrona para subir medios.
        reiniciar_flujo_fn: Función asíncrona para resetear el flujo.
        logger: Logger para registro de eventos.

    Returns:
        Respuesta con éxito y nuevo estado del flujo, o error de validación.
    """
    opcion = _resolver_opcion_confirmacion(carga)

    logger.info(
        "📝 Procesando confirmación registro. selected_option='%s', opcion='%s'",
        carga.get("selected_option"),
        opcion,
    )

    if opcion == "reject":
        tiene_consentimiento = flujo.get("has_consent", False)
        real_phone = flujo.get("real_phone")
        requiere_real_phone = flujo.get("requires_real_phone", False)
        flujo.clear()
        flujo["state"] = "awaiting_city"
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
        # Validar y construir proveedor usando el servicio de negocio
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
            await reiniciar_flujo_fn()
            return {
                "success": True,
                "messages": [
                    {
                        "response": mensaje_proveedor_en_revision(
                            resolver_nombre_visible_proveedor(
                                proveedor=datos_proveedor,
                            )
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

    # Opción no reconocida - reenviar solicitud con botones
    return {
        "success": True,
        "messages": construir_respuesta_solicitud_consentimiento()["messages"],
    }
