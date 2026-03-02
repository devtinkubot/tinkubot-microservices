"""Mensajes relacionados con la búsqueda de disponibilidad de proveedores."""


def mensaje_buscando_expertos() -> str:
    """Mensaje de búsqueda inicial de expertos."""
    from templates.busqueda.confirmacion import mensaje_buscando_expertos
    return mensaje_buscando_expertos


def mensaje_expertos_encontrados(cantidad: int, ciudad: str) -> str:
    """Mensaje cuando se encuentran expertos en la búsqueda.

    Args:
        cantidad: Número de expertos encontrados.
        ciudad: Ciudad donde se encontraron.

    Returns:
        Mensaje con singular/plural correcto.
    """
    from templates.busqueda.confirmacion import mensaje_expertos_encontrados as fn_expertos
    return fn_expertos(cantidad, ciudad)


def mensajes_consentimiento() -> list[dict]:
    """
    Retorna mensajes del flujo de consentimiento de datos.

    Genera los mensajes necesarios para solicitar el consentimiento del
    cliente para compartir sus datos de contacto con proveedores.

    Returns:
        list[dict]: Lista de diccionarios con la clave 'response'
            conteniendo cada mensaje del flujo de consentimiento.
    """
    from templates.mensajes.consentimiento import payload_consentimiento_resumen

    payload = payload_consentimiento_resumen()
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        return payload["messages"]
    return [payload]
