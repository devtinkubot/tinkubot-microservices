import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.gestores_estados.gestor_documentos import (
    manejar_dni_frontal_actualizacion,
    manejar_dni_trasera_actualizacion,
)


def test_dni_frontal_actualizacion_avanza_a_reverso():
    flujo = {"menu_limitado": True}

    respuesta = manejar_dni_frontal_actualizacion(
        flujo,
        {"image_base64": "front-image"},
    )

    assert flujo["state"] == "awaiting_dni_back_photo_update"
    assert flujo["dni_front_image"] == "front-image"
    assert "posterior" in respuesta["messages"][0]["response"].lower()


def test_dni_trasera_actualizacion_persiste_y_vuelve_menu():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload))

    flujo = {
        "menu_limitado": True,
        "provider_id": "prov-10",
        "dni_front_image": "front-image",
        "esta_registrado": True,
    }

    respuesta = asyncio.run(
        manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga={"image_base64": "back-image"},
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
                "dni_back_image": "back-image",
            },
        )
    ]
    assert "cédula actualizada" in respuesta["messages"][0]["response"].lower()
    assert "actualizar cédula" in respuesta["messages"][1]["response"].lower()


def test_dni_trasera_actualizacion_permite_actualizar_solo_reverso():
    llamadas = []

    async def subir_medios_identidad(proveedor_id, payload):
        llamadas.append((proveedor_id, payload))

    flujo = {
        "menu_limitado": False,
        "provider_id": "prov-10",
        "profile_edit_mode": "personal_dni_back_update",
        "profile_return_state": "viewing_personal_dni_back",
    }

    respuesta = asyncio.run(
        manejar_dni_trasera_actualizacion(
            flujo=flujo,
            carga={"image_base64": "back-image"},
            proveedor_id="prov-10",
            subir_medios_identidad=subir_medios_identidad,
        )
    )

    assert llamadas == [("prov-10", {"dni_back_image": "back-image"})]
    assert flujo["state"] == "viewing_personal_dni_back"
    assert respuesta["messages"][1]["ui"]["options"][0]["id"] == "provider_detail_dni_back_change"


def test_dni_frontal_actualizacion_directa_marca_persistencia():
    flujo = {"profile_edit_mode": "personal_dni_front_update"}

    respuesta = manejar_dni_frontal_actualizacion(
        flujo,
        {"image_base64": "front-image"},
    )

    assert flujo["state"] == "awaiting_dni_back_photo_update"
    assert flujo["dni_front_image"] == "front-image"
    assert respuesta["messages"][0]["response"] == "__persistir_dni_frontal__"
