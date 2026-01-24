"""Mensajes de confirmación y estados de disponibilidad."""

# ==================== MENSAJES ====================

mensaje_confirmando_disponibilidad = (
    "⏳ *Estoy confirmando disponibilidad con proveedores y te aviso en breve.*"
)

texto_opcion_buscar_otro_servicio = "Buscar otro servicio"

opciones_confirmar_nueva_busqueda_textos = [
    f"{texto_opcion_buscar_otro_servicio}",
    "No, por ahora está bien",
]

titulo_confirmacion_repetir_busqueda = "¿Te ayudo con otro servicio?"


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
