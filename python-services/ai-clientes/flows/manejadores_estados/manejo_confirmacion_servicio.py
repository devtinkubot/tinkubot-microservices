"""Manejador del estado de confirmación de servicio detectado."""

from typing import Any, Awaitable, Callable, Dict, Optional


async def procesar_estado_confirmar_servicio(
    flujo: Dict[str, Any],
    texto: Optional[str],
    seleccionado: Optional[str],
    telefono: str,
    guardar_flujo_fn: Callable[[Dict[str, Any]], Awaitable[None]],
    iniciar_busqueda_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    interpretar_si_no_fn: Callable[[Optional[str]], Optional[bool]],
    mensaje_inicial_solicitud: str,
) -> Dict[str, Any]:
    """Confirma el servicio detectado antes de iniciar búsqueda."""
    from templates.mensajes.validacion import ui_confirmar_servicio

    eleccion = (seleccionado or texto or "").strip()
    eleccion_norm = eleccion.lower().strip().strip("*").rstrip(".)")
    service_candidate = (flujo.get("service_candidate") or "").strip()

    if (
        eleccion_norm in {"1", "si", "sí", "s", "problem_confirm_yes"}
        or interpretar_si_no_fn(eleccion) is True
    ):
        if not service_candidate:
            for key in ["service", "service_full", "service_candidate"]:
                flujo.pop(key, None)
            flujo["state"] = "awaiting_service"
            await guardar_flujo_fn(flujo)
            return {
                "response": (
                    "No pude confirmar el servicio detectado. "
                    "Por favor descríbelo nuevamente de forma concreta."
                )
            }
        flujo["service"] = service_candidate
        flujo["service_captured_after_consent"] = True
        flujo.pop("service_candidate", None)
        await guardar_flujo_fn(flujo)
        return await iniciar_busqueda_fn(flujo)

    if (
        eleccion_norm in {"2", "no", "problem_confirm_no"}
        or interpretar_si_no_fn(eleccion) is False
    ):
        for key in ["service", "service_full", "service_candidate"]:
            flujo.pop(key, None)
        flujo["state"] = "awaiting_service"
        await guardar_flujo_fn(flujo)
        return {"response": mensaje_inicial_solicitud}

    return {
        "response": "Por favor confirma con un botón: Sí o No.",
        "ui": ui_confirmar_servicio(),
    }
