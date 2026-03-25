import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.maintenance.document_update import (
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera_actualizacion,
)
from flows.onboarding.handlers.documentos import (
    manejar_dni_frontal_onboarding as manejar_dni_frontal,
    manejar_foto_perfil_onboarding as manejar_selfie_registro,
)


def test_dni_frontal_actualizacion_marca_persistencia():
    flujo = {}

    respuesta = manejar_dni_frontal_actualizacion(
        flujo,
        {"image_base64": "front-image"},
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["dni_front_image"] == "front-image"
    assert respuesta["messages"][0]["response"] == "__persistir_dni_frontal__"


def test_dni_trasera_actualizacion_persiste_solo_frontal_y_vuelve_menu():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload))

    flujo = {
        "provider_id": "prov-10",
        "dni_front_image": "front-image",
        "esta_registrado": True,
    }

    respuesta = asyncio.run(
        manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga={},
            proveedor_id="prov-10",
            subir_medios_identidad=subir_medios_identidad,
        )
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert llamadas == [
        (
            "prov-10",
            {
                "dni_front_image": "front-image",
            },
        )
    ]
    assert "cédula actualizada" in respuesta["messages"][0]["response"].lower()
    assert respuesta["messages"][1]["response"] == "Elige la opción de interés."


def test_dni_trasera_actualizacion_ignora_reverso_y_persiste_frontal():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload))

    flujo = {
        "provider_id": "prov-10",
        "dni_front_image": "front-image",
        "profile_edit_mode": "personal_dni_front_update",
        "profile_return_state": "viewing_personal_dni_front",
    }

    respuesta = asyncio.run(
        manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga={"image_base64": "back-image"},
            proveedor_id="prov-10",
            subir_medios_identidad=subir_medios_identidad,
        )
    )

    assert llamadas == [("prov-10", {"dni_front_image": "front-image"})]
    assert flujo["state"] == "viewing_personal_dni_front"
    assert respuesta["messages"][1]["ui"]["options"][0]["id"] == "provider_detail_dni_front_change"


def test_dni_frontal_actualizacion_directa_marca_persistencia():
    flujo = {"profile_edit_mode": "personal_dni_front_update"}

    respuesta = manejar_dni_frontal_actualizacion(
        flujo,
        {"image_base64": "front-image"},
    )

    assert flujo["state"] == "awaiting_menu_option"
    assert flujo["dni_front_image"] == "front-image"
    assert respuesta["messages"][0]["response"] == "__persistir_dni_frontal__"


def test_dni_frontal_registro_persiste_de_inmediato_y_avanza():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload.get("phone"), payload.get("dni_front_image")))

    flujo = {}

    respuesta = asyncio.run(
        manejar_dni_frontal(
            flujo,
            {"image_base64": "front-image"},
            telefono="593969648465@s.whatsapp.net",
            subir_medios_identidad=subir_medios_identidad,
        )
    )

    assert flujo["state"] == "onboarding_face_photo"
    assert flujo["phone"] == "593969648465@s.whatsapp.net"
    assert flujo["dni_front_image"] == "front-image"
    assert llamadas == [(None, "593969648465@s.whatsapp.net", "front-image")]
    assert "foto de perfil" in respuesta["messages"][0]["response"].lower()


def test_selfie_registro_persiste_de_inmediato_y_avanza():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload.get("phone"), payload.get("face_image")))

    flujo = {}

    respuesta = asyncio.run(
        manejar_selfie_registro(
            flujo,
            {"image_base64": "face-image"},
            telefono="593995971988@s.whatsapp.net",
            subir_medios_identidad=subir_medios_identidad,
        )
    )

    assert flujo["state"] == "onboarding_experience"
    assert flujo["phone"] == "593995971988@s.whatsapp.net"
    assert flujo["face_image"] == "face-image"
    assert llamadas == [(None, "593995971988@s.whatsapp.net", "face-image")]
    assert "años de experiencia" in respuesta["messages"][0]["response"].lower()
