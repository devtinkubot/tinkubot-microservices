"""Mensajes de validación y error para entrada de usuario."""

# ==================== MENSAJES ====================

mensaje_inicial_solicitud_servicio = (
    "*Cuéntame. Describe el problema o la necesidad que quieres resolver.*"
)

mensaje_error_input_invalido = """Para continuar, por favor describe el servicio que buscas, la necesidad o el problema que quieres resolver.

📝 *Ejemplos válidos:*
• "tubería rota" → conectaré con plomeros
• "diseño de marca" → conectaré con diseñadores
• "cuidado de piel" → conectaré con esteticistas
• "computadora no enciende" → conectaré con técnicos

Describe tu situación con tus propias palabras."""

mensaje_advertencia_contenido_ilegal = """⚠️ *ADVERTENCIA*

TinkuBot NO conecta servicios de contenido ilegal o inapropiado.

Si vuelves a insistir con este tipo de contenido, tu cuenta será suspendida temporalmente.

Por favor, describe un servicio legítimo que necesites."""

mensaje_ban_usuario = """🚫 *CUENTA SUSPENDIDA TEMPORALMENTE*

Has sido suspendido por 15 minutos por infringir nuestras políticas de contenido.

Podrás reanudar el servicio después de las {hora_reinicio}."""

mensaje_error_input_sin_sentido = """❌ *NO PUEDO PROCESAR ESE MENSAJE*

No parece una solicitud de servicio real o válida.

📝 *Ejemplos de lo que sí puedo hacer:*
• "tubería rota" → conectaré con plomeros
• "diseño de marca" → conectaré con diseñadores
• "cuidado de piel" → conectaré con esteticistas

Por favor, describe tu necesidad real."""


def solicitar_reformulacion() -> str:
    """Solicita al usuario reformular su mensaje."""
    return "¿Podrías reformular tu mensaje?"

def solicitar_descripcion_servicio() -> str:
    """Solicita descripción del servicio."""
    return "Por favor describe el servicio."


def mensaje_confirmar_servicio(servicio: str) -> str:
    """Confirma el servicio detectado antes de continuar la búsqueda."""
    from templates.comunes import pie_instrucciones_respuesta_numerica

    servicio_texto = (servicio or "").strip() or "tu solicitud"
    return (
        f"*Entendí que necesitas:* **{servicio_texto}**\n\n"
        f"{pie_instrucciones_respuesta_numerica}\n\n"
        "1) Sí\n"
        "2) No"
    )
