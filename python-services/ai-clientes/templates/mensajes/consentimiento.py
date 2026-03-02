"""Mensajes de onboarding/consentimiento para clientes."""

import os
from typing import Any, Dict

# ==================== MENSAJES ====================

mensaje_consentimiento_session_first = """Para ayudarte a buscar expertos cercanos, usaré tu ubicación y tu necesidad para gestionar solicitudes en tiempo real.

Política de privacidad:
https://tinku.bot/privacy.html"""

opciones_consentimiento_textos = ["Continuar", "Cancelar"]
consent_accept_id = "consent_accept"
consent_decline_id = "consent_decline"

ONBOARDING_STRATEGY_ENV = "WA_ONBOARDING_STRATEGY"
ONBOARDING_STRATEGY_SESSION_FIRST = "session_first_v1"
ONBOARDING_IMAGE_URL_ENV = "WA_ONBOARDING_IMAGE_URL"
ONBOARDING_IMAGE_CAPTION_ENV = "WA_ONBOARDING_IMAGE_CAPTION"
ONBOARDING_CONTINUE_LABEL_ENV = "WA_ONBOARDING_CONTINUE_LABEL"
ONBOARDING_CONTINUE_ID_ENV = "WA_ONBOARDING_CONTINUE_ID"
ONBOARDING_FOOTER_TEXT_ENV = "WA_ONBOARDING_FOOTER_TEXT"
ONBOARDING_FOOTER_TEXT_MAX_LEN = 60


# ==================== FUNCIONES ====================

def estrategia_onboarding() -> str:
    """Retorna la estrategia activa; hoy solo soportamos session_first_v1."""
    estrategia = os.getenv(ONBOARDING_STRATEGY_ENV, ONBOARDING_STRATEGY_SESSION_FIRST).strip()
    if estrategia != ONBOARDING_STRATEGY_SESSION_FIRST:
        return ONBOARDING_STRATEGY_SESSION_FIRST
    return ONBOARDING_STRATEGY_SESSION_FIRST


def onboarding_precontractual_habilitado() -> bool:
    """Siempre true para el flujo actual de consentimiento+ciudad."""
    return estrategia_onboarding() == ONBOARDING_STRATEGY_SESSION_FIRST


def _normalizar_footer_text(texto: str) -> str:
    """Limpia y limita el footer para cumplir restricción de Meta (máx 60 chars)."""
    limpio = (texto or "").strip()
    if not limpio:
        return ""
    return limpio[:ONBOARDING_FOOTER_TEXT_MAX_LEN]


def payload_consentimiento_resumen() -> Dict[str, Any]:
    """Retorna payload de onboarding para estrategia única session_first_v1."""
    image_url = os.getenv(ONBOARDING_IMAGE_URL_ENV, "").strip()
    image_caption = os.getenv(ONBOARDING_IMAGE_CAPTION_ENV, "").strip()
    continue_label = os.getenv(ONBOARDING_CONTINUE_LABEL_ENV, "Continuar").strip() or "Continuar"
    continue_id = os.getenv(ONBOARDING_CONTINUE_ID_ENV, "continue_onboarding").strip() or "continue_onboarding"

    ui_buttons: Dict[str, Any] = {
        "type": "buttons",
        "id": "onboarding_continue_v1",
        "options": [{"id": continue_id, "title": continue_label}],
    }
    footer_text = os.getenv(
        ONBOARDING_FOOTER_TEXT_ENV,
        "Al continuar aceptas nuestras condiciones.",
    )
    footer_text = _normalizar_footer_text(footer_text)
    if footer_text:
        ui_buttons["footer_text"] = footer_text
    if image_url:
        ui_buttons["header_type"] = "image"
        ui_buttons["header_media_url"] = image_url
    elif image_caption:
        ui_buttons["header_type"] = "text"
        ui_buttons["header_text"] = image_caption

    return {
        "messages": [
            {
                "response": mensaje_consentimiento_session_first,
                "ui": ui_buttons,
            }
        ]
    }


def mensaje_rechazo_consentimiento() -> str:
    """Mensaje cuando el usuario rechaza que TinkuBot use sus datos.

    Returns:
        Mensaje explicativo con opción de reconsiderar.
    """
    return """Entendido. Sin tu consentimiento no puedo buscar profesionales para ti.

Si cambias de opinión, simplemente escribe "hola" y podremos empezar de nuevo.

📞 ¿Necesitas ayuda directamente? Llámanos al [número de atención al cliente]"""
