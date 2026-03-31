import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.sesion_proveedor import manejar_estado_inicial  # noqa: E402
from templates.onboarding.inicio import (  # noqa: E402
    payload_menu_registro_proveedor,
)
from templates.onboarding.consentimiento import (  # noqa: E402
    payload_consentimiento_proveedor,
)
from templates.onboarding.experiencia import (  # noqa: E402
    ONBOARDING_EXPERIENCE_RANGES_ID,
    payload_experiencia_onboarding,
)
from templates.onboarding.documentos import (  # noqa: E402
    payload_onboarding_dni_frontal,
    payload_onboarding_foto_perfil,
)


def test_payload_menu_registro_proveedor_incluye_header_image_y_registrarse():
    payload = payload_menu_registro_proveedor()

    assert payload["response"].startswith("Para continuar con tu registro")
    assert payload["ui"]["header_type"] == "image"
    assert "tinkubot_providers_onboarding.png" in payload["ui"]["header_media_url"]
    assert payload["ui"]["options"][0]["title"] == "Aceptar"


def test_payload_consentimiento_proveedor_retorna_el_mismo_payload():
    payload = payload_consentimiento_proveedor()

    assert payload["messages"][0]["response"].startswith(
        "Para continuar con tu registro"
    )


def test_estado_inicial_sin_consentimiento_muestra_onboarding():
    flujo = {}

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            tiene_consentimiento=False,
            esta_registrado=False,
            esta_verificado=False,
            telefono="593999111250@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "onboarding_consent"
    assert flujo["mode"] == "registration"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Aceptar"


def test_estado_inicial_sin_provider_id_prioriza_onboarding():
    flujo = {}

    respuesta = asyncio.run(
        manejar_estado_inicial(
            estado=None,
            flujo=flujo,
            provider_id=None,
            tiene_consentimiento=True,
            esta_registrado=True,
            esta_verificado=True,
            telefono="593999111251@s.whatsapp.net",
        )
    )

    assert respuesta is not None
    assert flujo["state"] == "onboarding_consent"
    assert flujo["mode"] == "registration"
    assert respuesta["messages"][0]["ui"]["type"] == "buttons"
    assert respuesta["messages"][0]["ui"]["options"][0]["title"] == "Aceptar"


def test_payload_onboarding_dni_frontal_incluye_imagen_guia():
    payload = payload_onboarding_dni_frontal()

    assert payload["response"].startswith("*Envía una foto frontal de tu cédula.*")
    assert payload["media_type"] == "image"
    assert "tinkubot_dni_photo.png" in payload["media_url"]


def test_payload_onboarding_dni_frontal_usa_env_override(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_ONBOARDING_DNI_FRONT_GUIDE_URL",
        "https://example.com/dni.png",
    )

    payload = payload_onboarding_dni_frontal()

    assert payload["media_url"] == "https://example.com/dni.png"


def test_payload_onboarding_foto_perfil_incluye_imagen_guia():
    payload = payload_onboarding_foto_perfil()

    assert payload["response"].startswith("*Envía tu foto de perfil.*")
    assert payload["media_type"] == "image"
    assert "tinkubot_profile_photo.png" in payload["media_url"]


def test_payload_experiencia_onboarding_incluye_lista():
    payload = payload_experiencia_onboarding()

    assert payload["response"] == "Selecciona tus *años de experiencia*."
    assert payload["ui"]["type"] == "list"
    assert payload["ui"]["header_text"] == "Años de experiencia"
    assert payload["ui"]["id"] == ONBOARDING_EXPERIENCE_RANGES_ID
    assert payload["ui"]["options"][0]["title"] == "Menos de 1 año"
