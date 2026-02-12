"""Mensajes de confirmación y estados de disponibilidad."""

# ==================== MENSAJES ====================

mensaje_confirmando_disponibilidad = (
    "⏳ Estoy confirmando disponibilidad. Te aviso en breve."
)

mensaje_buscando_expertos = (
    "⏳ Estoy buscando expertos. Te aviso en breve."
)

texto_opcion_buscar_otro_servicio = "Buscar otro servicio"

opciones_confirmar_nueva_busqueda_textos = [
    f"{texto_opcion_buscar_otro_servicio}",
    "No, por ahora está bien",
]

titulo_confirmacion_repetir_busqueda = "¿Te ayudo con otra solicitud?"


# ==================== FUNCIONES ====================

def mensaje_sin_disponibilidad(servicio: str, ciudad: str) -> str:
    """Mensaje cuando no hay disponibilidad inmediata en proveedores aceptados."""
    servicio_texto = (servicio or "").strip() or "tu solicitud"
    ciudad_texto = (ciudad or "").strip()
    destino = f"*{servicio_texto}*" if servicio_texto else "este servicio"
    ciudad_mensaje = f" en *{ciudad_texto}*" if ciudad_texto else ""
    return (
        f"No hay proveedores disponibles ahora mismo para {destino}{ciudad_mensaje}. "
        "¿Quieres buscar en otra ciudad o intentarlo más tarde?"
    )


def mensaje_expertos_encontrados(cantidad: int, ciudad: str) -> str:
    """Mensaje cuando se encuentran expertos en la búsqueda.

    Args:
        cantidad: Número de expertos encontrados.
        ciudad: Ciudad donde se encontraron.

    Returns:
        Mensaje con singular/plural correcto.
    """
    if cantidad == 1:
        return f"✅ He encontrado 1 experto en {ciudad}."
    return f"✅ He encontrado {cantidad} expertos en {ciudad}."


def menu_opciones_confirmacion(incluir_opcion_ciudad: bool = False) -> str:
    """Menú de confirmación de búsqueda (solo opciones 1/2/3)."""
    from templates.comunes import pie_instrucciones_respuesta_numerica

    lineas: list[str] = []
    if incluir_opcion_ciudad:
        lineas.extend(
            [
                f"{pie_instrucciones_respuesta_numerica}",
                "",
                "*1.* Buscar en otra ciudad",
                f"*2.* {opciones_confirmar_nueva_busqueda_textos[0]}",
                "*3.* Salir",
                "",
            ]
        )
    else:
        lineas.extend(
            [
                f"{pie_instrucciones_respuesta_numerica}",
                "",
                f"*1.* {opciones_confirmar_nueva_busqueda_textos[0]}",
                "*2.* Salir",
                "",
            ]
        )
    return "\n".join(lineas)


def mensajes_confirmacion_busqueda(titulo: str, incluir_opcion_ciudad: bool = False):
    """Genera mensajes de confirmación de búsqueda con botones.

    Args:
        titulo: Título del menú de confirmación.
        incluir_opcion_ciudad: Si incluir opción de cambiar ciudad.

    Returns:
        Lista de diccionarios con 'response' y opcionalmente 'ui'.
    """
    from templates.comunes.elementos_ui import pie_instrucciones_respuesta_numerica

    titulo_negrita = f"*{titulo}*"
    return [
        {
            "response": f"{titulo_negrita}\n\n{menu_opciones_confirmacion(incluir_opcion_ciudad)}"
        },
    ]
