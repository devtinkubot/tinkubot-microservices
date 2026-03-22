import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.router as modulo_router  # noqa: E402
from flows.router import enrutar_estado, manejar_mensaje
from templates.interfaz.registro_inicio import MENU_ID_REGISTRARSE


def _ejecutar_enrutado(flujo, texto_mensaje, opcion_menu=None):
    return asyncio.run(
        enrutar_estado(
            estado=flujo.get("state"),
            flujo=flujo,
            texto_mensaje=texto_mensaje,
            carga={},
            telefono="593999111299@s.whatsapp.net",
            opcion_menu=opcion_menu,
            tiene_consentimiento=True,
            esta_registrado=True,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=None,
        )
    )


def test_estado_esperando_disponibilidad_mantiene_flujo():
    flujo = {"state": "awaiting_availability_response"}
    resultado = _ejecutar_enrutado(flujo, "hola")

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_availability_response"
    assert "solicitud pendiente de disponibilidad" in resultado["response"]["messages"][0][
        "response"
    ].lower()
    assert "disponible" in resultado["response"]["messages"][0]["response"].lower()
    assert "no disponible" in resultado["response"]["messages"][0]["response"].lower()


def test_estado_esperando_disponibilidad_permite_volver_menu():
    flujo = {"state": "awaiting_availability_response"}
    resultado = _ejecutar_enrutado(flujo, "menu")

    assert resultado is not None
    assert resultado["persist_flow"] is True
    assert flujo["state"] == "awaiting_menu_option"
    assert resultado["response"]["messages"]


def test_reset_devuelve_menu_de_registro():
    flujo = {"state": "awaiting_city"}
    logger = SimpleNamespace(info=lambda *args, **kwargs: None)
    modulo_router.reiniciar_flujo = lambda _telefono: asyncio.sleep(0)
    resultado = asyncio.run(
        manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="reiniciar",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=None,
            logger=logger,
        )
    )

    assert resultado is not None
    assert flujo["state"] == "awaiting_menu_option"
    assert resultado["response"]["messages"][1]["ui"]["options"][0]["id"] == (
        MENU_ID_REGISTRARSE
    )
