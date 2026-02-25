"""Mensajes de validación y error para entrada de usuario."""

# ==================== MENSAJES ====================

mensaje_inicial_solicitud_servicio = (
    '*¿Qué necesitas resolver?*\nDescribe qué pasó o qué necesitas (ej: "mi lavadora no enciende").'
)

mensaje_error_input_invalido = mensaje_inicial_solicitud_servicio

mensaje_advertencia_contenido_ilegal = """⚠️ *ADVERTENCIA*

TinkuBot NO conecta servicios de contenido ilegal o inapropiado.

Si vuelves a insistir con este tipo de contenido, tu cuenta será suspendida temporalmente.

Por favor, describe un servicio legítimo que necesites."""

mensaje_ban_usuario = """🚫 *CUENTA SUSPENDIDA TEMPORALMENTE*

Has sido suspendido por 15 minutos por infringir nuestras políticas de contenido.

Podrás reanudar el servicio después de las {hora_reinicio}."""

mensaje_error_input_sin_sentido = mensaje_inicial_solicitud_servicio


def solicitar_reformulacion() -> str:
    """Solicita al usuario reformular su mensaje."""
    return "¿Podrías reformular tu mensaje?"

def mensaje_confirmar_servicio(servicio: str) -> str:
    """Confirma el servicio detectado antes de continuar la búsqueda."""
    from templates.comunes import pie_instrucciones_respuesta_numerica

    servicio_texto = (servicio or "").strip() or "tu solicitud"
    return (
        f"Entendí que necesitas: *{servicio_texto}*\n\n"
        f"{pie_instrucciones_respuesta_numerica}\n\n"
        "*1.* Sí\n"
        "*2.* No"
    )
