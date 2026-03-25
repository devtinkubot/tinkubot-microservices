"""Manejador del estado de confirmación (async)."""

from typing import Any, Awaitable, Callable, Dict, Optional

from models.proveedores import SolicitudCreacionProveedor
from templates.onboarding.registration import (
    CONFIRM_ACCEPT_ID,
    CONFIRM_REJECT_ID,
)
from flows.constructors import construir_respuesta_solicitud_consentimiento
from flows.validators.input import parsear_cadena_servicios
from services.onboarding.registration import validar_y_construir_proveedor
from templates.review.estados import mensaje_proveedor_en_revision


def _resolver_opcion_confirmacion(carga: Dict[str, Any]) -> Optional[str]:
    """Mapea respuesta interactiva o textual a 'accept'/'reject' para confirmación.

    Args:
        carga: Diccionario con selected_option y/o message/content.

    Returns:
        'accept' si acepta, 'reject' si rechaza, None si no se puede determinar.
    """
    seleccionado = str(carga.get("selected_option") or "").strip().lower()
    texto_mensaje = str(carga.get("message") or carga.get("content") or "").strip()
    texto_min = texto_mensaje.lower()

    # Botones interactivos
    if seleccionado in {CONFIRM_ACCEPT_ID, "confirm_accept", "accept", "1"}:
        return "accept"
    if seleccionado in {CONFIRM_REJECT_ID, "confirm_reject", "reject", "2"}:
        return "reject"

    # Fallback a texto
    if texto_min.startswith("1") or texto_min.startswith("confirm"):
        return "accept"
    if texto_min.startswith("2") or "editar" in texto_min or "no acepto" in texto_min:
        return "reject"
    if texto_min in {"si", "ok", "listo", "confirmar", "acepto", "sí"}:
        return "accept"
    if texto_min in {"no", "cancelar", "rechazo"}:
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
            "messages": [
                {"response": "Reiniciemos. *En que ciudad trabajas principalmente?*"}
            ],
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
                    {
                        "response": (
                            f"*No pude validar tus datos:* {mensaje_error}. "
                            "Revisá que nombre y ciudad cumplan con el formato."
                        )
                    }
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
            "messages": [
                {
                    "response": (
                        "*Hubo un error al guardar tu informacion. Por favor intenta de nuevo.*"
                    )
                }
            ],
        }

    # Opción no reconocida - reenviar solicitud con botones
    return {
        "success": True,
        "messages": construir_respuesta_solicitud_consentimiento()["messages"],
    }
