import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.consentimiento.procesador_respuesta import (  # noqa: E402
    _resolver_opcion_consentimiento,
)
from flows.constructores.construidor_consentimiento import (  # noqa: E402
    construir_respuesta_solicitud_consentimiento,
)
from models.mensajes import RecepcionMensajeWhatsApp  # noqa: E402
from templates.consentimiento.mensajes import (  # noqa: E402
    payload_consentimiento_proveedor,
)


def test_payload_consentimiento_proveedor_retorna_interactive_con_imagen_default():
    payload = payload_consentimiento_proveedor()

    assert "messages" in payload
    assert len(payload["messages"]) == 1
    mensaje = payload["messages"][0]
    assert "Para poder conectarte con clientes" in mensaje["response"]
    assert "- Nombres" in mensaje["response"]
    assert "- Telefono" in mensaje["response"]
    assert "- Ubicación" in mensaje["response"]
    assert "- Foto de perfil" in mensaje["response"]
    assert "https://www.tinku.bot/privacy" in mensaje["response"]
    assert mensaje["ui"]["type"] == "buttons"
    assert mensaje["ui"]["header_type"] == "image"
    assert "tinkubot_providers_onboarding.png" in mensaje["ui"]["header_media_url"]
    assert len(mensaje["ui"]["options"]) == 1
    assert mensaje["ui"]["options"][0]["id"] == "continue_provider_onboarding"
    assert mensaje["ui"]["options"][0]["title"] == "Aceptar"


def test_construir_respuesta_solicitud_consentimiento_reusa_payload_interactivo():
    respuesta = construir_respuesta_solicitud_consentimiento()

    assert respuesta["success"] is True
    assert len(respuesta["messages"]) == 1
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert len(respuesta["messages"][0]["ui"]["options"]) == 1


def test_resolver_opcion_consentimiento_acepta_selected_option_interactivo():
    opcion = _resolver_opcion_consentimiento(
        {
            "selected_option": "continue_provider_onboarding",
            "content": "",
        }
    )

    assert opcion == "1"


def test_resolver_opcion_consentimiento_mantiene_fallback_textual_de_rechazo():
    opcion = _resolver_opcion_consentimiento(
        {
            "selected_option": "",
            "content": "no",
        }
    )

    assert opcion == "2"


def test_modelo_recepcion_preserva_selected_option_interactivo():
    solicitud = RecepcionMensajeWhatsApp(
        from_number="593999111222@s.whatsapp.net",
        content="",
        message_type="interactive_button_reply",
        selected_option="continue_provider_onboarding",
    )

    datos = solicitud.model_dump()

    assert datos["selected_option"] == "continue_provider_onboarding"
    assert datos["message_type"] == "interactive_button_reply"
