"""Utilidades y funciones auxiliares para los flujos conversacionales."""

from typing import Any, Dict, Optional


def es_opcion_reinicio(seleccionado: str) -> bool:
    """
    Verifica si la opción seleccionada es de reinicio.

    Args:
        seleccionado: Opción seleccionada por el usuario.

    Returns:
        True si la opción corresponde a reiniciar el flujo, False en caso contrario.
    """
    from templates.busqueda.confirmacion import opciones_confirmar_nueva_busqueda_textos
    return seleccionado in opciones_confirmar_nueva_busqueda_textos


async def verificar_ciudad_y_proceder(
    flujo: Dict[str, Any],
    perfil_cliente: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verifica si el usuario YA tiene ciudad confirmada y procede accordingly.

    Si el usuario YA tiene ciudad confirmada, ir directo a búsqueda.
    Si NO tiene ciudad, pedir ciudad normalmente.

    Args:
        flujo: Diccionario con el estado del flujo conversacional.
        perfil_cliente: Perfil del cliente con datos previos (opcional).

    Returns:
        Dict con "response" (mensaje para el usuario) y opcionalmente "ui".
    """
    if not perfil_cliente:
        return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    ciudad_existente = perfil_cliente.get("city")
    ciudad_confirmada_en = perfil_cliente.get("city_confirmed_at")

    if ciudad_existente and ciudad_confirmada_en:
        # Tiene ciudad confirmada: usarla automáticamente
        flujo["city"] = ciudad_existente
        flujo["city_confirmed"] = True
        flujo["state"] = "searching"
        flujo["searching_dispatched"] = True

        return {
            "response": f"Perfecto, buscaré {flujo.get('service')} en {ciudad_existente}.",
            "ui": {"type": "silent"}
        }

    # No tiene ciudad: pedir normalmente
    return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}
