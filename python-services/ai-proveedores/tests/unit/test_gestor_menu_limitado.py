import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flows.gestores_estados.gestor_menu import manejar_estado_menu


def test_menu_limitado_opcion_4_abre_actualizacion_cedula():
    flujo = {
        "provider_id": "prov-1",
        "services": ["Plomeria"],
        "menu_limitado": True,
    }

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="4",
            opcion_menu="4",
            esta_registrado=True,
            menu_limitado=True,
        )
    )

    assert flujo["menu_limitado"] is True
    assert flujo["state"] == "awaiting_dni_front_photo_update"
    assert "frontal" in respuesta["messages"][0]["response"].lower()


def test_menu_limitado_no_permita_eliminar_por_texto():
    flujo = {
        "provider_id": "prov-2",
        "services": ["Gasfiteria"],
        "menu_limitado": True,
    }

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="eliminar mi registro",
            opcion_menu=None,
            esta_registrado=True,
            menu_limitado=True,
        )
    )

    assert flujo.get("state") != "awaiting_deletion_confirmation"
    assert "no reconoc" in respuesta["messages"][0]["response"].lower()
    assert "Eliminar mi registro" not in respuesta["messages"][1]["response"]


def test_menu_limitado_opcion_5_sale_sin_abrir_eliminacion():
    flujo = {
        "provider_id": "prov-4",
        "services": ["Electricidad"],
        "menu_limitado": True,
    }

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="5",
            opcion_menu="5",
            esta_registrado=True,
            menu_limitado=True,
        )
    )

    assert "perfecto" in respuesta["messages"][0]["response"].lower()
    assert flujo.get("state") is None


def test_menu_completo_opcion_4_abre_confirmacion_eliminacion():
    flujo = {
        "provider_id": "prov-3",
        "services": ["Pintura"],
    }

    respuesta = asyncio.run(
        manejar_estado_menu(
            flujo=flujo,
            texto_mensaje="4",
            opcion_menu="4",
            esta_registrado=True,
            menu_limitado=False,
        )
    )

    assert flujo["state"] == "awaiting_deletion_confirmation"
    assert "eliminar" in respuesta["messages"][0]["response"].lower()
