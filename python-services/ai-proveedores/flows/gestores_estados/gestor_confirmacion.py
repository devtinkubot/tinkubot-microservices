"""Manejador del estado de confirmación (async)."""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from models.proveedores import SolicitudCreacionProveedor
from templates import provider_under_review_message
from services.servicios_proveedor.utilidades import limpiar_espacios
from flows.validadores.validador_entrada import parsear_cadena_servicios
from services.registro import validar_y_construir_proveedor


async def manejar_confirmacion(
    flow: Dict[str, Any],
    message_text: Optional[str],
    phone: str,
    register_provider_fn: Callable[
        [SolicitudCreacionProveedor], Awaitable[Optional[Dict[str, Any]]]
    ],
    upload_media_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
    reset_flow_fn: Callable[[], Awaitable[None]],
    logger: Any,
) -> Dict[str, Any]:
    """Procesa la confirmación del registro y crea el proveedor.

    Args:
        flow: Diccionario del flujo conversacional.
        message_text: Mensaje del usuario con confirmación o edición.
        phone: Número de teléfono del proveedor.
        register_provider_fn: Función asíncrona para registrar el proveedor.
        upload_media_fn: Función asíncrona para subir medios.
        reset_flow_fn: Función asíncrona para resetear el flujo.
        logger: Logger para registro de eventos.

    Returns:
        Respuesta con éxito y nuevo estado del flujo, o error de validación.
    """
    raw_text = limpiar_espacios(message_text)
    text = raw_text.lower()

    if text.startswith("2") or "editar" in text:
        has_consent = flow.get("has_consent", False)
        flow.clear()
        flow["state"] = "awaiting_city"
        if has_consent:
            flow["has_consent"] = True
        return {
            "success": True,
            "response": ("Reiniciemos. *En que ciudad trabajas principalmente?*"),
        }

    if (
        text.startswith("1")
        or text.startswith("confirm")
        or text in {"si", "ok", "listo", "confirmar"}
    ):
        # Validar y construir proveedor usando el servicio de negocio
        es_valido, mensaje_error, provider_payload = validar_y_construir_proveedor(
            flow, phone
        )

        if not es_valido or provider_payload is None:
            return {
                "success": False,
                "response": (
                    f"*No pude validar tus datos:* {mensaje_error}. "
                    "Revisa que nombre, ciudad y profesión cumplan con el formato y longitud."
                ),
            }

        registered_provider = await register_provider_fn(provider_payload)
        if registered_provider:
            logger.info(
                "Proveedor registrado exitosamente: %s",
                registered_provider.get("id"),
            )
            provider_id = registered_provider.get("id")
            servicios_registrados = parsear_cadena_servicios(
                registered_provider.get("services")
            )
            flow["services"] = servicios_registrados
            if provider_id:
                await upload_media_fn(provider_id, flow)
            await reset_flow_fn()
            return {
                "success": True,
                "messages": [{"response": provider_under_review_message()}],
                "reset_flow": True,
                "new_flow": {
                    "state": "pending_verification",
                    "has_consent": True,
                    "registration_allowed": False,
                    "provider_id": provider_id,
                    "services": servicios_registrados,
                    "awaiting_verification": True,
                },
            }

        logger.error("No se pudo registrar el proveedor")
        return {
            "success": False,
            "response": (
                "*Hubo un error al guardar tu informacion. Por favor intenta de nuevo.*"
            ),
        }

    return {
        "success": True,
        "response": (
            "*Por favor selecciona 1 para confirmar o 2 para editar tu informacion.*"
        ),
    }
