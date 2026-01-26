"""Utilidades y funciones auxiliares para los flujos conversacionales."""

from typing import Any, Dict, Optional


def es_opcion_reinicio(selected: str) -> bool:
    """
    Verifica si la opción seleccionada es de reinicio.

    Args:
        selected: Opción seleccionada por el usuario.

    Returns:
        True si la opción corresponde a reiniciar el flujo, False en caso contrario.
    """
    from templates.busqueda.confirmacion import opciones_confirmar_nueva_busqueda_textos
    return selected in opciones_confirmar_nueva_busqueda_textos


async def verificar_ciudad_y_proceder(
    flow: Dict[str, Any],
    customer_profile: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Verifica si el usuario YA tiene ciudad confirmada y procede accordingly.

    Si el usuario YA tiene ciudad confirmada, ir directo a búsqueda.
    Si NO tiene ciudad, pedir ciudad normalmente.

    Args:
        flow: Diccionario con el estado del flujo conversacional.
        customer_profile: Perfil del cliente con datos previos (opcional).

    Returns:
        Dict con "response" (mensaje para el usuario) y opcionalmente "ui".
    """
    if not customer_profile:
        return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}

    existing_city = customer_profile.get("city")
    city_confirmed_at = customer_profile.get("city_confirmed_at")

    if existing_city and city_confirmed_at:
        # Tiene ciudad confirmada: usarla automáticamente
        flow["city"] = existing_city
        flow["city_confirmed"] = True
        flow["state"] = "searching"
        flow["searching_dispatched"] = True

        return {
            "response": f"Perfecto, buscaré {flow.get('service')} en {existing_city}.",
            "ui": {"type": "silent"}
        }

    # No tiene ciudad: pedir normalmente
    return {"response": "*Perfecto, ¿en qué ciudad lo necesitas?*"}
