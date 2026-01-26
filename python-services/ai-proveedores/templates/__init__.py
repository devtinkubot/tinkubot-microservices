"""Textos base reutilizables para el servicio de proveedores.

Este módulo centraliza todos los templates de mensajes organizados por dominios de negocio.
"""

# ==================== DOMINIO: INTERFAZ ====================
from templates.interfaz.componentes import pie_instrucciones_respuesta_numerica

# ==================== DOMINIO: CONSENTIMIENTO ====================
from templates.consentimiento import (
    CONSENT_OPTIONS,
    CONSENT_PROMPT,
    CONSENT_SCOPE_BLOCK,
    consent_acknowledged_message,
    consent_declined_message,
    consent_options_block,
    consent_prompt_messages,
)

# ==================== DOMINIO: INTERFAZ - MENÚS ====================
from templates.interfaz import (
    PROVIDER_MAIN_MENU,
    PROVIDER_POST_REGISTRATION_MENU,
    provider_main_menu_message,
    provider_post_registration_menu_message,
    provider_services_menu_message,
    informar_cierre_session,
    error_opcion_no_reconocida,
    solicitar_selfie_actualizacion,
    solicitar_selfie_requerida,
    confirmar_selfie_actualizada,
    error_actualizar_selfie,
    solicitar_red_social_actualizacion,
    error_actualizar_redes_sociales,
    confirmar_actualizacion_redes_sociales,
    error_limite_servicios_alcanzado,
    preguntar_nuevo_servicio,
    error_servicio_no_interpretado,
    error_servicios_ya_registrados,
    error_guardar_servicio,
    confirmar_servicios_agregados,
    informar_limite_servicios_alcanzado,
    informar_sin_servicios_eliminar,
    preguntar_servicio_eliminar,
    error_eliminar_servicio,
    confirmar_servicio_eliminado,
)

# ==================== DOMINIO: REGISTRO ====================
from templates.registro import (
    GUIDANCE_MESSAGE,
    REGISTRATION_START_PROMPT,
    provider_guidance_message,
    preguntar_correo_opcional,
    preguntar_actualizar_ciudad,
    solicitar_foto_dni_frontal,
    solicitar_foto_dni_trasera,
    solicitar_foto_dni_trasera_requerida,
    solicitar_selfie_registro,
    solicitar_selfie_requerida_registro,
    informar_datos_recibidos,
)

# ==================== DOMINIO: SESIÓN ====================
from templates.sesion import (
    session_expired_message,
    session_state_expired_mapping,
    session_timeout_warning_message,
    informar_reinicio_conversacion,
    informar_timeout_inactividad,
    informar_reinicio_completo,
)

# ==================== DOMINIO: VERIFICACIÓN ====================
from templates.verificacion import (
    provider_under_review_message,
    provider_verified_message,
)

# Compatibilidad con prompts.py - re-exportar con nombres originales
CONSENT_FOOTER = pie_instrucciones_respuesta_numerica
CONSENT_DECLINED_MESSAGE = (
    "Entendido. Sin tu consentimiento no puedo registrar tu perfil ni compartir tus datos.\n\n"
    'Si cambias de opinión más adelante, escribe "registro" y continuamos desde aquí. '
    "Gracias por tu tiempo."
)

__all__ = [
    # Comunes
    "pie_instrucciones_respuesta_numerica",
    "CONSENT_FOOTER",
    # Consentimiento
    "CONSENT_PROMPT",
    "CONSENT_SCOPE_BLOCK",
    "CONSENT_OPTIONS",
    "consent_options_block",
    "consent_prompt_messages",
    "consent_acknowledged_message",
    "consent_declined_message",
    # Registro
    "REGISTRATION_START_PROMPT",
    "GUIDANCE_MESSAGE",
    "provider_guidance_message",
    "preguntar_correo_opcional",
    "preguntar_actualizar_ciudad",
    "solicitar_foto_dni_frontal",
    "solicitar_foto_dni_trasera",
    "solicitar_foto_dni_trasera_requerida",
    "solicitar_selfie_registro",
    "solicitar_selfie_requerida_registro",
    "informar_datos_recibidos",
    # Menús
    "PROVIDER_MAIN_MENU",
    "PROVIDER_POST_REGISTRATION_MENU",
    "provider_main_menu_message",
    "provider_post_registration_menu_message",
    "provider_services_menu_message",
    # Interfaz - mensajes comunes
    "informar_cierre_session",
    "error_opcion_no_reconocida",
    # Interfaz - actualización de perfil
    "solicitar_selfie_actualizacion",
    "solicitar_selfie_requerida",
    "confirmar_selfie_actualizada",
    "error_actualizar_selfie",
    "solicitar_red_social_actualizacion",
    "error_actualizar_redes_sociales",
    "confirmar_actualizacion_redes_sociales",
    # Interfaz - servicios
    "error_limite_servicios_alcanzado",
    "preguntar_nuevo_servicio",
    "error_servicio_no_interpretado",
    "error_servicios_ya_registrados",
    "error_guardar_servicio",
    "confirmar_servicios_agregados",
    "informar_limite_servicios_alcanzado",
    "informar_sin_servicios_eliminar",
    "preguntar_servicio_eliminar",
    "error_eliminar_servicio",
    "confirmar_servicio_eliminado",
    # Verificación
    "provider_under_review_message",
    "provider_verified_message",
    # Sesión
    "session_timeout_warning_message",
    "session_expired_message",
    "session_state_expired_mapping",
    "informar_reinicio_conversacion",
    "informar_timeout_inactividad",
    "informar_reinicio_completo",
]
