import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.sesion_proveedor import manejar_estado_inicial  # noqa: E402
from templates.interfaz.registro_inicio import (  # noqa: E402
    MENU_ID_REGISTRARSE,
    payload_menu_registro_proveedor,
)
from templates.registro import (  # noqa: E402
    payload_experiencia_registro,
)
from templates.registro.documentacion import (  # noqa: E402
    payload_foto_dni_frontal,
    payload_selfie_registro,
)


def test_payload_menu_registro_proveedor_incluye_header_image_y_registrarse():
    payload = payload_menu_registro_proveedor()

    assert payload["response"].startswith("¡Hola! Vamos a crear tu perfil de proveedor")
    assert payload["ui"]["type"] == "buttons"
    assert payload["ui"]["header_type"] == "image"
    assert "tinkubot_provider_start_register.png" in payload["ui"]["header_media_url"]
    assert payload["ui"]["options"][0]["id"] == MENU_ID_REGISTRARSE


def test_estado_inicial_sin_consentimiento_muestra_menu_de_registro():
    flujo = {}

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=False,
            esta_registrado=False,
            esta_verificado=False,
            menu_limitado=False,
            approved_basic=False,
            telefono="593999111250@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["mode"] == "registration"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["id"] == MENU_ID_REGISTRARSE


def test_payload_foto_dni_frontal_incluye_imagen_guia():
    payload = payload_foto_dni_frontal()

    assert payload["response"].startswith("Ahora envía una foto frontal de tu *cédula*")
    assert payload["media_type"] == "image"
    assert "tinkubot_dni_photo.png" in payload["media_url"]


def test_payload_foto_dni_frontal_usa_env_override(monkeypatch):
    monkeypatch.setenv("WA_PROVIDER_DNI_FRONT_GUIDE_URL", "https://example.com/dni.png")

    payload = payload_foto_dni_frontal()

    assert payload["media_url"] == "https://example.com/dni.png"


def test_payload_selfie_registro_incluye_imagen_guia():
    payload = payload_selfie_registro()

    assert payload["response"].startswith("Ahora envía tu *foto de perfil*")
    assert payload["media_type"] == "image"
    assert "tinkubot_profile_photo.png" in payload["media_url"]


def test_payload_experiencia_registro_incluye_lista():
    payload = payload_experiencia_registro()

    assert payload["response"] == "Selecciona tus *años de experiencia*."
    assert payload["ui"]["type"] == "list"
    assert payload["ui"]["header_text"] == "Años de experiencia"
    assert payload["ui"]["options"][0]["title"] == "Menos de 1 año"
