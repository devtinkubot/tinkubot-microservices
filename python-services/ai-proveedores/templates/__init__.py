"""Plantillas de texto para AI Proveedores."""

# Re-exportar desde los módulos granulares para mantener compatibilidad
# TODO: Fase 2 - migrar imports a usar los módulos específicos

from templates.comunes import pie_instrucciones_respuesta_numerica
from templates.consentimiento import (
    CONSENT_OPTIONS,
    CONSENT_PROMPT,
    CONSENT_SCOPE_BLOCK,
    consent_acknowledged_message,
    consent_declined_message,
    consent_options_block,
    consent_prompt_messages,
)
from templates.menus import (
    PROVIDER_MAIN_MENU,
    PROVIDER_POST_REGISTRATION_MENU,
    provider_main_menu_message,
    provider_post_registration_menu_message,
    provider_services_menu_message,
)
from templates.registro_proveedor import (
    GUIDANCE_MESSAGE,
    REGISTRATION_START_PROMPT,
    provider_guidance_message,
)
from templates.sesion import (
    session_expired_message,
    session_state_expired_mapping,
    session_timeout_warning_message,
)
from templates.verificacion import (
    provider_approved_notification,
    provider_under_review_message,
    provider_verified_message,
)

# Compatibilidad con prompts.py - re-exportar con nombres originales
CONSENT_FOOTER = pie_instrucciones_respuesta_numerica

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
    # Menús
    "PROVIDER_MAIN_MENU",
    "PROVIDER_POST_REGISTRATION_MENU",
    "provider_main_menu_message",
    "provider_post_registration_menu_message",
    "provider_services_menu_message",
    # Verificación
    "provider_under_review_message",
    "provider_verified_message",
    "provider_approved_notification",
    # Sesión
    "session_timeout_warning_message",
    "session_expired_message",
    "session_state_expired_mapping",
]
