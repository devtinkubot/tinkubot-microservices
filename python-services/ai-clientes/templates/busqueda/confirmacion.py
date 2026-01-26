"""Mensajes de confirmación y estados de disponibilidad."""

# ==================== MENSAJES ====================

mensaje_confirmando_disponibilidad = (
    "⏳ *Estoy confirmando disponibilidad, te aviso en breve.*"
)

mensaje_buscando_expertos = (
    "⏳ *Estoy buscando expertos, te aviso en breve.*"
)

texto_opcion_buscar_otro_servicio = "Buscar otro servicio"

opciones_confirmar_nueva_busqueda_textos = [
    f"{texto_opcion_buscar_otro_servicio}",
    "No, por ahora está bien",
]

titulo_confirmacion_repetir_busqueda = "¿Te ayudo con otra solicitud?"


# ==================== FUNCIONES ====================

def mensaje_sin_disponibilidad(service: str, city: str) -> str:
    """Mensaje cuando no hay disponibilidad inmediata en proveedores aceptados."""
    svc_txt = (service or "").strip() or "tu solicitud"
    city_txt = (city or "").strip()
    destino = f"**{svc_txt}**" if svc_txt else "este servicio"
    ciudad = f" en **{city_txt}**" if city_txt else ""
    return (
        f"No hay proveedores disponibles ahora mismo para {destino}{ciudad}. "
        "¿Quieres buscar en otra ciudad o intentarlo más tarde?"
    )


def mensaje_expertos_encontrados(cantidad: int, city: str) -> str:
    """Mensaje cuando se encuentran expertos en la búsqueda.

    Args:
        cantidad: Número de expertos encontrados.
        city: Ciudad donde se encontraron.

    Returns:
        Mensaje con singular/plural correcto.
    """
    if cantidad == 1:
        return f"✅ *He encontrado 1 experto en {city}.*"
    else:
        return f"✅ *He encontrado {cantidad} expertos en {city}.*"


def menu_opciones_confirmacion(include_city_option: bool = False) -> str:
    """Menú de confirmación de búsqueda (solo opciones 1/2/3)."""
    from templates.comunes import pie_instrucciones_respuesta_numerica

    lines: list[str] = []
    if include_city_option:
        lines.extend(
            [
                f"{pie_instrucciones_respuesta_numerica}",
                "",
                "1) Buscar en otra ciudad",
                f"2) {opciones_confirmar_nueva_busqueda_textos[0]}",
                "3) Salir",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"{pie_instrucciones_respuesta_numerica}",
                "",
                f"1) {opciones_confirmar_nueva_busqueda_textos[0]}",
                "2) Salir",
                "",
            ]
        )
    return "\n".join(lines)


def mensajes_confirmacion_busqueda(title: str, include_city_option: bool = False):
    """Genera mensajes de confirmación de búsqueda con botones.

    Args:
        title: Título del menú de confirmación.
        include_city_option: Si incluir opción de cambiar ciudad.

    Returns:
        Lista de diccionarios con 'response' y opcionalmente 'ui'.
    """
    from templates.comunes.elementos_ui import pie_instrucciones_respuesta_numerica

    title_bold = f"*{title}*"
    return [
        {
            "response": f"{title_bold}\n\n{menu_opciones_confirmacion(include_city_option)}"
        },
    ]
