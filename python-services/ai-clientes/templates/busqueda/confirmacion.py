"""Mensajes de confirmación y estados de disponibilidad."""

# ==================== MENSAJES ====================


def mensaje_confirmando_disponibilidad(
    cantidad_expertos: int | None = None,
    cupo_distribucion: int = 10,
) -> str:
    """Mensaje de confirmación de disponibilidad con copy dinámico.

    Cuando hay 10 o menos expertos, mantiene un copy simple.
    Si hay más de 10, comunica que la oportunidad se está distribuyendo
    sobre el cupo aplicado de expertos.
    """
    if isinstance(cantidad_expertos, int) and cantidad_expertos > cupo_distribucion:
        expertos_a_notificar = max(1, min(cantidad_expertos, cupo_distribucion))
        return (
            f"⏳ *Distribuyendo oportunidad en {expertos_a_notificar} expertos.* "
            "Te aviso en 3 min como máximo."
        )

    return "⏳ *Confirmo disponibilidad.* Te aviso en 3 min como máximo."


mensaje_buscando_expertos = "⏳ *Busco expertos.* Te aviso en breve."

texto_opcion_nueva_solicitud = "Nueva solicitud"
texto_opcion_cambiar_ciudad = "Cambiar ciudad"

opciones_confirmar_nueva_busqueda_textos = [
    texto_opcion_nueva_solicitud,
    "No, por ahora está bien",
]

titulo_confirmacion_repetir_busqueda = "¿Te ayudo con otra solicitud?"

titulo_ayuda_otro_servicio = "¿Te ayudo con otro servicio?"


# ==================== FUNCIONES ====================


def mensaje_sin_proveedores_registrados(servicio: str, ciudad: str) -> str:
    """Mensaje cuando no existen proveedores registrados para el servicio."""
    ciudad_texto = (ciudad or "").strip() or "tu ciudad"
    return (
        f"*No hay expertos registrados* para atender tu solicitud en *{ciudad_texto}*.\n\n"
        "*¿Te ayudo con otra solicitud o buscar expertos en otra ciudad?*"
    )


def mensaje_sin_disponibilidad(servicio: str, ciudad: str) -> str:
    """Mensaje cuando hay expertos registrados, pero ninguno respondió."""
    ciudad_texto = (ciudad or "").strip() or "tu ciudad"
    return (
        f"*No hay expertos disponibles* para atender tu solicitud en *{ciudad_texto}*.\n\n"
        "*¿Te ayudo con otra solicitud o buscar expertos en otra ciudad?*"
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
        return f"✅ Encontre *1* experto en *{ciudad}*."
    return f"✅ Encontre *{cantidad}* expertos en *{ciudad}*."


def menu_opciones_confirmacion(incluir_opcion_ciudad: bool = False) -> str:
    """Menú de confirmación de búsqueda (solo opciones 1/2/3)."""
    from templates.comunes import pie_instrucciones_respuesta_numerica

    lineas: list[str] = []
    if incluir_opcion_ciudad:
        lineas.extend(
            [
                f"{pie_instrucciones_respuesta_numerica}",
                "",
                f"*1.* {texto_opcion_cambiar_ciudad}",
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
    titulo_negrita = titulo if ("*" in titulo or "\n" in titulo) else f"*{titulo}*"
    if incluir_opcion_ciudad:
        return [
            {
                "response": titulo_negrita,
                "ui": {
                    "type": "buttons",
                    "options": [
                        {
                            "id": "confirm_new_search_city",
                            "title": texto_opcion_cambiar_ciudad,
                        },
                        {
                            "id": "confirm_new_search_service",
                            "title": texto_opcion_nueva_solicitud,
                        },
                    ],
                },
            },
        ]

    return [
        {
            "response": titulo_negrita,
            "ui": {
                "type": "buttons",
                "options": [
                    {
                        "id": "confirm_new_search_service",
                        "title": texto_opcion_nueva_solicitud,
                    },
                ],
            },
        },
    ]
