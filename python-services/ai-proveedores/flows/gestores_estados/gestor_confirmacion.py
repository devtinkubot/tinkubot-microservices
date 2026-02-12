"""Manejador del estado de confirmación (async)."""

from typing import Any, Awaitable, Callable, Dict, Optional

from models.proveedores import SolicitudCreacionProveedor
from templates import mensaje_proveedor_en_revision
from services.servicios_proveedor.utilidades import limpiar_espacios
from flows.validadores.validador_entrada import parsear_cadena_servicios
from services.registro import validar_y_construir_proveedor


async def manejar_confirmacion(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
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
        texto_mensaje: Mensaje del usuario con confirmación o edición.
        telefono: Número de teléfono del proveedor.
        registrar_proveedor_fn: Función asíncrona para registrar el proveedor.
        subir_medios_fn: Función asíncrona para subir medios.
        reiniciar_flujo_fn: Función asíncrona para resetear el flujo.
        logger: Logger para registro de eventos.

    Returns:
        Respuesta con éxito y nuevo estado del flujo, o error de validación.
    """
    texto_crudo = limpiar_espacios(texto_mensaje)
    texto = texto_crudo.lower()

    if texto.startswith("2") or "editar" in texto:
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

    if (
        texto.startswith("1")
        or texto.startswith("confirm")
        or texto in {"si", "ok", "listo", "confirmar"}
    ):
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
                            "Revisa que nombre, ciudad y servicios cumplan con el formato."
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

    return {
        "success": True,
        "messages": [
            {
                "response": (
                    "*Por favor responde 1 para aceptar o 2 para no aceptar.*"
                )
            }
        ],
    }
